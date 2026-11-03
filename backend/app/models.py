"""SQLAlchemy tables for GlucoTrack.

Datetimes are stored as the patient's local time (no timezone), because the
app reasons about time of day ("readings run high after dinner").
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # FHIR Patient.id
    first_name: Mapped[str]
    last_name: Mapped[str]
    gender: Mapped[str | None]
    birth_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(default="synthea")

    conditions: Mapped[list["Condition"]] = relationship(back_populates="patient")
    medications: Mapped[list["Medication"]] = relationship(back_populates="patient")
    observations: Mapped[list["Observation"]] = relationship(back_populates="patient")
    glucose_readings: Mapped[list["GlucoseReading"]] = relationship(back_populates="patient")


class Condition(Base):
    """Diagnoses and medical history (FHIR Condition, SNOMED CT coded)."""

    __tablename__ = "conditions"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # FHIR Condition.id
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    snomed_code: Mapped[str] = mapped_column(index=True)
    display: Mapped[str]
    clinical_status: Mapped[str | None]  # active / resolved
    onset_at: Mapped[datetime | None] = mapped_column(DateTime)
    abatement_at: Mapped[datetime | None] = mapped_column(DateTime)

    patient: Mapped[Patient] = relationship(back_populates="conditions")


class Medication(Base):
    """Prescriptions (FHIR MedicationRequest, RxNorm coded)."""

    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # FHIR MedicationRequest.id
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    rxnorm_code: Mapped[str | None]
    name: Mapped[str]
    status: Mapped[str]  # active / completed / stopped
    authored_on: Mapped[datetime | None] = mapped_column(DateTime)
    prescriber: Mapped[str | None]

    patient: Mapped[Patient] = relationship(back_populates="medications")


class Observation(Base):
    """Labs and vitals other than glucose, keyed by LOINC code.

    HbA1c (4548-4), BMI (39156-5), and blood pressure. A FHIR BP panel
    (85354-9) is split into one row for systolic (8480-6) and one for
    diastolic (8462-4); both rows share the same fhir_id and effective_at.
    """

    __tablename__ = "observations"
    __table_args__ = (Index("ix_obs_patient_code_time", "patient_id", "loinc_code", "effective_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fhir_id: Mapped[str | None]
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    loinc_code: Mapped[str]
    display: Mapped[str]
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None]
    effective_at: Mapped[datetime] = mapped_column(DateTime)

    patient: Mapped[Patient] = relationship(back_populates="observations")


class GlucoseReading(Base):
    """Every glucose value, whatever its origin.

    Lab glucose from FHIR (LOINC 2339-0 / 2345-7) lands here rather than in
    observations, so the Glucose Log can show one combined history.
    """

    __tablename__ = "glucose_readings"
    __table_args__ = (Index("ix_glucose_patient_time", "patient_id", "measured_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    value_mg_dl: Mapped[float] = mapped_column(Float)
    measured_at: Mapped[datetime] = mapped_column(DateTime)
    meal_context: Mapped[str | None]  # fasting / before_meal / after_meal / bedtime
    source: Mapped[str]  # fhir / user / uci / cgm
    fhir_id: Mapped[str | None]

    patient: Mapped[Patient] = relationship(back_populates="glucose_readings")


class InsulinDose(Base):
    __tablename__ = "insulin_doses"
    __table_args__ = (Index("ix_insulin_patient_time", "patient_id", "administered_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    units: Mapped[float] = mapped_column(Float)
    insulin_type: Mapped[str | None]  # rapid / long / premixed
    administered_at: Mapped[datetime] = mapped_column(DateTime)
    source: Mapped[str]  # user / uci


class Meal(Base):
    __tablename__ = "meals"
    __table_args__ = (Index("ix_meal_patient_time", "patient_id", "eaten_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    eaten_at: Mapped[datetime] = mapped_column(DateTime)
    description: Mapped[str | None]
    carbs_g: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str]  # user / uci
