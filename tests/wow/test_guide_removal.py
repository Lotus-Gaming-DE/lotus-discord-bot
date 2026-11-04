"""The how-to posts in the dungeons and market forums are switched off."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
import pytest_asyncio

from lotus_bot import log_setup
from lotus_bot.cogs.wow import cog as wow_cog_mod
from lotus_bot.cogs.wow.data import WoWData
from lotus_bot.cogs.wow.marketplace_cog import MarketplaceCog
from lotus_bot.cogs.wow.marketplace_data import MarketplaceData

pytestmark = pytest.mark.asyncio

_OPEN = []


@pytest_asyncio.fixture(autouse=True)
async def _close_databases():
    yield
    for data in _OPEN:
        await data.close()
    _OPEN.clear()


class _Bot:
    def __init__(self, thread=None):
        self.thread = thread
        self.views = []
        self.data = {}
        self.fetch_channel = AsyncMock(return_value=None)

    def get_channel(self, channel_id):
        return self.thread

    def add_view(self, view):
        self.views.append(view)

    def get_cog(self, name):
        return None

    async def wait_until_ready(self):
        return


def _thread(parent_id):
    thread = MagicMock(spec=discord.Thread)
    thread.parent_id = parent_id
    thread.delete = AsyncMock()
    return thread


async def _wow_cog(tmp_path, patch_logged_task, thread):
    patch_logged_task(wow_cog_mod, log_setup)
    cog = wow_cog_mod.WoWCog(_Bot(thread))
    cog.data = WoWData(str(tmp_path / "wow.db"))
    _OPEN.append(cog.data)
    return cog


async def _market_cog(tmp_path, thread):
    cog = MarketplaceCog(_Bot(thread))
    for task in list(cog.tasks):  # the startup publish must not race the test
        task.cancel()
    cog.data = MarketplaceData(str(tmp_path / "marketplace.db"))
    _OPEN.append(cog.data)
    return cog


async def test_dungeons_guide_is_deleted_and_forgotten(tmp_path, patch_logged_task):
    thread = _thread(wow_cog_mod.DUNGEONS_FORUM_CHANNEL_ID)
    cog = await _wow_cog(tmp_path, patch_logged_task, thread)
    await cog.data.set_setting("dungeons_guide_thread_id", "42")

    await cog.publish_dungeons_guide()

    thread.delete.assert_awaited_once()
    assert await cog.data.get_setting("dungeons_guide_thread_id") == ""


async def test_dungeons_guide_never_deletes_a_thread_of_another_channel(
    tmp_path, patch_logged_task
):
    thread = _thread(parent_id=1)  # not the dungeons forum
    cog = await _wow_cog(tmp_path, patch_logged_task, thread)
    await cog.data.set_setting("dungeons_guide_thread_id", "42")

    await cog.publish_dungeons_guide()

    thread.delete.assert_not_awaited()


async def test_dungeons_guide_without_stored_post_does_nothing(
    tmp_path, patch_logged_task
):
    thread = _thread(wow_cog_mod.DUNGEONS_FORUM_CHANNEL_ID)
    cog = await _wow_cog(tmp_path, patch_logged_task, thread)

    await cog.publish_dungeons_guide()

    thread.delete.assert_not_awaited()


async def test_market_hub_is_deleted_and_forgotten(tmp_path):
    cog = await _market_cog(tmp_path, None)
    thread = _thread(cog.forum_channel_id)
    cog.bot.thread = thread
    await cog.data.set_setting("hub_thread_id", "77")

    await cog.remove_hub()

    thread.delete.assert_awaited_once()
    assert await cog.data.get_setting("hub_thread_id") == ""


async def test_market_hub_never_deletes_a_thread_of_another_channel(tmp_path):
    cog = await _market_cog(tmp_path, None)
    thread = _thread(parent_id=1)
    cog.bot.thread = thread
    await cog.data.set_setting("hub_thread_id", "77")

    await cog.remove_hub()

    thread.delete.assert_not_awaited()
