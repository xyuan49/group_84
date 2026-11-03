"""Load filtered Synthea FHIR R4 bundles into the GlucoTrack database.

Expects the output of scripts/filter_synthea.py (one bundle per patient).
Patients already in the database are skipped, so the loader is safe to re-run.

Usage (from backend/):
    python -m app.loaders.synthea ../data/synthea_t2d
"""

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import Condition, GlucoseReading, Medication, Observation, Patient

GLUCOSE_LOINC = {"2339-0", "2345-7"}
OBSERVATION_LOINC = {"4548-4", "39156-5"}  # HbA1c, BMI
BP_PANEL_LOINC = "85354-9"
BP_COMPONENT_LOINC = {"8480-6", "8462-4"}  # systolic, diastolic


def strip_digits(text):
    """Synthea appends numbers to names ("Abe604 Gaylord332"); drop them."""
    return re.sub(r"\d+", "", text).strip()


def parse_datetime(value):
    """FHIR dateTime -> naive local datetime (offset dropped, clock time kept)."""
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=None)


def coding(concept, system_substring):
    """First coding in a CodeableConcept whose system contains system_substring."""
    for c in (concept or {}).get("coding", []):
        if system_substring in c.get("system", ""):
            return c
    return {}


def concept_text(concept):
    concept = concept or {}
    return concept.get("text") or coding(concept, "").get("display", "")


def to_patient(r):
    name = next(
        (n for n in r.get("name", []) if n.get("use") == "official"),
        (r.get("name") or [{}])[0],
    )
    return Patient(
        id=r["id"],
        first_name=strip_digits(" ".join(name.get("given", []))),
        last_name=strip_digits(name.get("family", "")),
        gender=r.get("gender"),
        birth_date=date.fromisoformat(r["birthDate"]) if r.get("birthDate") else None,
        source="synthea",
    )


def to_condition(r, patient_id):
    return Condition(
        id=r["id"],
        patient_id=patient_id,
        snomed_code=coding(r.get("code"), "snomed").get("code", ""),
        display=concept_text(r.get("code")),
        clinical_status=coding(r.get("clinicalStatus"), "").get("code"),
        onset_at=parse_datetime(r.get("onsetDateTime")),
        abatement_at=parse_datetime(r.get("abatementDateTime")),
    )


def to_medication(r, patient_id, medications_by_ref):
    concept = r.get("medicationCodeableConcept")
    if concept is None:
        ref = r.get("medicationReference", {}).get("reference")
        concept = medications_by_ref.get(ref, {}).get("code", {})
    prescriber = r.get("requester", {}).get("display")
    return Medication(
        id=r["id"],
        patient_id=patient_id,
        rxnorm_code=coding(concept, "rxnorm").get("code"),
        name=concept_text(concept) or "Unknown medication",
        status=r.get("status", "unknown"),
        authored_on=parse_datetime(r.get("authoredOn")),
        prescriber=strip_digits(prescriber) if prescriber else None,
    )


def to_rows_for_observation(r, patient_id):
    """One FHIR Observation -> zero or more Observation/GlucoseReading rows."""
    loinc = coding(r.get("code"), "loinc").get("code")
    effective_at = parse_datetime(r.get("effectiveDateTime"))
    if effective_at is None:
        return []

    if loinc in GLUCOSE_LOINC:
        return [GlucoseReading(
            patient_id=patient_id,
            value_mg_dl=r["valueQuantity"]["value"],
            measured_at=effective_at,
            meal_context=None,
            source="fhir",
            fhir_id=r["id"],
        )]

    if loinc in OBSERVATION_LOINC:
        q = r["valueQuantity"]
        return [Observation(
            fhir_id=r["id"],
            patient_id=patient_id,
            loinc_code=loinc,
            display=concept_text(r.get("code")),
            value=q["value"],
            unit=q.get("unit"),
            effective_at=effective_at,
        )]

    if loinc == BP_PANEL_LOINC:
        rows = []
        for comp in r.get("component", []):
            comp_loinc = coding(comp.get("code"), "loinc").get("code")
            if comp_loinc in BP_COMPONENT_LOINC and "valueQuantity" in comp:
                rows.append(Observation(
                    fhir_id=r["id"],
                    patient_id=patient_id,
                    loinc_code=comp_loinc,
                    display=concept_text(comp.get("code")),
                    value=comp["valueQuantity"]["value"],
                    unit=comp["valueQuantity"].get("unit"),
                    effective_at=effective_at,
                ))
        return rows

    return []


def load_bundle(session: Session, bundle: dict) -> bool:
    """Add one patient's bundle to the session. Returns False if already loaded."""
    resources = [e["resource"] for e in bundle.get("entry", [])]
    patient_res = next(r for r in resources if r["resourceType"] == "Patient")
    if session.get(Patient, patient_res["id"]) is not None:
        return False

    patient = to_patient(patient_res)
    medications_by_ref = {
        f"urn:uuid:{r['id']}": r for r in resources if r["resourceType"] == "Medication"
    }

    rows = [patient]
    for r in resources:
        rtype = r["resourceType"]
        if rtype == "Condition":
            rows.append(to_condition(r, patient.id))
        elif rtype == "MedicationRequest":
            rows.append(to_medication(r, patient.id, medications_by_ref))
        elif rtype == "Observation":
            rows.extend(to_rows_for_observation(r, patient.id))

    session.add_all(rows)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input_dir", type=Path, help="directory of filtered bundles")
    args = parser.parse_args()

    paths = sorted(args.input_dir.glob("*.json"))
    if not paths:
        raise SystemExit(f"No bundles found in {args.input_dir}")

    Base.metadata.create_all(engine)
    loaded = skipped = 0
    with SessionLocal() as session:
        for path in paths:
            with path.open(encoding="utf-8") as f:
                bundle = json.load(f)
            if load_bundle(session, bundle):
                loaded += 1
            else:
                skipped += 1
        session.commit()

    print(f"Loaded {loaded} patients, skipped {skipped} already in the database.")


if __name__ == "__main__":
    main()
