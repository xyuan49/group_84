"""Load the Shanghai T2DM CGM dataset onto non-insulin Synthea patients.

Synthea only records glucose at clinic visits. The Shanghai T2DM dataset
(Zhao et al., Scientific Data 2023) has real-life continuous glucose
monitoring (a reading every 15 minutes for 3-14 days) and diet records for
100 people with Type 2 diabetes. Insulin-treated Synthea patients already get
UCI data (app.loaders.uci), so this loader uses only Shanghai patients who
received no insulin and attaches each to a Synthea patient who has no insulin
prescription. Dates are shifted so each series ends on the anchor date (time
of day is kept).

Stored: CGM readings -> glucose_readings (source="cgm"), dietary intake ->
meals (source="cgm"). Not stored: finger-stick glucose (CBG), ketones and
oral-medication administrations.

Usage (from backend/, after the Synthea loader):
    python -m app.loaders.shanghai ../data/shanghai_raw/Shanghai_T2DM
"""

import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import GlucoseReading, Meal, Medication, Patient

DEFAULT_ANCHOR = date(2026, 11, 1)  # Synthea reference date, same as the UCI loader
MIN_DAYS = 7
SOURCE = "cgm"

# Column positions are stable across files; the header text varies slightly
# (e.g. "CGM (mg / dl)" vs "CGM ", some headers only in Chinese), so only the
# start of each English header is checked.
COL_DATE, COL_CGM, COL_DIET = 0, 1, 4
INSULIN_COLS = (6, 8, 9, 10)  # s.c. dose, pump bolus, pump basal, i.v. dose
EXPECTED_HEADERS = {0: "Date", 1: "CGM", 4: "Dietary intake", 6: "Insulin dose - s.c.", 8: "CSII - bolus"}
NOT_RECORDED = {"data not available"}  # diet placeholder: meal happened, contents unknown


# --- Pydantic models for incoming records ----------------------------------


class CgmReading(BaseModel):
    measured_at: datetime
    value_mg_dl: float = Field(ge=20, le=600)  # sensors report about 40-400 mg/dL


class DietEntry(BaseModel):
    eaten_at: datetime
    # None when the meal time was recorded but not what was eaten.
    description: str | None = Field(min_length=1, max_length=500)

    @field_validator("description", mode="before")
    @classmethod
    def one_line(cls, v):
        # Cells list one food per line: "Rice 150 g\nVegetable 100 g".
        if isinstance(v, str):
            text = ", ".join(" ".join(part.split()) for part in v.splitlines() if part.strip())
            return None if text.lower() in NOT_RECORDED else text
        return v


@dataclass
class ShanghaiSeries:
    name: str  # file stem, e.g. "2003_0_20210615"
    glucose: list[CgmReading] = field(default_factory=list)
    meals: list[DietEntry] = field(default_factory=list)
    insulin_entries: int = 0
    skipped: Counter = field(default_factory=Counter)

    @property
    def patient_code(self) -> str:
        return self.name.split("_")[0]

    @property
    def last_timestamp(self) -> datetime:
        return max([g.measured_at for g in self.glucose] + [m.eaten_at for m in self.meals])

    @property
    def days_covered(self) -> int:
        return len({g.measured_at.date() for g in self.glucose})


def check_headers(name: str, columns) -> None:
    for pos, prefix in EXPECTED_HEADERS.items():
        if pos >= len(columns) or not str(columns[pos]).strip().startswith(prefix):
            raise ValueError(f"{name}: expected column {pos} to start with {prefix!r}, got {list(columns)}")


