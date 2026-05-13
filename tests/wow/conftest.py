"""Default WoW API stubs for the test suite.

Without these, every `_refresh_member_profiles` call during a scan would
attempt a real Battle.net request, log a warning and slow the suite down.
Tests that need specific profile responses override `fetch_character_profile`
via `monkeypatch.setattr(wow_cog_mod, "fetch_character_profile", ...)`.
"""

from __future__ import annotations

import pytest

import lotus_bot.cogs.wow.cog as wow_cog_mod


@pytest.fixture(autouse=True)
def stub_wow_api(monkeypatch):
    async def alive_profile(*args, **kwargs):
        return {"is_ghost": False}

    monkeypatch.setattr(wow_cog_mod, "fetch_character_profile", alive_profile)
