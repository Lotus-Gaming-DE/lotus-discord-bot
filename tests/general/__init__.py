"""Pytest package configuration for general tests."""

import pytest

pytestmark = pytest.mark.asyncio(mode="auto")
