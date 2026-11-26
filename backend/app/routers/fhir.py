"""FHIR R4 Observation API over GlucoTrack's glucose readings, labs and vitals.

    GET  /fhir/Observation?patient=<id>[&code=<loinc>][&_count=<n>]  -> searchset Bundle
    GET  /fhir/Observation/<id>                                      -> Observation
    POST /fhir/Observation                                           -> 201 + Observation

Glucose readings become LOINC 2339-0 Observations in mg/dL whatever their
source; their ids start with `glucose-`. Labs and vitals from the
`observations` table (HbA1c, BMI, blood pressure) keep their own LOINC code
and unit; their ids start with `obs-`. Every resource carries a `meta.tag`
naming its data source, and readings from the UCI and Shanghai datasets also
say they were paired with a synthetic patient for demonstration.

POST accepts one glucose Observation (LOINC 2339-0 or 2345-7) in mg/dL or
mmol/L; mmol/L is converted to mg/dL. It is stored as a patient entry
(source `user`), so it shows up in /api/patients/{id}/glucose too.

The database keeps local clock time. FHIR needs a UTC offset on a dateTime
with a time, so output times get the offset of GLUCOTRACK_TIMEZONE
(default America/New_York; Synthea's default population is Massachusetts).
"""

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import GlucoseReading, Observation, Patient

router = APIRouter(prefix="/fhir", tags=["FHIR R4"])

FHIR_JSON = "application/fhir+json"
LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"
CATEGORY_SYSTEM = "http://terminology.hl7.org/CodeSystem/observation-category"
SOURCE_SYSTEM = "urn:glucotrack:data-source"

GLUCOSE_CODE = "2339-0"
GLUCOSE_DISPLAY = "Glucose [Mass/volume] in Blood"
ACCEPTED_GLUCOSE_CODES = {"2339-0", "2345-7"}
MMOL_TO_MG_DL = 18.016  # molar mass of glucose 180.16 g/mol / 10

SOURCES = {
    "fhir": "Synthea synthetic EHR (FHIR lab result)",
    "user": "Entered by the patient in GlucoTrack",
    "uci": "UCI Diabetes dataset, paired with a synthetic patient for demonstration",
    "cgm": "Shanghai T2DM CGM dataset, paired with a synthetic patient for demonstration",
}

VITAL_SIGNS = {"39156-5", "8480-6", "8462-4"}  # BMI, systolic, diastolic


def local_zone() -> ZoneInfo:
    return ZoneInfo(os.environ.get("GLUCOTRACK_TIMEZONE", "America/New_York"))


def fhir_datetime(value: datetime) -> str:
    return value.replace(tzinfo=local_zone()).isoformat()


def to_local(value: datetime) -> datetime:
    """A FHIR dateTime as local clock time, the way the database stores it."""
    if value.tzinfo is None:
        return value
    return value.astimezone(local_zone()).replace(tzinfo=None)


def fhir_response(body: dict, status_code: int = 200, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(body, status_code=status_code, media_type=FHIR_JSON, headers=headers)


def outcome(status_code: int, code: str, message: str) -> JSONResponse:
    """FHIR OperationOutcome error response."""
    return fhir_response(
        {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "code": code, "diagnostics": message}],
        },
        status_code,
    )


def category(code: str, display: str) -> list[dict]:
    return [{"coding": [{"system": CATEGORY_SYSTEM, "code": code, "display": display}]}]


def source_meta(source: str) -> dict:
    return {"tag": [{"system": SOURCE_SYSTEM, "code": source, "display": SOURCES.get(source, source)}]}


def glucose_resource(r: GlucoseReading) -> dict:
    resource = {
        "resourceType": "Observation",
        "id": f"glucose-{r.id}",
        "meta": source_meta(r.source),
        "status": "final",
        "category": category("laboratory", "Laboratory"),
        "code": {
            "coding": [{"system": LOINC, "code": GLUCOSE_CODE, "display": GLUCOSE_DISPLAY}],
            "text": "Glucose",
        },
        "subject": {"reference": f"Patient/{r.patient_id}"},
        "effectiveDateTime": fhir_datetime(r.measured_at),
        "valueQuantity": {"value": r.value_mg_dl, "unit": "mg/dL", "system": UCUM, "code": "mg/dL"},
    }
    if r.meal_context:
        resource["note"] = [{"text": f"Meal context: {r.meal_context.replace('_', ' ')}"}]
    return resource


def observation_resource(o: Observation) -> dict:
    vital = o.loinc_code in VITAL_SIGNS
    quantity = {"value": o.value, "system": UCUM}
    if o.unit:
        quantity.update(unit=o.unit, code=o.unit)
    return {
        "resourceType": "Observation",
        "id": f"obs-{o.id}",
        "meta": source_meta("fhir"),
        "status": "final",
        "category": category("vital-signs", "Vital Signs") if vital else category("laboratory", "Laboratory"),
        "code": {"coding": [{"system": LOINC, "code": o.loinc_code, "display": o.display}], "text": o.display},
        "subject": {"reference": f"Patient/{o.patient_id}"},
        "effectiveDateTime": fhir_datetime(o.effective_at),
        "valueQuantity": quantity,
    }


