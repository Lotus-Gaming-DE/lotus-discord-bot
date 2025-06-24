import pytest

from cogs.quiz.slash_commands import quiz_group
from cogs.wcr.slash_commands import wcr_group
from cogs.champion.slash_commands import champion_group, syncroles
from cogs.ptcgp.slash_commands import ptcgp_group
import cogs.quiz.message_tracker as msg_mod
import log_setup


@pytest.mark.asyncio
async def test_load_all_cogs_registers_commands_and_syncs(
    monkeypatch, bot, patch_logged_task, wcr_data
):
    patch_logged_task(log_setup, msg_mod)

    monkeypatch.setattr("bot.Path.glob", lambda self, pattern: [])
    monkeypatch.setattr("bot.load_json", lambda path: {})

    async def fake_wcr_load():
        return wcr_data

    monkeypatch.setattr("bot.load_wcr_data", fake_wcr_load)
    monkeypatch.setattr("bot.load_quiz_config", lambda b: None)
    monkeypatch.setattr(bot, "_load_emojis_from_file", lambda: {})

    add_calls = []
    sync_calls = []

    def fake_add(cmd, *, guild=None):
        add_calls.append((cmd, guild))

    async def fake_sync(*, guild=None):
        sync_calls.append(guild)

    monkeypatch.setattr(bot.tree, "add_command", fake_add)
    monkeypatch.setattr(bot.tree, "sync", fake_sync)

    await bot.setup_hook()

    expected_groups = [
        quiz_group,
        wcr_group,
        champion_group,
        syncroles,
        ptcgp_group,
    ]

    assert add_calls == [(g, bot.main_guild) for g in expected_groups]
    assert sync_calls == [None, bot.main_guild]
