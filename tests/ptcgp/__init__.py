"""Pytest package configuration for PTCGP tests."""

import pytest

pytestmark = pytest.mark.asyncio(mode="auto")