def parse_codes(code: str | None) -> set[str] | None:
    """FHIR token search: `4548-4`, `http://loinc.org|4548-4`, comma-separated for OR."""
    if not code:
        return None
    codes = set()
    for token in code.split(","):
        system, _, value = token.strip().rpartition("|")
        if system and system != LOINC:
            continue  # only LOINC codes exist here
        codes.add(value)
    return codes


def patient_id_from_reference(reference: str | None) -> str | None:
    """`Patient/<id>` or an absolute URL ending in `/Patient/<id>`."""
    parts = (reference or "").rstrip("/").split("/")
    if len(parts) >= 2 and parts[-2] == "Patient" and parts[-1]:
        return parts[-1]
    return None


@router.get("/Observation", summary="Search Observations (searchset Bundle)")
def search_observations(
    request: Request,
    patient: str = Query(..., description="Patient id, or Patient/<id>"),
    code: str | None = Query(None, description="LOINC code(s), e.g. 2339-0 or http://loinc.org|4548-4,39156-5"),
    count: int = Query(100, alias="_count", ge=1, le=1000, description="Maximum entries, newest first"),
    db: Session = Depends(get_db),
):
    pid = patient.removeprefix("Patient/")
    if db.get(Patient, pid) is None:
        return outcome(404, "not-found", f"Patient/{pid} not found")

    codes = parse_codes(code)
    want_glucose = codes is None or bool(codes & ACCEPTED_GLUCOSE_CODES)
    other_codes = None if codes is None else codes - ACCEPTED_GLUCOSE_CODES

    resources: list[tuple[datetime, dict]] = []
    total = 0
    if want_glucose:
        where = GlucoseReading.patient_id == pid
        total += db.scalar(select(func.count()).where(where))
        rows = db.scalars(
            select(GlucoseReading).where(where).order_by(GlucoseReading.measured_at.desc()).limit(count)
        )
        resources += [(r.measured_at, glucose_resource(r)) for r in rows]
    if other_codes is None or other_codes:
        where = [Observation.patient_id == pid]
        if other_codes:
            where.append(Observation.loinc_code.in_(other_codes))
        total += db.scalar(select(func.count()).where(*where))
        rows = db.scalars(select(Observation).where(*where).order_by(Observation.effective_at.desc()).limit(count))
        resources += [(o.effective_at, observation_resource(o)) for o in rows]

    resources.sort(key=lambda pair: pair[0], reverse=True)
    base = str(request.base_url).rstrip("/")
    return fhir_response({
        "resourceType": "Bundle",
        "type": "searchset",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "link": [{"relation": "self", "url": str(request.url)}],
        "entry": [
            {"fullUrl": f"{base}/fhir/Observation/{res['id']}", "resource": res, "search": {"mode": "match"}}
            for _, res in resources[:count]
        ],
    })


@router.get("/Observation/{observation_id}", summary="Read one Observation")
def read_observation(observation_id: str, db: Session = Depends(get_db)):
    kind, _, number = observation_id.partition("-")
    row = None
    if number.isdigit():
        if kind == "glucose":
            row = db.get(GlucoseReading, int(number))
        elif kind == "obs":
            row = db.get(Observation, int(number))
    if row is None:
        return outcome(404, "not-found", f"Observation/{observation_id} not found")
    return fhir_response(glucose_resource(row) if kind == "glucose" else observation_resource(row))


@router.post("/Observation", status_code=201, summary="Create a glucose Observation")
async def create_observation(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
    except ValueError:
        return outcome(400, "structure", "Body must be a JSON FHIR Observation")
    if not isinstance(body, dict) or body.get("resourceType") != "Observation":
        return outcome(400, "structure", "resourceType must be Observation")

    codings = (body.get("code") or {}).get("coding") or []
    if not any(c.get("system") == LOINC and c.get("code") in ACCEPTED_GLUCOSE_CODES for c in codings):
        return outcome(422, "not-supported", "Only glucose Observations (LOINC 2339-0 or 2345-7) can be created")

    pid = patient_id_from_reference((body.get("subject") or {}).get("reference"))
    if pid is None:
        return outcome(422, "required", "subject.reference must be Patient/<id>")
    if db.get(Patient, pid) is None:
        return outcome(422, "not-found", f"Patient/{pid} not found")

    try:
        measured_at = to_local(datetime.fromisoformat(body["effectiveDateTime"]))
    except (KeyError, TypeError, ValueError):
        return outcome(422, "required", "effectiveDateTime must be a FHIR dateTime")

    quantity = body.get("valueQuantity") or {}
    value = quantity.get("value")
    unit = quantity.get("code") or quantity.get("unit")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return outcome(422, "required", "valueQuantity.value must be a number")
    if unit == "mmol/L":
        value = round(value * MMOL_TO_MG_DL, 1)
    elif unit != "mg/dL":
        return outcome(422, "value", "valueQuantity unit must be mg/dL or mmol/L")
    if not 20 <= value <= 600:
        return outcome(422, "value", "Glucose must be 20-600 mg/dL (1.1-33.3 mmol/L)")

    reading = GlucoseReading(patient_id=pid, value_mg_dl=value, measured_at=measured_at, source="user")
    db.add(reading)
    db.commit()
    db.refresh(reading)
    resource = glucose_resource(reading)
    return fhir_response(resource, 201, headers={"Location": f"/fhir/Observation/{resource['id']}"})
