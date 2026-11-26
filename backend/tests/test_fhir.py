from datetime import datetime

import pytest

from app.models import GlucoseReading, Observation

PID = "p-1"


@pytest.fixture
def readings(db_session, patients):
    db_session.add_all([
        GlucoseReading(id=1, patient_id=PID, value_mg_dl=110, measured_at=datetime(2026, 7, 1, 8, 0),
                       meal_context="fasting", source="cgm"),
        GlucoseReading(id=2, patient_id=PID, value_mg_dl=160, measured_at=datetime(2026, 1, 10, 13, 0),
                       source="fhir"),
        GlucoseReading(id=3, patient_id="p-2", value_mg_dl=99, measured_at=datetime(2026, 7, 1, 8, 0),
                       source="uci"),
        Observation(id=10, patient_id=PID, loinc_code="4548-4", display="Hemoglobin A1c", value=7.1, unit="%",
                    effective_at=datetime(2026, 6, 1, 9, 0)),
        Observation(id=11, patient_id=PID, loinc_code="39156-5", display="BMI", value=31.2, unit="kg/m2",
                    effective_at=datetime(2026, 6, 1, 9, 0)),
    ])
    db_session.commit()


def entries(response):
    return [e["resource"] for e in response.json()["entry"]]


def test_search_returns_searchset_bundle(client, readings):
    r = client.get("/fhir/Observation", params={"patient": PID})

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/fhir+json")
    bundle = r.json()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "searchset"
    assert bundle["total"] == 4
    # newest first, across glucose readings and other observations
    ids = [res["id"] for res in entries(r)]
    assert ids[0] == "glucose-1"  # Jul 2026
    assert set(ids[1:3]) == {"obs-10", "obs-11"}  # Jun 2026, same time
    assert ids[3] == "glucose-2"  # Jan 2026
    assert all(res["subject"] == {"reference": "Patient/p-1"} for res in entries(r))


def test_glucose_observation_shape(client, readings):
    r = client.get("/fhir/Observation/glucose-1")

    res = r.json()
    assert res["resourceType"] == "Observation"
    assert res["status"] == "final"
    assert res["code"]["coding"][0] == {"system": "http://loinc.org", "code": "2339-0",
                                        "display": "Glucose [Mass/volume] in Blood"}
    assert res["valueQuantity"] == {"value": 110, "unit": "mg/dL", "system": "http://unitsofmeasure.org",
                                    "code": "mg/dL"}
    # local clock time gets the configured zone's offset (EDT in July)
    assert res["effectiveDateTime"] == "2026-07-01T08:00:00-04:00"
    assert res["note"] == [{"text": "Meal context: fasting"}]


def test_paired_dataset_readings_are_labelled(client, readings):
    tag = client.get("/fhir/Observation/glucose-1").json()["meta"]["tag"][0]
    assert tag["code"] == "cgm"
    assert "paired with a synthetic patient" in tag["display"]

    tag = client.get("/fhir/Observation/glucose-2").json()["meta"]["tag"][0]
    assert tag["code"] == "fhir"


def test_effective_time_uses_winter_offset(client, readings):
    assert client.get("/fhir/Observation/glucose-2").json()["effectiveDateTime"] == "2026-01-10T13:00:00-05:00"


def test_timezone_is_configurable(client, readings, monkeypatch):
    monkeypatch.setenv("GLUCOTRACK_TIMEZONE", "Asia/Shanghai")
    assert client.get("/fhir/Observation/glucose-1").json()["effectiveDateTime"] == "2026-07-01T08:00:00+08:00"


def test_vitals_and_labs_keep_their_code_and_category(client, readings):
    hba1c = client.get("/fhir/Observation/obs-10").json()
    assert hba1c["code"]["coding"][0]["code"] == "4548-4"
    assert hba1c["valueQuantity"]["unit"] == "%"
    assert hba1c["category"][0]["coding"][0]["code"] == "laboratory"

    bmi = client.get("/fhir/Observation/obs-11").json()
    assert bmi["category"][0]["coding"][0]["code"] == "vital-signs"


