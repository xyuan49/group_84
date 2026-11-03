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

This creates `backend/glucotrack.db` (SQLite, ~10 MB, gitignored) with 85
patients. Re-running skips patients already loaded. Set `DATABASE_URL` to use
a different database file.

## Tables (`app/models.py`)

| Table | Contents | Source |
|---|---|---|
| `patients` | name, gender, birth date | FHIR Patient |
| `conditions` | diagnoses and history, SNOMED CT code | FHIR Condition |
| `medications` | prescriptions, RxNorm code, status, prescriber | FHIR MedicationRequest |
| `observations` | HbA1c `4548-4`, BMI `39156-5`, systolic `8480-6`, diastolic `8462-4` | FHIR Observation |
| `glucose_readings` | all glucose values, with `source` = fhir / user / uci / cgm and optional `meal_context` | FHIR lab glucose + patient entries |
| `insulin_doses` | units, insulin type, time | patient entries / UCI (not loaded yet) |
| `meals` | description, carbs, calories | patient entries / UCI (not loaded yet) |

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
