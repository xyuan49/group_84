"""Rule-based alerts: glucose lows and highs, fasting, HbA1c and blood pressure.

The rules and thresholds live in app/alerts.py.
"""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import alerts as rules
from app.db import get_db
from app.models import GlucoseReading, Observation, Patient
from app.routers.patients import get_patient
from app.routers.timeseries import time_window
from app.schemas import AlertsOut

router = APIRouter(prefix="/api/patients/{patient_id}", tags=["alerts"])

HBA1C, SYSTOLIC, DIASTOLIC = "4548-4", "8480-6", "8462-4"


def latest(db: Session, patient_id: str, code: str, at=None) -> tuple | None:
    stmt = select(Observation.effective_at, Observation.value).where(
        Observation.patient_id == patient_id, Observation.loinc_code == code)
    if at is not None:
        stmt = stmt.where(Observation.effective_at == at)
    row = db.execute(stmt.order_by(Observation.effective_at.desc()).limit(1)).first()
    return tuple(row) if row else None


@router.get("/alerts", response_model=AlertsOut)
def list_alerts(
    days: int = Query(7, ge=1, le=90, description="Glucose window: last N days, ending at the latest reading"),
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
):
    """Alerts for one patient, most severe first.

    Glucose rules look at the last `days` days of readings from every source.
    HbA1c and blood pressure rules use the latest results on record.
    """
    stmt = select(GlucoseReading).where(GlucoseReading.patient_id == patient.id)
    stmt = time_window(db, stmt, GlucoseReading.measured_at, None, None, days)
    glucose = db.scalars(stmt).all()
    readings = [rules.Reading(g.value_mg_dl, g.measured_at, g.meal_context) for g in glucose]

    hba1c = db.execute(
        select(Observation.effective_at, Observation.value)
        .where(Observation.patient_id == patient.id, Observation.loinc_code == HBA1C)
    ).all()
    systolic = latest(db, patient.id, SYSTOLIC)
    diastolic = latest(db, patient.id, DIASTOLIC, at=systolic[0]) if systolic else None

    found = (
        rules.glucose_alerts(readings, days)
        + rules.hba1c_alerts([tuple(r) for r in hba1c])
        + rules.bp_alerts(systolic, diastolic)
    )
    return {
        "days": days,
        "window_start": min((r.at for r in readings), default=None),
        "window_end": max((r.at for r in readings), default=None),
        "alerts": [asdict(a) for a in rules.sort_alerts(found)],
    }
