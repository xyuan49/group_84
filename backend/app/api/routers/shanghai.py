from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import GlucoseReading, Meal

router = APIRouter(
    prefix="/patients/{patient_id}/shanghai",
    tags=["Shanghai CGM"],
)


@router.get("/glucose")
def get_shanghai_glucose(
    patient_id: str,
    db: Session = Depends(get_db),
):
    return (
        db.query(GlucoseReading)
        .filter(
            GlucoseReading.patient_id == patient_id,
            GlucoseReading.source == "cgm",
        )
        .order_by(GlucoseReading.measured_at.desc())
        .all()
    )


@router.get("/meals")
def get_shanghai_meals(
    patient_id: str,
    db: Session = Depends(get_db),
):
    return (
        db.query(Meal)
        .filter(
            Meal.patient_id == patient_id,
            Meal.source == "cgm",
        )
        .order_by(Meal.eaten_at.desc())
        .all()
    )