from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.loaders.shanghai import (
    load_series,
    non_insulin_patient_ids,
    parse_frame,
    read_series,
    select_series,
)
from app.models import GlucoseReading, Meal, Medication, Patient

HEADERS = [
    "Date", "CGM (mg / dl)", "CBG (mg / dl)", "Blood Ketone (mmol / L)", "Dietary intake", "饮食",
    "Insulin dose - s.c.", "Non-insulin hypoglycemic agents", "CSII - bolus insulin (Novolin R, IU)",
    "CSII - basal insulin (Novolin R, IU / H)", "Insulin dose - i.v.",
]


def frame(rows, headers=HEADERS):
    """rows: dicts keyed by column position."""
    return pd.DataFrame([[r.get(i) for i in range(len(headers))] for r in rows], columns=headers)


def cgm_rows(days, start=datetime(2021, 6, 1, 8, 0), value=140.0):
    return [{0: start + timedelta(minutes=15 * i), 1: value} for i in range(days * 96)]


def test_parse_frame_reads_cgm_and_diet_and_skips_bad_values():
    df = frame([
        {0: datetime(2021, 6, 1, 7, 0), 1: 138.6, 2: 120.0},          # CBG is not stored
        {0: datetime(2021, 6, 1, 7, 15), 1: 10.0},                     # out of range
        {0: datetime(2021, 6, 1, 7, 30), 4: "Rice 150 g\nVegetable  100 g\n", 5: "米饭150g"},
        {0: datetime(2021, 6, 1, 12, 0), 4: "Data not available"},   # meal time known, contents not
        {0: None, 1: 150.0},                                           # no timestamp
        {0: datetime(2021, 6, 1, 7, 45), 7: "metformin 850 mg"},       # oral agent: not stored
    ])
    s = parse_frame("2003_0_20210615", df)
    assert [(g.measured_at, g.value_mg_dl) for g in s.glucose] == [(datetime(2021, 6, 1, 7, 0), 138.6)]
    assert [m.description for m in s.meals] == ["Rice 150 g, Vegetable 100 g", None]
    assert s.insulin_entries == 0
    assert s.patient_code == "2003"
    assert s.skipped == {"CGM value out of range": 1, "missing timestamp": 1}


def test_parse_frame_counts_insulin_in_any_insulin_column():
    df = frame([{0: datetime(2021, 6, 1), 1: 120, 6: "Gansulin 40R, 6 IU"},
                {0: datetime(2021, 6, 2), 1: 120, 9: 0.8}])
    assert parse_frame("2000_0_20201230", df).insulin_entries == 2


def test_parse_frame_accepts_header_variants_and_rejects_unexpected_layout():
    variant = ["Date", "CGM ", "CBG ", "Blood Ketone ", "Dietary intake", "饮食", "Insulin dose - s.c.",
               "Non-insulin hypoglycemic agents", "CSII - bolus insulin ", "胰岛素泵基础量", "Insulin dose - i.v."]
    assert len(parse_frame("2050_0_20210101", frame(cgm_rows(1), variant)).glucose) == 96

    shuffled = HEADERS[:1] + HEADERS[2:3] + HEADERS[1:2] + HEADERS[3:]
    with pytest.raises(ValueError, match="column 1"):
        parse_frame("2050_0_20210101", frame(cgm_rows(1), shuffled))


def test_select_series_no_insulin_min_days_longest_file_per_person():
    on_insulin = parse_frame("2000_0_20201230", frame(cgm_rows(10) + [{0: datetime(2021, 7, 1), 6: "6 IU"}]))
    too_short = parse_frame("2001_0_20201102", frame(cgm_rows(3)))
    first_visit = parse_frame("2002_0_20210513", frame(cgm_rows(8)))
    second_visit = parse_frame("2002_1_20210601", frame(cgm_rows(12)))
    other = parse_frame("2004_0_20211028", frame(cgm_rows(7)))
    chosen = select_series([other, on_insulin, too_short, first_visit, second_visit])
    assert [s.name for s in chosen] == ["2002_1_20210601", "2004_0_20211028"]


def test_read_series_reads_excel_files_only(tmp_path):
    frame(cgm_rows(1)).to_excel(tmp_path / "2003_0_20210615.xlsx", index=False)
    (tmp_path / ".DS_Store").write_bytes(b"\x00")
    (tmp_path / "notes.txt").write_text("not data")
    assert [s.name for s in read_series(tmp_path)] == ["2003_0_20210615"]


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([
            Patient(id="p-b", first_name="B", last_name="B"),
            Patient(id="p-a", first_name="A", last_name="A"),
            Patient(id="p-ins", first_name="C", last_name="C"),
            Medication(id="m-1", patient_id="p-ins", name="Insulin isophane [Humulin]", status="active"),
            Medication(id="m-2", patient_id="p-a", name="Metformin 500 MG", status="active"),
        ])
        s.commit()
        yield s


def test_non_insulin_patients_sorted(session):
    assert non_insulin_patient_ids(session) == ["p-a", "p-b"]


def test_load_series_shifts_to_anchor_keeps_time_and_skips_reload(session):
    df = frame([
        {0: datetime(2021, 6, 1, 23, 50), 1: 150.0},
        {0: datetime(2021, 6, 2, 12, 5), 4: "Noodles 100 g"},
        {0: datetime(2021, 6, 2, 12, 10), 1: 210.0},
    ])
    s = parse_frame("2003_0_20210615", df)
    assert load_series(session, s, "p-a", anchor=date(2026, 11, 1)) is True
    session.commit()

    glucose = session.scalars(select(GlucoseReading).order_by(GlucoseReading.measured_at)).all()
    assert [(g.measured_at, g.source) for g in glucose] == [
        (datetime(2026, 10, 31, 23, 50), "cgm"),
        (datetime(2026, 11, 1, 12, 10), "cgm"),
    ]
    meal = session.scalars(select(Meal)).one()
    assert (meal.eaten_at, meal.description, meal.carbs_g) == (datetime(2026, 11, 1, 12, 5), "Noodles 100 g", None)

    assert load_series(session, s, "p-a", anchor=date(2026, 11, 1)) is False
    assert session.query(GlucoseReading).count() == 2
