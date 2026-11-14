"""Load the UCI (AIM-94) diabetes dataset onto insulin-treated Synthea patients.

Synthea only records glucose at clinic visits (a few readings a year), which
is too sparse for the 14-day glucose chart and the insulin chart. The UCI
dataset has weeks to months of self-monitored glucose, insulin doses and meal
events for 70 patients. Each selected UCI series is attached to one Synthea
patient who has an insulin prescription, and its dates are shifted so the
series ends on the anchor date (time of day is kept).

The UCI patients are insulin-treated (mostly Type 1), so the series are only
attached to Synthea patients who are on insulin.

Usage (from backend/, after the Synthea loader):
    python -m app.loaders.uci ../data/uci_raw/Diabetes-Data
"""

import argparse
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import GlucoseReading, InsulinDose, Meal, Medication

# Synthea reference date (-r 20261101), so UCI series end with the Synthea records.
DEFAULT_ANCHOR = date(2026, 11, 1)
FILE_PATTERN = re.compile(r"data-\d{2}")  # exact match; skips Data-Codes on case-insensitive filesystems

# UCI codes -> GlucoTrack fields (see Data-Codes in the dataset).
INSULIN_TYPES = {33: "short", 34: "intermediate", 35: "long"}  # Regular, NPH, UltraLente
GLUCOSE_CONTEXT = {
    48: None,
    57: None,
    58: "fasting",  # pre-breakfast
    59: "after_meal",
    60: "before_meal",
    61: "after_meal",
    62: "before_meal",
    63: "after_meal",
    64: "before_meal",  # pre-snack
}
MEAL_DESCRIPTIONS = {66: "Typical meal", 67: "Larger than usual meal", 68: "Smaller than usual meal"}
# 65 hypoglycemic symptoms, 69-71 exercise, 72 special event: no table for these yet.
NOT_STORED = {65, 69, 70, 71, 72}

# Paper records were given these fixed times; device records have real ones.
PAPER_TIMES = {"8:00", "08:00", "12:00", "18:00", "22:00"}


# --- Pydantic models for incoming records ----------------------------------


class UciRecord(BaseModel):
    """One raw line: date, time, code, value (tab-separated)."""

    timestamp: datetime
    code: int
    value: float

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v):
        if isinstance(v, str):
            return datetime.strptime(v, "%m-%d-%Y %H:%M")
        return v

    @classmethod
    def from_line(cls, line: str) -> "UciRecord":
        parts = line.rstrip("\r\n").split("\t")
        if len(parts) != 4:
            raise ValueError(f"expected 4 tab-separated fields, got {len(parts)}")
        day, time, code, value = parts
        return cls(timestamp=f"{day} {time}", code=code, value=value)


class UciGlucose(BaseModel):
    measured_at: datetime
    # Home meters of the era read roughly 20-600 mg/dL; outside that is an entry error.
    value_mg_dl: float = Field(ge=20, le=600)
    meal_context: Literal["fasting", "before_meal", "after_meal"] | None


class UciInsulin(BaseModel):
    administered_at: datetime
    units: float = Field(gt=0, le=100)  # 0 and >100 units are entry errors in this dataset
    insulin_type: Literal["short", "intermediate", "long"]


class UciMeal(BaseModel):
    eaten_at: datetime
    description: str


@dataclass
class UciSeries:
    name: str
    glucose: list[UciGlucose] = field(default_factory=list)
    insulin: list[UciInsulin] = field(default_factory=list)
    meals: list[UciMeal] = field(default_factory=list)
    skipped: Counter = field(default_factory=Counter)
    paper_records: int = 0
    total_records: int = 0

    @property
    def timestamps(self):
        return (
            [g.measured_at for g in self.glucose]
            + [i.administered_at for i in self.insulin]
            + [m.eaten_at for m in self.meals]
        )

    @property
    def days_covered(self) -> int:
        return len({t.date() for t in self.timestamps})

    @property
    def device_fraction(self) -> float:
        return 1 - self.paper_records / self.total_records if self.total_records else 0.0


