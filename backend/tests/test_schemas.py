from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.models import Condition, GlucoseReading, InsulinDose, Meal, Medication, Observation, Patient
from app.schemas import (
    ConditionOut,
    GlucoseIn,
    GlucoseOut,
    InsulinIn,
    InsulinOut,
    MealIn,
    MealOut,
    MedicationOut,
    ObservationOut,
    PatientOut,
)

# --- response models read ORM rows -----------------------------------------


def test_out_models_read_orm_rows():
    assert PatientOut.model_validate(
        Patient(id="p-1", first_name="Maria", last_name="Lopez", gender="female", birth_date=date(1968, 3, 2))
    ).last_name == "Lopez"
    assert ConditionOut.model_validate(
        Condition(id="c-1", snomed_code="44054006", display="Diabetes mellitus type 2 (disorder)",
                  clinical_status="active", onset_at=datetime(2016, 5, 1), abatement_at=None)
    ).snomed_code == "44054006"
    assert MedicationOut.model_validate(
        Medication(id="m-1", rxnorm_code="860975", name="Metformin 500 MG", status="active",
                   authored_on=None, prescriber=None)
    ).name == "Metformin 500 MG"
    assert ObservationOut.model_validate(
        Observation(id=1, loinc_code="4548-4", display="HbA1c", value=7.1, unit="%",
                    effective_at=datetime(2026, 1, 1))
    ).value == 7.1


@pytest.mark.parametrize("row, model", [
    (GlucoseReading(id=1, value_mg_dl=145, measured_at=datetime(2026, 11, 1, 7), meal_context="fasting",
                    source="cgm"), GlucoseOut),
    (InsulinDose(id=1, units=6, insulin_type="intermediate", administered_at=datetime(2026, 11, 1, 7),
                 source="uci"), InsulinOut),
    (Meal(id=1, eaten_at=datetime(2026, 11, 1, 12), description=None, carbs_g=None, calories=None,
          source="cgm"), MealOut),
])
def test_log_out_models_accept_every_loader_source(row, model):
    assert model.model_validate(row).source == row.source


def test_out_model_rejects_unknown_source():
    with pytest.raises(ValidationError):
        GlucoseOut.model_validate(GlucoseReading(id=1, value_mg_dl=100, measured_at=datetime(2026, 1, 1),
                                                 meal_context=None, source="spreadsheet"))


# --- request models validate patient input ---------------------------------


def test_glucose_in_defaults_and_offset_dropped():
    g = GlucoseIn(value_mg_dl=142, measured_at="2026-10-25T07:10:00-04:00")
    assert g.measured_at == datetime(2026, 10, 25, 7, 10)  # clock time kept
    assert g.meal_context is None


@pytest.mark.parametrize("body", [
    {"value_mg_dl": 0, "measured_at": "2026-10-25T07:10"},
    {"value_mg_dl": 900, "measured_at": "2026-10-25T07:10"},
    {"value_mg_dl": 142, "measured_at": "2026-10-25T07:10", "meal_context": "brunch"},
    {"value_mg_dl": 142},
    {"value_mg_dl": "high", "measured_at": "2026-10-25T07:10"},
])
def test_glucose_in_rejects_bad_input(body):
    with pytest.raises(ValidationError):
        GlucoseIn(**body)


def test_insulin_in():
    dose = InsulinIn(units=20, insulin_type="long", administered_at="2026-10-24T22:00:00Z")
    assert (dose.units, dose.administered_at) == (20, datetime(2026, 10, 24, 22, 0))
    for bad in ({"units": 0}, {"units": 150}, {"units": 5, "insulin_type": "fast"}):
        with pytest.raises(ValidationError):
            InsulinIn(**{"administered_at": "2026-10-24T22:00", **bad})


def test_meal_in():
    meal = MealIn(eaten_at="2026-10-24T19:00", description="Rice 150 g, Vegetable 100 g", carbs_g=55)
    assert (meal.description, meal.carbs_g, meal.calories) == ("Rice 150 g, Vegetable 100 g", 55, None)
    assert MealIn(eaten_at="2026-10-24T19:00").description is None  # everything but the time is optional
    for bad in ({"description": ""}, {"description": "x" * 501}, {"carbs_g": -1}, {"calories": 9000}):
        with pytest.raises(ValidationError):
            MealIn(**{"eaten_at": "2026-10-24T19:00", **bad})
