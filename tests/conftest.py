import pytest

@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("server_id", "0")
