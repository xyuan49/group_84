from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.loaders.synthea import load_bundle
from app.models import Condition, GlucoseReading, Medication, Observation, Patient

LOINC = "http://loinc.org"
PID = "p-1"


def quantity(value, unit):
    return {"value": value, "unit": unit}


def obs(id, code, display, **extra):
    return {
        "resourceType": "Observation",
        "id": id,
        "code": {"coding": [{"system": LOINC, "code": code}], "text": display},
        "effectiveDateTime": "2026-10-24T19:34:00-04:00",
        **extra,
    }


BUNDLE = {
    "resourceType": "Bundle",
    "entry": [{"resource": r} for r in [
        {
            "resourceType": "Patient",
            "id": PID,
            "name": [{"use": "official", "family": "Lopez123", "given": ["Maria45"]}],
            "gender": "female",
            "birthDate": "1968-03-02",
        },
        {
            "resourceType": "Condition",
            "id": "c-1",
            "clinicalStatus": {"coding": [{"code": "active"}]},
            "code": {
                "coding": [{"system": "http://snomed.info/sct", "code": "44054006"}],
                "text": "Diabetes mellitus type 2 (disorder)",
            },
            "onsetDateTime": "2016-05-01T10:00:00-04:00",
        },
        {
            "resourceType": "MedicationRequest",
            "id": "m-inline",
            "status": "active",
            "medicationCodeableConcept": {
                "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "860975"}],
                "text": "Metformin 500 MG",
            },
            "authoredOn": "2020-01-01T09:00:00-05:00",
            "requester": {"display": "Dr. Ann12 Chen34"},
        },
        {
            "resourceType": "MedicationRequest",
            "id": "m-ref",
            "status": "active",
            "medicationReference": {"reference": "urn:uuid:med-1"},
        },
        {
            "resourceType": "Medication",
            "id": "med-1",
            "code": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "1"}],
                     "text": "Insulin glargine"},
        },
        obs("o-a1c", "4548-4", "HbA1c", valueQuantity=quantity(7.6, "%")),
        obs("o-glu", "2339-0", "Glucose", valueQuantity=quantity(177.0, "mg/dL")),
        obs("o-bp", "85354-9", "BP panel", component=[
            {"code": {"coding": [{"system": LOINC, "code": "8480-6"}], "text": "Systolic"},
             "valueQuantity": quantity(134, "mm[Hg]")},
            {"code": {"coding": [{"system": LOINC, "code": "8462-4"}], "text": "Diastolic"},
             "valueQuantity": quantity(84, "mm[Hg]")},
        ]),
    ]],
}


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_patient_name_digits_stripped(session):
    load_bundle(session, BUNDLE)
    p = session.get(Patient, PID)
    assert (p.first_name, p.last_name) == ("Maria", "Lopez")
    assert p.birth_date == date(1968, 3, 2)


def test_condition_loaded(session):
    load_bundle(session, BUNDLE)
    c = session.get(Condition, "c-1")
    assert c.snomed_code == "44054006"
    assert c.clinical_status == "active"


def test_medications_resolve_inline_and_reference(session):
    load_bundle(session, BUNDLE)
    assert session.get(Medication, "m-inline").name == "Metformin 500 MG"
    assert session.get(Medication, "m-inline").prescriber == "Dr. Ann Chen"
    assert session.get(Medication, "m-ref").name == "Insulin glargine"


def test_glucose_goes_to_glucose_readings_with_local_time(session):
    load_bundle(session, BUNDLE)
    g = session.scalars(select(GlucoseReading)).one()
    assert g.value_mg_dl == 177.0
    assert g.source == "fhir"
    # local clock time kept, offset dropped
    assert g.measured_at == datetime(2026, 10, 24, 19, 34)
    assert session.scalars(select(Observation).where(Observation.loinc_code == "2339-0")).first() is None


def test_bp_panel_split_into_systolic_and_diastolic(session):
    load_bundle(session, BUNDLE)
    bp = {o.loinc_code: o.value for o in session.scalars(
        select(Observation).where(Observation.fhir_id == "o-bp"))}
    assert bp == {"8480-6": 134, "8462-4": 84}


def test_reload_skips_existing_patient(session):
    assert load_bundle(session, BUNDLE) is True
    session.commit()
    assert load_bundle(session, BUNDLE) is False
    assert session.query(Observation).count() == 3  # HbA1c + systolic + diastolic
