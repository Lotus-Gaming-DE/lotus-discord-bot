"""Pytest package configuration for champion tests."""

import pytest

# Run all async tests in auto mode
pytestmark = pytest.mark.asyncio(mode="auto")
