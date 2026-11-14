"""Pydantic models for API requests and responses.

Response models (`...Out`) read straight from SQLAlchemy rows
(`from_attributes`), so an endpoint can return ORM objects and FastAPI
converts them. Request models (`...In`) validate what patients submit; FastAPI
answers 422 when a request breaks a limit.

Times are local clock time, like the database: a timestamp sent with a UTC
offset keeps its clock time and the offset is dropped.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MealContext = Literal["fasting", "before_meal", "after_meal", "bedtime"]
InsulinType = Literal["rapid", "short", "intermediate", "long", "premixed"]
GlucoseSource = Literal["fhir", "user", "uci", "cgm"]
LogSource = Literal["user", "uci", "cgm"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LocalTimeModel(BaseModel):
    """Request model whose datetime fields are stored as local clock time."""

    @field_validator("*", mode="after")
    @classmethod
    def drop_utc_offset(cls, v):
        if isinstance(v, datetime) and v.tzinfo is not None:
            return v.replace(tzinfo=None)
        return v


# --- clinical record (read-only, from Synthea / FHIR) ----------------------


class PatientOut(ORMModel):
    id: str
    first_name: str
    last_name: str
    gender: str | None
    birth_date: date | None


class ConditionOut(ORMModel):
    id: str
    snomed_code: str
    display: str
    clinical_status: str | None  # active / resolved
    onset_at: datetime | None
    abatement_at: datetime | None


class MedicationOut(ORMModel):
    id: str
    rxnorm_code: str | None
    name: str
    status: str  # active / completed / stopped
    authored_on: datetime | None
    prescriber: str | None


class ObservationOut(ORMModel):
    """HbA1c (4548-4), BMI (39156-5), systolic (8480-6), diastolic (8462-4)."""

    id: int
    loinc_code: str
    display: str
    value: float
    unit: str | None
    effective_at: datetime


# --- glucose, insulin, meals (imported datasets + patient entries) ---------


class GlucoseIn(LocalTimeModel):
    value_mg_dl: float = Field(ge=20, le=600, description="Meters and CGMs read about 20-600 mg/dL")
    measured_at: datetime
    meal_context: MealContext | None = None


class GlucoseOut(ORMModel):
    id: int
    value_mg_dl: float
    measured_at: datetime
    meal_context: MealContext | None
    source: GlucoseSource


class InsulinIn(LocalTimeModel):
    units: float = Field(gt=0, le=100)
    insulin_type: InsulinType | None = None
    administered_at: datetime


class InsulinOut(ORMModel):
    id: int
    units: float
    insulin_type: InsulinType | None
    administered_at: datetime
    source: LogSource


class MealIn(LocalTimeModel):
    eaten_at: datetime
    description: str | None = Field(default=None, min_length=1, max_length=500)
    carbs_g: float | None = Field(default=None, ge=0, le=500)
    calories: float | None = Field(default=None, ge=0, le=5000)


class MealOut(ORMModel):
    id: int
    eaten_at: datetime
    description: str | None
    carbs_g: float | None
    calories: float | None
    source: LogSource