@pytest.mark.parametrize("code, expected", [
    ("2339-0", {"glucose-1", "glucose-2"}),
    ("http://loinc.org|4548-4", {"obs-10"}),
    ("4548-4,39156-5", {"obs-10", "obs-11"}),
    ("2339-0,4548-4", {"glucose-1", "glucose-2", "obs-10"}),
    ("http://snomed.info/sct|4548-4", set()),
])
def test_search_by_code(client, readings, code, expected):
    r = client.get("/fhir/Observation", params={"patient": PID, "code": code})
    assert {res["id"] for res in entries(r)} == expected
    assert r.json()["total"] == len(expected)


def test_search_count_limits_entries_not_total(client, readings):
    r = client.get("/fhir/Observation", params={"patient": "Patient/p-1", "_count": 2})
    assert len(r.json()["entry"]) == 2
    assert r.json()["total"] == 4


def test_search_unknown_patient_is_operation_outcome(client, readings):
    r = client.get("/fhir/Observation", params={"patient": "nobody"})
    assert r.status_code == 404
    assert r.json()["resourceType"] == "OperationOutcome"


@pytest.mark.parametrize("oid", ["glucose-999", "obs-999", "other-1", "glucose-abc", "1"])
def test_read_unknown_is_404(client, readings, oid):
    r = client.get(f"/fhir/Observation/{oid}")
    assert r.status_code == 404
    assert r.json()["resourceType"] == "OperationOutcome"


def glucose_body(**overrides):
    body = {
        "resourceType": "Observation",
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0"}]},
        "subject": {"reference": "Patient/p-1"},
        "effectiveDateTime": "2026-11-20T07:45:00-05:00",
        "valueQuantity": {"value": 132, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"},
    }
    body.update(overrides)
    return body


def test_create_glucose_observation(client, patients):
    r = client.post("/fhir/Observation", json=glucose_body())

    assert r.status_code == 201
    res = r.json()
    assert r.headers["location"] == f"/fhir/Observation/{res['id']}"
    assert res["valueQuantity"]["value"] == 132
    assert res["meta"]["tag"][0]["code"] == "user"
    assert res["effectiveDateTime"] == "2026-11-20T07:45:00-05:00"

    # stored as a normal patient entry, visible to the app's own API
    saved = client.get("/api/patients/p-1/glucose?source=user").json()
    assert [(g["value_mg_dl"], g["measured_at"]) for g in saved] == [(132, "2026-11-20T07:45:00")]


def test_create_converts_offset_to_local_time(client, patients):
    body = glucose_body(effectiveDateTime="2026-11-20T12:45:00Z")
    client.post("/fhir/Observation", json=body)
    assert client.get("/api/patients/p-1/glucose").json()[0]["measured_at"] == "2026-11-20T07:45:00"


def test_create_converts_mmol_per_l(client, patients):
    body = glucose_body(valueQuantity={"value": 7.0, "unit": "mmol/L", "system": "http://unitsofmeasure.org",
                                       "code": "mmol/L"})
    res = client.post("/fhir/Observation", json=body).json()
    assert res["valueQuantity"]["value"] == 126.1
    assert res["valueQuantity"]["unit"] == "mg/dL"


def test_create_accepts_absolute_patient_reference(client, patients):
    body = glucose_body(subject={"reference": "http://example.org/fhir/Patient/p-2"})
    assert client.post("/fhir/Observation", json=body).json()["subject"] == {"reference": "Patient/p-2"}


@pytest.mark.parametrize("overrides, status", [
    ({"resourceType": "Patient"}, 400),
    ({"code": {"coding": [{"system": "http://loinc.org", "code": "4548-4"}]}}, 422),
    ({"subject": {"reference": "Patient/nobody"}}, 422),
    ({"subject": {"reference": "Group/1"}}, 422),
    ({"effectiveDateTime": "yesterday"}, 422),
    ({"valueQuantity": {"value": 132, "code": "g/L"}}, 422),
    ({"valueQuantity": {"value": "132", "code": "mg/dL"}}, 422),
    ({"valueQuantity": {"value": 700, "code": "mg/dL"}}, 422),
])
def test_create_rejects_invalid_observation(client, patients, overrides, status):
    r = client.post("/fhir/Observation", json=glucose_body(**overrides))
    assert r.status_code == status
    assert r.json()["resourceType"] == "OperationOutcome"
    assert client.get("/api/patients/p-1/glucose").json() == []


def test_create_rejects_non_json(client, patients):
    r = client.post("/fhir/Observation", content="not json", headers={"Content-Type": "application/fhir+json"})
    assert r.status_code == 400
