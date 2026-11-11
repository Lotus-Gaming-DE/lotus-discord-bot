from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from lotus_bot.cogs.dev.slash_commands import dev_forever_report


def interaction_with(cog):
    return SimpleNamespace(
        client=SimpleNamespace(get_cog=lambda name: cog),
        response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )


async def test_forever_report_syncs_and_posts_now():
    snapshot = object()
    cog = MagicMock(sync=AsyncMock(return_value=snapshot), post_report=AsyncMock())
    interaction = interaction_with(cog)
    await dev_forever_report.callback(interaction)
    cog.post_report.assert_awaited_once_with(snapshot)


async def test_forever_report_skips_without_lotus_link():
    cog = MagicMock(sync=AsyncMock(return_value=None), post_report=AsyncMock())
    await dev_forever_report.callback(interaction_with(cog))
    cog.post_report.assert_not_awaited()


async def test_forever_report_without_cog_answers():
    interaction = interaction_with(None)
    await dev_forever_report.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
