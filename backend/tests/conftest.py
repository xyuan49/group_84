from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Patient


@pytest.fixture
def db_session():
    """Empty in-memory database shared by the test and the API client."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session


@pytest.fixture
def client(db_session):
    """API client that uses db_session instead of glucotrack.db. Add rows to db_session first."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def patients(db_session):
    rows = [
        Patient(id="p-1", first_name="Maria", last_name="Lopez", gender="female", birth_date=date(1968, 3, 2)),
        Patient(id="p-2", first_name="Abe", last_name="Gaylord", gender="male", birth_date=date(1950, 1, 1)),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows
