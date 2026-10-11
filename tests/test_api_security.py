import pytest

pytest.importorskip("httpx")

import config
from api.main import app
from fastapi.testclient import TestClient


def test_api_key_is_required_when_configured(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret")
    client = TestClient(app)

    missing = client.get("/api/kpis")
    valid = client.get("/api/kpis", headers={"x-api-key": "secret"})

    assert missing.status_code == 401
    assert valid.status_code != 401
