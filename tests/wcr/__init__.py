"""Pytest package configuration for WCR tests."""

import pytest

pytestmark = pytest.mark.asyncio(mode="auto")
