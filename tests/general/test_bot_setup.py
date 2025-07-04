import pytest


@pytest.mark.asyncio
async def test_setup_hook_clears_global_commands(monkeypatch, bot):
    clear_calls = []

    def fake_clear(guild=None):
        clear_calls.append(guild)

    async def fake_sync(guild=None):
        pass

    monkeypatch.setattr(bot.tree, "clear_commands", fake_clear)
    monkeypatch.setattr(bot.tree, "sync", fake_sync)

    monkeypatch.setattr("lotus_bot.bot.load_json", lambda path: {})

    async def fake_load():
        return {}

    monkeypatch.setattr("lotus_bot.bot.load_wcr_data", fake_load)
    monkeypatch.setattr("lotus_bot.bot.load_quiz_config", lambda b: None)

    async def nop(bot):
        return None

    monkeypatch.setattr("lotus_bot.cogs.quiz.setup", nop)
    monkeypatch.setattr("lotus_bot.cogs.wcr.setup", nop)
    monkeypatch.setattr("lotus_bot.cogs.champion.setup", nop)
    monkeypatch.setattr("lotus_bot.bot.Path.glob", lambda self, pattern: [])
    monkeypatch.setattr(bot, "_load_emojis_from_file", lambda: {})

    await bot.setup_hook()

    assert None in clear_calls
