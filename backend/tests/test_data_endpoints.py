from datetime import datetime

import pytest

from app.models import Condition, GlucoseReading, InsulinDose, Meal, Medication, Observation

PID = "p-1"


@pytest.fixture
def record(db_session, patients):
    db_session.add_all([
        Condition(id="c-1", patient_id=PID, snomed_code="44054006", display="Diabetes mellitus type 2 (disorder)",
                  clinical_status="active", onset_at=datetime(2016, 5, 1)),
        Condition(id="c-2", patient_id=PID, snomed_code="160903007", display="Full-time employment (finding)",
                  clinical_status="active", onset_at=datetime(2018, 1, 1)),
        Condition(id="c-3", patient_id=PID, snomed_code="444814009", display="Viral sinusitis (disorder)",
                  clinical_status="resolved", onset_at=datetime(2020, 1, 1)),
        Medication(id="m-1", patient_id=PID, name="Metformin 500 MG", status="active",
                   authored_on=datetime(2020, 1, 1)),
        Medication(id="m-2", patient_id=PID, name="Lisinopril 10 MG", status="completed",
                   authored_on=datetime(2021, 1, 1)),
        Observation(patient_id=PID, loinc_code="4548-4", display="HbA1c", value=7.9, unit="%",
                    effective_at=datetime(2025, 1, 1)),
        Observation(patient_id=PID, loinc_code="4548-4", display="HbA1c", value=7.1, unit="%",
                    effective_at=datetime(2026, 6, 1)),
        Observation(patient_id=PID, loinc_code="8480-6", display="Systolic", value=132, unit="mm[Hg]",
                    effective_at=datetime(2026, 6, 1)),
        Observation(patient_id=PID, loinc_code="8462-4", display="Diastolic", value=84, unit="mm[Hg]",
                    effective_at=datetime(2026, 6, 1)),
        Observation(patient_id=PID, loinc_code="39156-5", display="BMI", value=27.5, unit="kg/m2",
                    effective_at=datetime(2026, 9, 1)),
        # Glucose from three sources; the latest is 2026-11-01 08:00.
        GlucoseReading(patient_id=PID, value_mg_dl=110, measured_at=datetime(2026, 6, 1), source="fhir"),
        GlucoseReading(patient_id=PID, value_mg_dl=180, measured_at=datetime(2026, 10, 20, 7), source="uci",
                       meal_context="fasting"),
        GlucoseReading(patient_id=PID, value_mg_dl=140, measured_at=datetime(2026, 10, 31, 8), source="cgm"),
        GlucoseReading(patient_id=PID, value_mg_dl=150, measured_at=datetime(2026, 11, 1, 8), source="cgm"),
        InsulinDose(patient_id=PID, units=6, insulin_type="short", administered_at=datetime(2026, 10, 1, 7),
                    source="uci"),
        InsulinDose(patient_id=PID, units=12, insulin_type="intermediate",
                    administered_at=datetime(2026, 10, 30, 7), source="uci"),
        Meal(patient_id=PID, eaten_at=datetime(2026, 10, 31, 12), description="Rice 150 g", source="cgm"),
        Meal(patient_id=PID, eaten_at=datetime(2026, 11, 1, 12), description=None, source="cgm"),
    ])
    db_session.commit()


def get(client, path, **params):
    r = client.get(f"/api/patients/{PID}/{path}", params=params)
    assert r.status_code == 200, r.text
    return r.json()


# --- clinical record -------------------------------------------------------


def test_conditions_newest_first_and_filters(client, record):
    assert [c["id"] for c in get(client, "conditions")] == ["c-3", "c-2", "c-1"]
    assert [c["id"] for c in get(client, "conditions", status="active")] == ["c-2", "c-1"]
    assert [c["id"] for c in get(client, "conditions", disorders_only=True, status="active")] == ["c-1"]


def test_medications_filter_by_status(client, record):
    assert [m["name"] for m in get(client, "medications")] == ["Lisinopril 10 MG", "Metformin 500 MG"]
    assert [m["name"] for m in get(client, "medications", status="active")] == ["Metformin 500 MG"]


def test_observations_by_code_oldest_first(client, record):
    assert [o["value"] for o in get(client, "observations", code="4548-4")] == [7.9, 7.1]
    bp = get(client, "observations", code=["8480-6", "8462-4"])
    assert {o["loinc_code"]: o["value"] for o in bp} == {"8480-6": 132, "8462-4": 84}
    assert len(get(client, "observations")) == 5


def test_observations_days_counts_back_from_latest_matching_value(client, record):
    # Latest HbA1c is 2026-06-01; the newer BMI must not move the window.
    assert [o["value"] for o in get(client, "observations", code="4548-4", days=30)] == [7.1]


# --- glucose, insulin, meals -----------------------------------------------


def test_glucose_combines_sources_oldest_first(client, record):
    assert [(g["source"], g["value_mg_dl"]) for g in get(client, "glucose")] == [
        ("fhir", 110), ("uci", 180), ("cgm", 140), ("cgm", 150)]
    assert [g["value_mg_dl"] for g in get(client, "glucose", source=["uci", "fhir"])] == [110, 180]


def test_glucose_days_ends_at_latest_reading_not_today(client, record):
    # Data ends 2026-11-01; "last 14 days" must still find it.
    assert [g["value_mg_dl"] for g in get(client, "glucose", days=14)] == [180, 140, 150]
    assert [g["value_mg_dl"] for g in get(client, "glucose", days=1)] == [140, 150]


def test_glucose_start_end_and_days_with_end(client, record):
    assert [g["value_mg_dl"] for g in get(client, "glucose", start="2026-10-01T00:00", end="2026-10-31T23:59")] \
        == [180, 140]
    assert [g["value_mg_dl"] for g in get(client, "glucose", end="2026-10-31T23:59", days=14)] == [180, 140]


def test_start_and_days_together_rejected(client, record):
    r = client.get(f"/api/patients/{PID}/glucose", params={"start": "2026-10-01T00:00", "days": 7})
    assert r.status_code == 422


def test_unknown_source_rejected(client, record):
    assert client.get(f"/api/patients/{PID}/glucose", params={"source": "spreadsheet"}).status_code == 422


def test_insulin_and_meals(client, record):
    assert [(d["units"], d["insulin_type"]) for d in get(client, "insulin", days=7)] == [(12, "intermediate")]
    meals = get(client, "meals")
    assert [m["description"] for m in meals] == ["Rice 150 g", None]


def test_empty_patient_and_unknown_patient(client, record):
    assert client.get("/api/patients/p-2/glucose", params={"days": 14}).json() == []
    for path in ("conditions", "medications", "observations", "glucose", "insulin", "meals"):
        assert client.get(f"/api/patients/missing/{path}").status_code == 404
