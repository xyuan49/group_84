"""Patient endpoints. Use this file as the pattern for new routers:

- `router = APIRouter(prefix=..., tags=[...])`, then include it in app/main.py
- get a database session with `db: Session = Depends(get_db)`
- declare `response_model=` with a model from app/schemas.py
- per-patient routes take `patient: Patient = Depends(get_patient)` for the 404
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Patient
from app.schemas import PatientOut

router = APIRouter(prefix="/api/patients", tags=["patients"])


def get_patient(patient_id: str, db: Session = Depends(get_db)) -> Patient:
    """Dependency for /api/patients/{patient_id}/... routes: the patient, or 404."""
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("", response_model=list[PatientOut])
def list_patients(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Patient).order_by(Patient.last_name, Patient.first_name).limit(limit).offset(offset)
    return db.scalars(stmt).all()


@router.get("/{patient_id}", response_model=PatientOut)
def read_patient(patient: Patient = Depends(get_patient)):
    return patient
