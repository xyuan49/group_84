# GlucoTrack backend

## Setup

```
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate on Mac/Linux
pip install -r backend/requirements.txt
```

## Build the database

First generate and filter the Synthea data (see `data/README.md`), then from
`backend/`:

```
python -m app.loaders.synthea ../data/synthea_t2d
```

This creates `backend/glucotrack.db` (SQLite, gitignored; ~21 MB after all loaders) with 85
patients. Re-running skips patients already loaded. Set `DATABASE_URL` to use
a different database file.

Then add the UCI self-monitoring data (download steps in `data/README.md`):

```
python -m app.loaders.uci ../data/uci_raw/Diabetes-Data
```

Synthea has only a few lab glucose values per patient per year, so this gives
the 27 insulin-treated Synthea patients weeks of glucose, insulin and meal
records (median 47 glucose readings in the last 14 days). Each UCI series is
shifted so it ends on 2026-11-01, the Synthea reference date (`--anchor` to
change); time of day is kept. Only series with real device timestamps and at
least 14 days of data are used. Records are validated with Pydantic models
(`UciRecord`, `UciGlucose`, `UciInsulin`, `UciMeal`); invalid rows are counted
and skipped. Re-running skips patients that already have UCI data.

Then add the Shanghai T2DM continuous glucose monitoring (CGM) data:

```
python -m app.loaders.shanghai ../data/shanghai_raw/Shanghai_T2DM
```

This covers the patients who are not on insulin: 41 of the 58 get a CGM
series (a reading every 15 minutes, 7-14 days, plus diet records). Only
Shanghai patients who received no insulin and have at least 7 days of CGM
are used, one file per person. Dates are shifted the same way as UCI.
Records are validated with Pydantic models (`CgmReading`, `DietEntry`).
Finger-stick glucose, ketones and oral-medication records in the files are
not stored. Re-running skips patients that already have CGM data.

After all three loaders, 68 of 85 patients have dense glucose data for the
last 14 days; the other 17 (no insulin, no CGM series left) only have
Synthea lab values.

## Tables (`app/models.py`)

| Table | Contents | Source |
|---|---|---|
| `patients` | name, gender, birth date | FHIR Patient |
| `conditions` | diagnoses and history, SNOMED CT code | FHIR Condition |
| `medications` | prescriptions, RxNorm code, status, prescriber | FHIR MedicationRequest |
| `observations` | HbA1c `4548-4`, BMI `39156-5`, systolic `8480-6`, diastolic `8462-4` | FHIR Observation |
| `glucose_readings` | all glucose values, with `source` = fhir / user / uci / cgm and optional `meal_context` | FHIR lab glucose, UCI, Shanghai CGM, patient entries |
| `insulin_doses` | units, insulin type (`short` regular / `intermediate` NPH / `long` UltraLente for UCI), time | patient entries / UCI |
| `meals` | description, carbs, calories (UCI meals only say typical / larger / smaller; Shanghai meals list foods and portions; no carbs in either) | patient entries / UCI / Shanghai CGM |

Notes:
- Times are stored as the patient's local clock time (offset dropped) so
  time-of-day analysis works.
- A FHIR blood pressure panel (`85354-9`) becomes two `observations` rows
  (systolic + diastolic) with the same `fhir_id`.
- `conditions` includes every Synthea condition, including social findings
  such as "Risk activity involvement (finding)". Filter by SNOMED code or by
  `(disorder)` in `display` for medical history.

## API

Run from `backend/` (after building the database):

```
uvicorn app.main:app --reload
```

Open http://localhost:8000 (redirects to the interactive docs at `/docs`).
CORS allows the Vite dev server (`http://localhost:5173`); set `CORS_ORIGINS`
(comma-separated) to allow other frontends, e.g. the deployed site.

Current endpoints:

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{"status": "ok"}` |
| GET | `/api/patients?limit=&offset=` | patients, sorted by name |
| GET | `/api/patients/{patient_id}` | one patient, or 404 |
| GET | `.../{patient_id}/conditions?status=&disorders_only=` | diagnoses, newest first; `disorders_only=true` hides social findings |
| GET | `.../{patient_id}/medications?status=` | prescriptions, newest first; `active` / `completed` / `stopped` |
| GET | `.../{patient_id}/observations?code=&start=&end=&days=` | HbA1c `4548-4`, BMI `39156-5`, systolic `8480-6`, diastolic `8462-4`; `code` repeatable |
| GET | `.../{patient_id}/glucose?source=&start=&end=&days=` | all glucose in one history; `source` fhir / uci / cgm / user, repeatable |
| GET | `.../{patient_id}/insulin?source=&start=&end=&days=` | insulin doses (UCI patients only so far) |
| GET | `.../{patient_id}/meals?source=&start=&end=&days=` | meals (UCI and Shanghai) |

Time series (observations, glucose, insulin, meals) come back oldest first,
ready to plot. `days=N` means the last N days ending at the patient's latest
matching record (or at `end`), not at today: the loaded data ends on
2026-11-01. Use `days` or `start`, not both. CGM patients have ~1,300 glucose
readings per 14 days, so pass a range for charts.

Layout:

```
app/main.py            app, CORS, includes each router
app/schemas.py         Pydantic request/response models
app/routers/<name>.py  one router per resource (patients.py is the example)
tests/conftest.py      `client` fixture: API on an empty in-memory database
```

Pydantic models in `app/schemas.py`:

| Model | For | Validation |
|---|---|---|
| `PatientOut`, `ConditionOut`, `MedicationOut`, `ObservationOut` | reading the clinical record | — |
| `GlucoseOut`, `InsulinOut`, `MealOut` | reading logs from any source (`fhir` / `user` / `uci` / `cgm`) | `source`, `meal_context`, `insulin_type` must be known values |
| `GlucoseIn` | patient logs a reading | 20–600 mg/dL; `meal_context` fasting / before_meal / after_meal / bedtime |
| `InsulinIn` | patient logs a dose | 0 < units ≤ 100; type rapid / short / intermediate / long / premixed |
| `MealIn` | patient logs a meal | only `eaten_at` required; description ≤ 500 chars, carbs 0–500 g, calories 0–5000 |

`...In` models drop a UTC offset and keep the clock time, matching how the
loaders store times. Endpoints set `source="user"` themselves; it is not
part of the request.

To add an endpoint, follow `app/routers/patients.py`:

1. Add a response model to `app/schemas.py` (subclass `ORMModel` so it reads
   SQLAlchemy rows), and a request model with `Field(...)` limits for POSTs.
2. Add the route to a router, with `db: Session = Depends(get_db)` and
   `response_model=...`. Per-patient routes take
   `patient: Patient = Depends(get_patient)` so a bad id returns 404.
3. New router file? Include it in `app/main.py`.
4. Test it with the `client` fixture: add rows through `db_session`, then
   call the endpoint (see `tests/test_api.py`).

## Tests

```
cd backend
python -m pytest
```
