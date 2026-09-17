"""Unit tests for the db-health service and its HTTP mapping.

Hermetic by design: no network, the DB session is faked.
"""

import pytest
from fastapi.testclient import TestClient

import app.api.v1.db as db_route
from app.core.exceptions import DatabaseUnavailableError
from app.main import app
from app.services.health_service import get_db_status

client = TestClient(app)


class FakeSession:
    def __init__(self, fail: bool = False):
        self.fail = fail

    def execute(self, stmt):
        if self.fail:
            raise Exception("connection refused: SECRET-DETAILS-123")
        return None


def test_service_healthy():
    result = get_db_status(FakeSession())
    assert result.status == "ok"
    assert result.db == "connected"


def test_service_unhealthy_raises_domain_error():
    with pytest.raises(DatabaseUnavailableError):
        get_db_status(FakeSession(fail=True))


def test_endpoint_maps_to_503_without_leaking_details(monkeypatch):
    def boom(db):
        raise DatabaseUnavailableError("connection refused: SECRET-DETAILS-123")

    monkeypatch.setattr(db_route, "get_db_status", boom)
    r = client.get("/api/v1/db-health")
    assert r.status_code == 503
    assert r.json() == {"detail": "database unavailable"}
    assert "SECRET-DETAILS-123" not in r.text
