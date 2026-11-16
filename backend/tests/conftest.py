import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://exporbit:exporbit_dev@localhost:5432/exporbit_test")

from app.infrastructure.database import get_session  # noqa: E402
from app.main import app  # noqa: E402

engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3})
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


def database_available() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not database_available(), reason="PostgreSQL test database is unavailable")


def _truncate(connection) -> None:
    try:
        connection.execute(text("TRUNCATE llm_runs, inquiries, customers RESTART IDENTITY CASCADE"))
    except Exception:
        # llm_runs may not exist yet if the latest migration has not been applied
        connection.execute(text("TRUNCATE inquiries, customers RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def clean_database():
    if not database_available():
        yield
        return
    with engine.begin() as connection:
        _truncate(connection)
    yield


@pytest.fixture
def client():
    def override_session():
        with TestingSession() as session:
            yield session
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
