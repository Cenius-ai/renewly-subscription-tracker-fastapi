"""Pytest bootstrap: isolate the database, boot the real app, disable throttling."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

_TMP_DIR = tempfile.mkdtemp(prefix="renewly-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"
os.environ["SECRET_KEY"] = "renewly-test-session-key"
os.environ["RENEWLY_RATE_LIMIT"] = "off"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    """A fresh browser session per test; the database is shared and seeded."""
    with TestClient(app) as test_client:
        yield test_client