def parse_series(name: str, lines) -> UciSeries:
    series = UciSeries(name=name)
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = UciRecord.from_line(line)
        except (ValueError, ValidationError):
            series.skipped["malformed line"] += 1
            continue

        series.total_records += 1
        if line.split("\t")[1] in PAPER_TIMES:
            series.paper_records += 1

        try:
            if rec.code in GLUCOSE_CONTEXT:
                series.glucose.append(UciGlucose(
                    measured_at=rec.timestamp, value_mg_dl=rec.value, meal_context=GLUCOSE_CONTEXT[rec.code]))
            elif rec.code in INSULIN_TYPES:
                series.insulin.append(UciInsulin(
                    administered_at=rec.timestamp, units=rec.value, insulin_type=INSULIN_TYPES[rec.code]))
            elif rec.code in MEAL_DESCRIPTIONS:
                series.meals.append(UciMeal(eaten_at=rec.timestamp, description=MEAL_DESCRIPTIONS[rec.code]))
            elif rec.code in NOT_STORED:
                series.skipped["not stored (symptom/exercise/event)"] += 1
            else:
                series.skipped["unknown code"] += 1
        except ValidationError:
            series.skipped["value out of range"] += 1
    return series


def read_series(raw_dir: Path) -> list[UciSeries]:
    paths = sorted(p for p in raw_dir.iterdir() if FILE_PATTERN.fullmatch(p.name))
    series = []
    for p in paths:
        with p.open(encoding="ascii", errors="replace") as f:
            series.append(parse_series(p.name, f))
    return series


def select_series(series: list[UciSeries], min_days: int = 14, min_device_fraction: float = 0.8):
    """Series with real device timestamps and at least two weeks of data, in file order."""
    return [s for s in series if s.days_covered >= min_days and s.device_fraction >= min_device_fraction]


def insulin_patient_ids(session: Session) -> list[str]:
    return list(session.scalars(
        select(Medication.patient_id)
        .where(func.lower(Medication.name).like("%insulin%"))
        .distinct()
        .order_by(Medication.patient_id)
    ))


def load_series(session: Session, series: UciSeries, patient_id: str, anchor: date) -> bool:
    """Attach one series to a patient, shifted to end on `anchor`. False if already loaded."""
    already = session.scalars(
        select(GlucoseReading.id).where(GlucoseReading.patient_id == patient_id, GlucoseReading.source == "uci")
    ).first()
    if already is not None:
        return False

    shift = timedelta(days=(anchor - max(series.timestamps).date()).days)
    session.add_all(
        [GlucoseReading(patient_id=patient_id, value_mg_dl=g.value_mg_dl, measured_at=g.measured_at + shift,
                        meal_context=g.meal_context, source="uci") for g in series.glucose]
        + [InsulinDose(patient_id=patient_id, units=i.units, insulin_type=i.insulin_type,
                       administered_at=i.administered_at + shift, source="uci") for i in series.insulin]
        + [Meal(patient_id=patient_id, eaten_at=m.eaten_at + shift, description=m.description,
                source="uci") for m in series.meals]
    )
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input_dir", type=Path, help="extracted Diabetes-Data directory")
    parser.add_argument("--anchor", type=date.fromisoformat, default=DEFAULT_ANCHOR,
                        help=f"date each series ends on (default {DEFAULT_ANCHOR})")
    args = parser.parse_args()

    all_series = read_series(args.input_dir)
    if not all_series:
        raise SystemExit(f"No data-NN files found in {args.input_dir}")
    chosen = select_series(all_series)

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        patients = insulin_patient_ids(session)
        if not patients:
            raise SystemExit("No insulin-treated patients found; run the Synthea loader first.")

        loaded = skipped = 0
        for s, pid in zip(chosen, patients):
            if load_series(session, s, pid, args.anchor):
                loaded += 1
                print(f"{s.name} -> {pid}: {len(s.glucose)} glucose, {len(s.insulin)} insulin, {len(s.meals)} meals")
            else:
                skipped += 1
        session.commit()

    dropped = sum((s.skipped for s in chosen[:len(patients)]), Counter())
    print(f"Loaded {loaded} series, skipped {skipped} patients already loaded.")
    print(f"{len(chosen)} of {len(all_series)} UCI series qualified; {len(patients)} insulin-treated patients.")
    if dropped:
        print("Records not loaded: " + ", ".join(f"{n} {why}" for why, n in dropped.most_common()))


if __name__ == "__main__":
    main()
