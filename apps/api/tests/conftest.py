"""Test fixtures: a throwaway test database on the dev cluster, no network calls."""

import os

# Point the app at a dedicated test database BEFORE importing it.
os.environ.setdefault(
    "AGRISMART_DATABASE_URL",
    os.environ.get(
        "AGRISMART_TEST_DATABASE_URL",
        "postgresql+psycopg2://localhost:5432/agrismart_test",
    ),
)
os.environ.setdefault("AGRISMART_JWT_SECRET", "test-secret")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app import geo  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Field, User  # noqa: E402


def _ensure_test_database() -> None:
    url = get_settings().database_url
    db_name = url.rsplit("/", 1)[-1]
    admin_url = url.rsplit("/", 1)[0] + "/postgres"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _setup_schema():
    _ensure_test_database()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    # Fresh state per test.
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {Field.__tablename__}, {User.__tablename__} CASCADE"))
    yield


@pytest.fixture(autouse=True)
def _no_network_county(monkeypatch):
    monkeypatch.setattr(
        geo, "lookup_county",
        lambda lat, lon, timeout=6.0: {"county": "Hale", "county_fips": "48189", "state": "TX"},
    )
    # The fields router imported the name directly, so patch there too.
    import app.routers.fields as fields_router
    monkeypatch.setattr(fields_router, "lookup_county", geo.lookup_county)


@pytest.fixture
def client():
    return TestClient(app)


def _square(cx: float, cy: float, d: float = 0.004) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [cx - d, cy - d], [cx + d, cy - d], [cx + d, cy + d], [cx - d, cy + d], [cx - d, cy - d],
        ]],
    }


@pytest.fixture
def square_geometry():
    return _square


def register(client, email: str, password: str = "password123") -> str:
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
