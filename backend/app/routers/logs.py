"""Glucose readings, insulin doses and meals, from every source.

Sources: `fhir` (Synthea lab glucose), `uci` (UCI dataset), `cgm` (Shanghai
CGM dataset) and `user` (patient entries, once the logging endpoints exist).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import GlucoseReading, InsulinDose, Meal, Patient
from app.routers.patients import get_patient
from app.routers.timeseries import time_window
from app.schemas import GlucoseOut, GlucoseSource, InsulinOut, LogSource, MealOut

router = APIRouter(prefix="/api/patients/{patient_id}", tags=["glucose, insulin, meals"])

DAYS = Query(None, ge=1, le=3650, description="Last N days, ending at the patient's latest record")


@router.get("/glucose", response_model=list[GlucoseOut])
def list_glucose(
    source: list[GlucoseSource] | None = Query(None, description="Repeatable: fhir, uci, cgm, user"),
    start: datetime | None = None,
    end: datetime | None = None,
    days: int | None = DAYS,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
):
    """All glucose readings in one history, oldest first.

    CGM patients have a reading every 15 minutes (~1,300 per 14 days), so
    pass `days` or `start`/`end` for charts.
    """
    stmt = select(GlucoseReading).where(GlucoseReading.patient_id == patient.id)
    if source:
        stmt = stmt.where(GlucoseReading.source.in_(source))
    stmt = time_window(db, stmt, GlucoseReading.measured_at, start, end, days)
    return db.scalars(stmt.order_by(GlucoseReading.measured_at, GlucoseReading.id)).all()


@router.get("/insulin", response_model=list[InsulinOut])
def list_insulin(
    source: list[LogSource] | None = Query(None, description="Repeatable: uci, user"),
    start: datetime | None = None,
    end: datetime | None = None,
    days: int | None = DAYS,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
):
    """Insulin doses, oldest first. Only insulin-treated patients (UCI data) have any."""
    stmt = select(InsulinDose).where(InsulinDose.patient_id == patient.id)
    if source:
        stmt = stmt.where(InsulinDose.source.in_(source))
    stmt = time_window(db, stmt, InsulinDose.administered_at, start, end, days)
    return db.scalars(stmt.order_by(InsulinDose.administered_at, InsulinDose.id)).all()


@router.get("/meals", response_model=list[MealOut])
def list_meals(
    source: list[LogSource] | None = Query(None, description="Repeatable: uci, cgm, user"),
    start: datetime | None = None,
    end: datetime | None = None,
    days: int | None = DAYS,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
):
    """Meals, oldest first."""
    stmt = select(Meal).where(Meal.patient_id == patient.id)
    if source:
        stmt = stmt.where(Meal.source.in_(source))
    stmt = time_window(db, stmt, Meal.eaten_at, start, end, days)
    return db.scalars(stmt.order_by(Meal.eaten_at, Meal.id)).all()
