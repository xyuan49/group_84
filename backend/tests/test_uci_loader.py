from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.loaders.uci import UciRecord, insulin_patient_ids, load_series, parse_series, read_series, select_series
from app.models import GlucoseReading, InsulinDose, Meal, Medication, Patient

LINES = [
    "04-21-1991\t9:09\t58\t100\n",   # pre-breakfast glucose -> fasting
    "04-21-1991\t9:09\t33\t009\n",   # regular insulin
    "04-21-1991\t9:09\t34\t013\n",   # NPH insulin
    "04-21-1991\t17:08\t62\t119\n",  # pre-supper -> before_meal
    "04-21-1991\t17:10\t67\t0\n",    # larger meal
    "04-22-1991\t22:51\t48\t123\n",  # unspecified glucose
    "04-22-1991\t7:35\t33\t3A\n",    # non-numeric value
    "\t138\t33\t3A\n",               # missing date
    "06-31-1991\t8:00\t58\t150\n",   # impossible date
    "04-22-1991\t8:00\t62\t0Hi\n",   # meter "high" with no number
    "04-22-1991\t8:05\t60\t0\n",     # glucose 0 -> out of range
    "04-22-1991\t8:06\t33\t0\n",     # 0 units -> out of range
    "04-22-1991\t8:07\t69\t0\n",     # exercise -> not stored
    "04-22-1991\t8:08\t36\t5\n",     # undocumented code
]


def test_record_parses_line():
    rec = UciRecord.from_line("04-21-1991\t9:09\t58\t100\n")
    assert rec == UciRecord(timestamp=datetime(1991, 4, 21, 9, 9), code=58, value=100)


def test_parse_series_maps_codes_and_counts_skips():
    s = parse_series("data-01", LINES)
    assert [(g.value_mg_dl, g.meal_context) for g in s.glucose] == [(100, "fasting"), (119, "before_meal"), (123, None)]
    assert [(i.units, i.insulin_type) for i in s.insulin] == [(9, "short"), (13, "intermediate")]
    assert [m.description for m in s.meals] == ["Larger than usual meal"]
    assert s.skipped == {
        "malformed line": 4,
        "value out of range": 2,
        "not stored (symptom/exercise/event)": 1,
        "unknown code": 1,
    }


def series_spanning(name, days, time="9:09"):
    return parse_series(name, [f"05-{d:02d}-1991\t{time}\t58\t120\n" for d in range(1, days + 1)])


def test_select_series_needs_two_weeks_of_device_timestamps():
    long_device = series_spanning("data-01", 20)
    short = series_spanning("data-02", 5)
    paper = series_spanning("data-03", 20, time="8:00")
    assert [s.name for s in select_series([long_device, short, paper])] == ["data-01"]


def test_read_series_ignores_non_data_files(tmp_path):
    (tmp_path / "data-01").write_text(LINES[0])
    (tmp_path / "Data-Codes").write_text("33 = Regular insulin dose\n")
    (tmp_path / "data-01.bak").write_text(LINES[0])
    assert [s.name for s in read_series(tmp_path)] == ["data-01"]


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([
            Patient(id="p-b", first_name="B", last_name="B"),
            Patient(id="p-a", first_name="A", last_name="A"),
            Patient(id="p-none", first_name="C", last_name="C"),
            Medication(id="m-1", patient_id="p-b", name="insulin, regular, human 100 UNT/ML", status="active"),
            Medication(id="m-2", patient_id="p-a", name="Insulin isophane [Humulin]", status="completed"),
            Medication(id="m-3", patient_id="p-a", name="insulin, regular, human", status="active"),
            Medication(id="m-4", patient_id="p-none", name="Metformin 500 MG", status="active"),
        ])
        s.commit()
        yield s


def test_insulin_patients_sorted_and_distinct(session):
    assert insulin_patient_ids(session) == ["p-a", "p-b"]


def test_load_series_shifts_dates_to_anchor_and_keeps_time(session):
    s = parse_series("data-01", LINES)
    assert load_series(session, s, "p-a", anchor=date(2026, 11, 1)) is True
    session.commit()

    glucose = session.scalars(select(GlucoseReading).order_by(GlucoseReading.measured_at)).all()
    # Last record (04-22-1991 22:51) lands on the anchor date; the rest move by the same number of days.
    assert glucose[-1].measured_at == datetime(2026, 11, 1, 22, 51)
    assert glucose[0].measured_at == datetime(2026, 10, 31, 9, 9)
    assert {g.source for g in glucose} == {"uci"}
    assert session.query(InsulinDose).count() == 2
    assert session.scalars(select(Meal)).one().eaten_at == datetime(2026, 10, 31, 17, 10)


def test_load_series_skips_patient_already_loaded(session):
    s = parse_series("data-01", LINES)
    assert load_series(session, s, "p-a", anchor=date(2026, 11, 1)) is True
    session.commit()
    assert load_series(session, s, "p-a", anchor=date(2026, 11, 1)) is False
    assert session.query(GlucoseReading).count() == 3
