"""Clinical record from Synthea (FHIR): conditions, medications, labs and vitals."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Condition, Medication, Observation, Patient
from app.routers.patients import get_patient
from app.routers.timeseries import time_window
from app.schemas import ConditionOut, MedicationOut, ObservationOut

router = APIRouter(prefix="/api/patients/{patient_id}", tags=["clinical record"])


@router.get("/conditions", response_model=list[ConditionOut])
def list_conditions(
    status: str | None = Query(None, description="active or resolved"),
    disorders_only: bool = Query(False, description="Keep '(disorder)' entries; hide social findings"),
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
):
    """Newest onset first."""
    stmt = select(Condition).where(Condition.patient_id == patient.id)
    if status:
        stmt = stmt.where(Condition.clinical_status == status)
    if disorders_only:
        stmt = stmt.where(Condition.display.like("%(disorder)%"))
    return db.scalars(stmt.order_by(Condition.onset_at.desc(), Condition.id)).all()


@router.get("/medications", response_model=list[MedicationOut])
def list_medications(
    status: str | None = Query(None, description="active, completed or stopped"),
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
):
    """Newest prescription first."""
    stmt = select(Medication).where(Medication.patient_id == patient.id)
    if status:
        stmt = stmt.where(Medication.status == status)
    return db.scalars(stmt.order_by(Medication.authored_on.desc(), Medication.id)).all()


@router.get("/observations", response_model=list[ObservationOut])
def list_observations(
    code: list[str] | None = Query(
        None, description="LOINC, repeatable: 4548-4 HbA1c, 39156-5 BMI, 8480-6 systolic, 8462-4 diastolic"),
    start: datetime | None = None,
    end: datetime | None = None,
    days: int | None = Query(None, ge=1, le=3650, description="Last N days, ending at the latest matching value"),
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
):
    """Oldest first, ready to plot."""
    stmt = select(Observation).where(Observation.patient_id == patient.id)
    if code:
        stmt = stmt.where(Observation.loinc_code.in_(code))
    stmt = time_window(db, stmt, Observation.effective_at, start, end, days)
    return db.scalars(stmt.order_by(Observation.effective_at, Observation.loinc_code)).all()
