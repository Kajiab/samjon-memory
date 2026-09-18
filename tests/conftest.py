"""Test configuration for Samjon Memory Core."""

import os
import tempfile
import pytest
from samjon_memory.core.service import CoreService


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