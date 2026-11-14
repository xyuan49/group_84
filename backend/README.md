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
- For the API: use `app.db.get_db` as the FastAPI dependency for a session.

## Tests

```
cd backend
python -m pytest
```
