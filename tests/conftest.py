import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.db.repositories import _in_memory_incidents, _in_memory_events, _in_memory_docs
from scripts.seed_rag import seed_runbooks


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Ensure runbooks are seeded and clear incident state before each test."""
    _in_memory_incidents.clear()
    _in_memory_events.clear()

    # Seed runbooks once if not populated
    if len(_in_memory_docs) == 0:
        seed_runbooks(force=False)

    yield


@pytest.fixture
def client():
    """Provide FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client
