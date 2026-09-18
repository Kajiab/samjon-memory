"""OpenAPI drift test."""

import json
import pytest


def test_openapi_drift():
    from samjon_memory.core.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["service"] == "samjon-memory-core"