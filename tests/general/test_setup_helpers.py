import pytest
from discord import app_commands
from discord.ext import commands

from lotusbot.utils.setup_helpers import register_cog_and_group


class DummyCog(commands.Cog):
    pass


@pytest.mark.asyncio
async def test_register_cog_and_group_sync(monkeypatch, bot):
    called = []

    async def fake_add_cog(cog):
        called.append("add_cog")

    def fake_add_command(cmd, *, guild=None):
        called.append((cmd.name, guild))

    async def fake_sync(*, guild=None):
        called.append(("sync", guild))

    monkeypatch.setattr(bot, "add_cog", fake_add_cog)
    monkeypatch.setattr(bot.tree, "add_command", fake_add_command)
    monkeypatch.setattr(bot.tree, "sync", fake_sync)

    group = app_commands.Group(name="dummy", description="x")
    await register_cog_and_group(bot, DummyCog, group)

    assert ("sync", bot.main_guild) in called
