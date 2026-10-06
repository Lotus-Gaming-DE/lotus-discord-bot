from unittest.mock import AsyncMock, MagicMock

import discord

from lotus_bot.cogs.community.cog import CommunityCog


def _cog(setting):
    cog = CommunityCog.__new__(CommunityCog)
    cog.data = MagicMock()
    cog.data.get_setting = AsyncMock(return_value=setting)
    cog.data.set_setting = AsyncMock()
    return cog


async def test_misplaced_forever_panel_is_deleted_once():
    cog = _cog("123")
    message = MagicMock()
    message.delete = AsyncMock()
    channel = MagicMock(spec=discord.TextChannel)
    channel.fetch_message = AsyncMock(return_value=message)

    await cog._remove_misplaced_forever_panel(channel)

    message.delete.assert_awaited_once()
    cog.data.set_setting.assert_awaited_once_with("forever_panel_message_id", "")


async def test_cleanup_is_noop_without_setting():
    cog = _cog(None)
    channel = MagicMock(spec=discord.TextChannel)
    channel.fetch_message = AsyncMock()

    await cog._remove_misplaced_forever_panel(channel)

    channel.fetch_message.assert_not_awaited()
