"""Pydantic models for API requests and responses.

Response models read straight from SQLAlchemy rows (`from_attributes`), so an
endpoint can return ORM objects and FastAPI converts them. Request models
(e.g. `GlucoseIn`) should validate value ranges with `Field(...)`.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PatientOut(ORMModel):
    id: str
    first_name: str
    last_name: str
    gender: str | None
    birth_date: date | None