def parse_frame(name: str, df: pd.DataFrame) -> ShanghaiSeries:
    check_headers(name, df.columns)
    series = ShanghaiSeries(name=name)
    series.insulin_entries = int(sum(df.iloc[:, i].notna().sum() for i in INSULIN_COLS if i < df.shape[1]))

    for row in df.itertuples(index=False):
        when, cgm, diet = row[COL_DATE], row[COL_CGM], row[COL_DIET]
        if pd.isna(when):
            series.skipped["missing timestamp"] += 1
            continue
        when = pd.Timestamp(when).to_pydatetime()
        if not pd.isna(cgm):
            try:
                series.glucose.append(CgmReading(measured_at=when, value_mg_dl=cgm))
            except ValidationError:
                series.skipped["CGM value out of range"] += 1
        if not pd.isna(diet):
            try:
                series.meals.append(DietEntry(eaten_at=when, description=diet))
            except ValidationError:
                series.skipped["invalid diet entry"] += 1
    return series


def read_series(raw_dir: Path) -> list[ShanghaiSeries]:
    paths = sorted(p for p in raw_dir.iterdir() if p.suffix in (".xls", ".xlsx") and not p.name.startswith("."))
    return [parse_frame(p.stem, pd.read_excel(p)) for p in paths]


def select_series(series: list[ShanghaiSeries], min_days: int = MIN_DAYS) -> list[ShanghaiSeries]:
    """No insulin, at least `min_days` of CGM, one file per person (the longest), in patient order."""
    best: dict[str, ShanghaiSeries] = {}
    for s in series:
        if s.insulin_entries or s.days_covered < min_days:
            continue
        current = best.get(s.patient_code)
        if current is None or (s.days_covered, len(s.glucose)) > (current.days_covered, len(current.glucose)):
            best[s.patient_code] = s
    return [best[code] for code in sorted(best)]


def non_insulin_patient_ids(session: Session) -> list[str]:
    on_insulin = select(Medication.patient_id).where(func.lower(Medication.name).like("%insulin%"))
    return list(session.scalars(select(Patient.id).where(Patient.id.not_in(on_insulin)).order_by(Patient.id)))


def load_series(session: Session, series: ShanghaiSeries, patient_id: str, anchor: date) -> bool:
    """Attach one series to a patient, shifted to end on `anchor`. False if already loaded."""
    already = session.scalars(
        select(GlucoseReading.id).where(GlucoseReading.patient_id == patient_id, GlucoseReading.source == SOURCE)
    ).first()
    if already is not None:
        return False

    shift = timedelta(days=(anchor - series.last_timestamp.date()).days)
    session.add_all(
        [GlucoseReading(patient_id=patient_id, value_mg_dl=g.value_mg_dl, measured_at=g.measured_at + shift,
                        meal_context=None, source=SOURCE) for g in series.glucose]
        + [Meal(patient_id=patient_id, eaten_at=m.eaten_at + shift, description=m.description,
                source=SOURCE) for m in series.meals]
    )
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input_dir", type=Path, help="extracted Shanghai_T2DM directory")
    parser.add_argument("--anchor", type=date.fromisoformat, default=DEFAULT_ANCHOR,
                        help=f"date each series ends on (default {DEFAULT_ANCHOR})")
    args = parser.parse_args()

    all_series = read_series(args.input_dir)
    if not all_series:
        raise SystemExit(f"No .xls/.xlsx files found in {args.input_dir}")
    chosen = select_series(all_series)

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        patients = non_insulin_patient_ids(session)
        if not patients:
            raise SystemExit("No non-insulin patients found; run the Synthea loader first.")

        loaded = skipped = 0
        for s, pid in zip(chosen, patients):
            if load_series(session, s, pid, args.anchor):
                loaded += 1
                print(f"{s.name} -> {pid}: {len(s.glucose)} CGM readings over {s.days_covered} days, "
                      f"{len(s.meals)} meals")
            else:
                skipped += 1
        session.commit()

    dropped = sum((s.skipped for s in chosen[:len(patients)]), Counter())
    print(f"Loaded {loaded} series, skipped {skipped} patients already loaded.")
    print(f"{len(chosen)} Shanghai patients qualified (no insulin, >= {MIN_DAYS} days) out of "
          f"{len(all_series)} files; {len(patients)} non-insulin Synthea patients.")
    if dropped:
        print("Records not loaded: " + ", ".join(f"{n} {why}" for why, n in dropped.most_common()))


if __name__ == "__main__":
    main()
