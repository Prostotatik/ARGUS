import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _no_real_gemini_key(monkeypatch):
    """The test suite must stay deterministic, offline and free regardless of a real
    GEMINI_API_KEY sitting in backend/.env or the environment - strip it for every test by
    default (config.default_engine() would otherwise silently pick "gemini" and a test that
    doesn't inject a fake client would make a real network call). A test that specifically wants
    to exercise key-present behaviour re-sets it itself via monkeypatch.setenv."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
