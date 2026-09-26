"""Test configuration for Samjon Memory Core."""

import os
import tempfile
import pytest

os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")


@pytest.fixture(autouse=True)
def _portal_vocabulary_path(tmp_path, monkeypatch):
    """Isolate the file-backed Portal vocabulary store per test."""
    monkeypatch.setenv("SAMJON_PORTAL_VOCABULARY_PATH",
                       str(tmp_path / "portal_vocabulary.json"))

from samjon_memory.core.service import CoreService
from samjon_memory.core.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except PermissionError:
        pass


@pytest.fixture
def service(temp_db):
    svc = CoreService(database_path=temp_db)
    return svc


@pytest.fixture
def portal_client(temp_db):
    """TestClient with portal HTTP Basic credentials."""
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    client = TestClient(app)
    client.auth = ("portal-admin", "portal-secret")
    return client