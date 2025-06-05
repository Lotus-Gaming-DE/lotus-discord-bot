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

    monkeypatch.setattr("bot.load_json", lambda path: {})
    monkeypatch.setattr("bot.load_wcr_data", lambda: {})
    monkeypatch.setattr("bot.load_quiz_config", lambda b: None)
    async def nop(bot):
        return None
    monkeypatch.setattr("cogs.quiz.setup", nop)
    monkeypatch.setattr("cogs.wcr.setup", nop)
    monkeypatch.setattr("cogs.champion.setup", nop)
    monkeypatch.setattr("bot.Path.glob", lambda self, pattern: [])
    monkeypatch.setattr(bot, "_load_emojis_from_file", lambda: {})

    await bot.setup_hook()

    assert None in clear_calls
