import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


@pytest.fixture()
def sqlite_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(sqlite_engine):
    TestingSession = sessionmaker(
        bind=sqlite_engine, autoflush=False, expire_on_commit=False
    )
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture()
def client(sqlite_engine):
    TestingSession = sessionmaker(
        bind=sqlite_engine, autoflush=False, expire_on_commit=False
    )

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def authed_client(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"name": "Test Chemist", "email": "chemist@test.id", "password": "secret123"},
    )
    assert r.status_code == 201
    token = r.json()["tokens"]["accessToken"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
