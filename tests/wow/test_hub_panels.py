import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
import pytest_asyncio

from lotus_bot.cogs.wow import cog as wow_cog_mod
from lotus_bot.utils import ephemeral


def _cog():
    cog = MagicMock()
    cog.bot.data = {"emojis": {}}
    return cog


def _all_texts(view):
    return "".join(
        c.content for c in view.walk_children() if isinstance(c, discord.ui.TextDisplay)
    )


def _custom_ids(view):
    return [
        c.custom_id
        for c in view.walk_children()
        if isinstance(c, discord.ui.Button) and c.custom_id
    ]


def test_classic_hub_is_persistent_and_fits_limits():
    view = wow_cog_mod.WoWPanelLayoutView(_cog())
    ids = _custom_ids(view)
    assert len(ids) == len(set(ids))
    # Forever guilds, help, champion rank and the Raider role are gone.
    assert not {
        "wow_panel_v2:forever",
        "wow_panel_v2:help",
        "wow_panel_v2:champion",
        "wow_panel_v2:raider",
    } & set(ids)
    assert view.is_persistent()
    assert len(list(view.walk_children())) + 1 <= 40
    assert len(_all_texts(view)) < 4000


class _Message:
    def __init__(self, mid):
        self.id = mid
        self.edits = []
        self.deleted = False

    async def edit(self, **kwargs):
        self.edits.append(kwargs)

    async def delete(self):
        self.deleted = True


class _Channel:
    id = 1463577361562992807

    def __init__(self):
        self.messages = {}
        self.sent_order = []
        self._next = 100

    async def send(self, **kwargs):
        self._next += 1
        msg = _Message(self._next)
        self.messages[msg.id] = msg
        self.sent_order.append((msg.id, kwargs["view"].variant))
        return msg

    async def fetch_message(self, mid):
        if mid not in self.messages or self.messages[mid].deleted:
            resp = type("R", (), {"status": 404, "reason": "NF"})()
            raise discord.NotFound(resp, {"message": "Unknown Message"})
        return self.messages[mid]


_OPEN_COGS = []


@pytest_asyncio.fixture(autouse=True)
async def _close_cog_databases():
    """Open aiosqlite connections keep the interpreter alive after the run."""
    yield
    for cog in _OPEN_COGS:
        await cog.data.close()
    _OPEN_COGS.clear()


async def _cog_with_db(tmp_path, patch_logged_task):
    from lotus_bot import log_setup
    from lotus_bot.cogs.wow.data import WoWData
    from tests.wow.test_wow_cog import DummyBot

    patch_logged_task(wow_cog_mod, log_setup)
    cog = wow_cog_mod.WoWCog(DummyBot())
    cog.data = WoWData(str(tmp_path / "wow.db"))
    _OPEN_COGS.append(cog)
    return cog


@pytest.mark.asyncio
async def test_publish_all_panels_posts_in_order_then_edits_in_place(
    tmp_path, patch_logged_task, monkeypatch
):
    monkeypatch.setattr(wow_cog_mod, "CLASSIC_PANEL_ENABLED", True)
    cog = await _cog_with_db(tmp_path, patch_logged_task)
    channel = _Channel()

    await cog.publish_all_panels(channel)

    assert [v for _, v in channel.sent_order] == ["classic"]
    first_ids = [i for i, _ in channel.sent_order]

    await cog.publish_all_panels(channel)  # restart: edit, don't repost

    assert [i for i, _ in channel.sent_order] == first_ids
    assert all(channel.messages[i].edits for i in first_ids)


@pytest.mark.asyncio
async def test_layout_change_replaces_the_old_single_panel(
    tmp_path, patch_logged_task, monkeypatch
):
    monkeypatch.setattr(wow_cog_mod, "CLASSIC_PANEL_ENABLED", True)
    cog = await _cog_with_db(tmp_path, patch_logged_task)
    channel = _Channel()
    old = _Message(7)
    channel.messages[7] = old
    await cog.data.set_setting("panel_message_id", "7")  # pre-split layout

    await cog.publish_all_panels(channel)

    assert old.deleted is True
    assert await cog.data.get_setting("panel_message_id") != "7"
    assert len(channel.sent_order) == 1


@pytest.mark.asyncio
async def test_disabled_classic_panel_is_removed_and_not_reposted(
    tmp_path, patch_logged_task
):
    cog = await _cog_with_db(tmp_path, patch_logged_task)
    channel = _Channel()
    classic = _Message(7)
    channel.messages[7] = classic
    await cog.data.set_setting("panel_layout", wow_cog_mod.PANEL_LAYOUT)
    await cog.data.set_setting("panel_message_id", "7")

    result = await cog.publish_all_panels(channel)

    assert result is None
    assert classic.deleted is True
    assert await cog.data.get_setting("panel_message_id") == ""
    assert channel.sent_order == []

    await cog.publish_all_panels(channel)  # next refresh: nothing comes back
    assert channel.sent_order == []


@pytest.mark.asyncio
async def test_the_old_wow_bei_lotus_gaming_panel_is_removed(
    tmp_path, patch_logged_task
):
    # The channel belongs to Lotus Link; it offers the Raider role now.
    cog = await _cog_with_db(tmp_path, patch_logged_task)
    channel = _Channel()
    general = _Message(8)
    channel.messages[8] = general
    await cog.data.set_setting("panel_layout", wow_cog_mod.PANEL_LAYOUT)
    await cog.data.set_setting("panel_general_message_id", "8")

    await cog.publish_all_panels(channel)

    assert general.deleted is True
    assert await cog.data.get_setting("panel_general_message_id") == ""
    assert "general" not in [v for _, v in channel.sent_order]


@pytest.mark.asyncio
async def test_ephemeral_cleanup_deletes_after_delay_and_ignores_errors():
    interaction = MagicMock()
    interaction.delete_original_response = AsyncMock()
    ephemeral.schedule_response_cleanup(interaction, delay=0.01)

    gone = MagicMock()
    resp = type("R", (), {"status": 404, "reason": "NF"})()
    gone.delete = AsyncMock(side_effect=discord.NotFound(resp, {"message": "x"}))
    ephemeral.schedule_message_cleanup(gone, delay=0.01)

    await asyncio.sleep(0.1)

    interaction.delete_original_response.assert_awaited_once()
    gone.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_old_forever_guild_panel_is_removed(tmp_path, patch_logged_task):
    # The ForeverCog grants the guild roles from Battle.net links now.
    cog = await _cog_with_db(tmp_path, patch_logged_task)
    channel = _Channel()
    forever = _Message(9)
    channel.messages[9] = forever
    await cog.data.set_setting("panel_layout", wow_cog_mod.PANEL_LAYOUT)
    await cog.data.set_setting("panel_forever_message_id", "9")

    await cog.publish_all_panels(channel)

    assert forever.deleted is True
    assert await cog.data.get_setting("panel_forever_message_id") == ""
    assert channel.sent_order == []
