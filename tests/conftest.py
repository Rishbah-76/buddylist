"""Pytest configuration and fixtures."""
import asyncio
import pytest
from pathlib import Path
import tempfile
import os


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_session_dir(monkeypatch):
    """Create temp directory for session storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir) / "sessions"
        session_dir.mkdir()
        monkeypatch.setenv("ORCHESTRA_TEST_MODE", "1")
        yield session_dir


@pytest.fixture
def sample_config():
    """Sample agent config for testing."""
    return {
        "team": "test-team",
        "display": "test-user",
        "repo": "/tmp/test-repo",
        "broker": "ws://localhost:8765",
    }


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temp repo for testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# Test Repo\nThis is a test.")
    (repo / "test.py").write_text("def hello(): return 'world'")
    return repo
