from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.models import Message
from app.api.hello_world_utils import hello_world

from app.api.routers.shanghai import router as shanghai_router
from app.api.routers.uci import router as uci_router
from app.api.routers.stanford import router as stanford_router

from app.db import get_db
from app.models import (
    Patient,
    GlucoseReading,
    Condition,
    Medication,
    Observation,
)

app = FastAPI(
    title="Bio informatics",
    description="project backend",
    version="0.0.1"
)
app.include_router(shanghai_router)
app.include_router(uci_router)
app.include_router(stanford_router)


@app.get(
    "/",
    response_model=Message,
    summary="Hello World",
    description="Returns a hello world message.",
)
def get_hello_world():
    return hello_world()


@app.get("/patients")
def get_patients(db: Session = Depends(get_db)):
    patients = db.query(Patient).all()

    return [
        {
            "id": p.id,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "gender": p.gender,
            "birth_date": p.birth_date,
        }
        for p in patients
    ]


@app.get("/patients/{patient_id}")
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
):
    patient = db.get(Patient, patient_id)

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )

    return {
        "id": patient.id,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "gender": patient.gender,
        "birth_date": patient.birth_date,
        "source": patient.source,
    }


@app.get("/patients/{patient_id}/conditions")
def get_conditions(
    patient_id: str,
    db: Session = Depends(get_db),
):
    return (
        db.query(Condition)
        .filter(Condition.patient_id == patient_id)
        .all()
    )


@app.get("/patients/{patient_id}/medications")
def get_medications(
    patient_id: str,
    db: Session = Depends(get_db),
):
    return (
        db.query(Medication)
        .filter(Medication.patient_id == patient_id)
        .all()
    )


@app.get("/patients/{patient_id}/observations")
def get_observations(
    patient_id: str,
    db: Session = Depends(get_db),
):
    return (
        db.query(Observation)
        .filter(Observation.patient_id == patient_id)
        .order_by(Observation.effective_at.desc())
        .all()
    )


@app.get("/patients/{patient_id}/glucose")
def get_glucose_readings(
    patient_id: str,
    db: Session = Depends(get_db),
):
    return (
        db.query(GlucoseReading)
        .filter(GlucoseReading.patient_id == patient_id)
        .order_by(GlucoseReading.measured_at.desc())
        .all()
    )


@app.get("/patients/{patient_id}/glucose/latest")
def get_latest_glucose(
    patient_id: str,
    db: Session = Depends(get_db),
):
    reading = (
        db.query(GlucoseReading)
        .filter(GlucoseReading.patient_id == patient_id)
        .order_by(GlucoseReading.measured_at.desc())
        .first()
    )

    if not reading:
        raise HTTPException(
            status_code=404,
            detail="No glucose readings found",
        )

    return reading


@app.get("/patients/{patient_id}/summary")
def get_patient_summary(
    patient_id: str,
    db: Session = Depends(get_db),
):
    patient = db.get(Patient, patient_id)

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )

    latest_glucose = (
        db.query(GlucoseReading)
        .filter(GlucoseReading.patient_id == patient_id)
        .order_by(GlucoseReading.measured_at.desc())
        .first()
    )

    return {
        "patient": {
            "id": patient.id,
            "name": f"{patient.first_name} {patient.last_name}",
        },
        "conditions": len(patient.conditions),
        "medications": len(patient.medications),
        "observations": len(patient.observations),
        "glucose_readings": len(patient.glucose_readings),
        "latest_glucose": (
            latest_glucose.value_mg_dl
            if latest_glucose
            else None
        ),
    }