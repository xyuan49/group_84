from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    GlucoseReading,
    InsulinDose,
    Meal,
)

router = APIRouter(
    prefix="/patients/{patient_id}/uci",
    tags=["UCI Diabetes"],
)


@router.get("/glucose")
def get_uci_glucose(
    patient_id: str,
    db: Session = Depends(get_db),
):
    return (
        db.query(GlucoseReading)
        .filter(
            GlucoseReading.patient_id == patient_id,
            GlucoseReading.source == "uci",
        )
        .order_by(GlucoseReading.measured_at.desc())
        .all()
    )


@router.get("/insulin")
def get_uci_insulin(
    patient_id: str,
    db: Session = Depends(get_db),
):
    return (
        db.query(InsulinDose)
        .filter(InsulinDose.patient_id == patient_id)
        .order_by(InsulinDose.administered_at.desc())
        .all()
    )


@router.get("/meals")
def get_uci_meals(
    patient_id: str,
    db: Session = Depends(get_db),
):
    return (
        db.query(Meal)
        .filter(
            Meal.patient_id == patient_id,
            Meal.source == "uci",
        )
        .order_by(Meal.eaten_at.desc())
        .all()
    )