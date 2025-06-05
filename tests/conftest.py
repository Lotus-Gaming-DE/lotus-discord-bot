import os
import sys
import pytest
import warnings

warnings.filterwarnings(
    "ignore",
    message=".*'audioop' is deprecated.*",
    category=DeprecationWarning,
    module=r"discord\.player",
)


def pytest_configure(config):
    warnings.filterwarnings(
        "ignore",
        message=".*'audioop' is deprecated.*",
        category=DeprecationWarning,
        module=r"discord\.player",
        append=True,
    )
    config.addinivalue_line(
        "filterwarnings",
        "ignore:.*'audioop' is deprecated.*:DeprecationWarning:discord\\.player",
    )

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("server_id", "0")


class DummyTask:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


@pytest.fixture
def patch_logged_task(monkeypatch):
    """Patch create_logged_task in the given modules with a dummy implementation."""

    def apply(*modules):
        def fake_task(coro, logger=None):
            coro.close()
            return DummyTask()

        for module in modules:
            monkeypatch.setattr(module, "create_logged_task", fake_task)

        return fake_task

    return apply
