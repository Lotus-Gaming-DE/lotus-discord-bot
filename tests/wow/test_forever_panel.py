import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
import pytest_asyncio

from lotus_bot.cogs.wow import cog as wow_cog_mod
from lotus_bot.cogs.wow.forever_panel import (
    BAR_WIDTH,
    FACTION_ROLE_IDS,
    MIN_SCALE,
    bar_scale,
    count_forever_roles,
    progress_bar,
)
from lotus_bot.cogs.wow.forever_roles import FOREVER_ROLES
from lotus_bot.utils import ephemeral

HORDE_HC = 1556277335500525749
HORDE_PVP = 1556276890853965884


def _cog():
    cog = MagicMock()
    cog.bot.data = {"emojis": {}}
    return cog


def _guild(members_by_role):
    guild = MagicMock(spec=discord.Guild)
    roles = {}
    for rid, member_ids in members_by_role.items():
        role = MagicMock(spec=discord.Role)
        role.members = [MagicMock(id=m) for m in member_ids]
        roles[rid] = role
    guild.get_role.side_effect = roles.get
    return guild


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


def test_scale_has_a_floor_and_grows_with_the_number_of_players():
    assert bar_scale(0) == MIN_SCALE
    assert bar_scale(33) == MIN_SCALE  # 60 % of 33 is still below the floor
    assert bar_scale(34) > MIN_SCALE
    assert bar_scale(100) == 60
    sizes = [bar_scale(n) for n in range(0, 400)]
    assert sizes == sorted(sizes)  # never shrinks while players are added


def test_bars_share_one_scale_across_rows():
    scale = bar_scale(33)
    assert progress_bar(0, scale).count("▰") == 0
    assert progress_bar(1, scale).count("▰") == 1  # first person is visible
    assert progress_bar(17, scale).count("▰") > progress_bar(9, scale).count("▰")
    # Same count -> same bar, whichever guild it belongs to.
    assert progress_bar(9, scale) == progress_bar(9, scale)
    assert progress_bar(scale, scale) == "▰" * BAR_WIDTH
    assert progress_bar(scale * 3, scale) == "▰" * BAR_WIDTH  # no overflow
    assert len(progress_bar(37, scale)) == len(progress_bar(0, scale)) == BAR_WIDTH


def test_count_forever_roles_counts_people_once():
    guild = _guild({HORDE_HC: [1, 2, 3], HORDE_PVP: [3, 4]})

    counts, total = count_forever_roles(guild)

    assert counts[HORDE_HC] == 3 and counts[HORDE_PVP] == 2
    assert total == 4  # person 3 holds two roles
    assert count_forever_roles(None)[1] == 0


def test_three_variants_have_disjoint_custom_ids_and_fit_limits():
    classic = wow_cog_mod.WoWPanelLayoutView(_cog())
    general = wow_cog_mod.WoWPanelLayoutView(_cog(), variant="general")
    forever = wow_cog_mod.WoWPanelLayoutView(
        _cog(), variant="forever", forever_counts=({HORDE_HC: 12}, 12)
    )

    all_ids = _custom_ids(classic) + _custom_ids(general) + _custom_ids(forever)
    assert len(all_ids) == len(set(all_ids))
    assert _custom_ids(forever) == ["wow_panel_v2:forever"]
    assert set(_custom_ids(general)) == {
        "wow_panel_v2:help",
        "wow_panel_v2:champion",
        "wow_panel_v2:raider",
    }
    assert "wow_panel_v2:raider" not in _custom_ids(classic)
    for view in (classic, general, forever):
        assert view.is_persistent()
        assert len(list(view.walk_children())) + 1 <= 40
        assert len(_all_texts(view)) < 4000


def test_forever_panel_shows_counts_and_total():
    view = wow_cog_mod.WoWPanelLayoutView(
        _cog(), variant="forever", forever_counts=({HORDE_HC: 12}, 41)
    )
    text = _all_texts(view)
    assert "**12**" in text and "**41**" in text


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
    tmp_path, patch_logged_task
):
    cog = await _cog_with_db(tmp_path, patch_logged_task)
    channel = _Channel()

    await cog.publish_all_panels(channel)

    assert [v for _, v in channel.sent_order] == ["forever", "classic", "general"]
    first_ids = [i for i, _ in channel.sent_order]

    await cog.publish_all_panels(channel)  # restart: edit, don't repost

    assert [i for i, _ in channel.sent_order] == first_ids
    assert all(channel.messages[i].edits for i in first_ids)


@pytest.mark.asyncio
async def test_layout_change_replaces_the_old_single_panel(tmp_path, patch_logged_task):
    cog = await _cog_with_db(tmp_path, patch_logged_task)
    channel = _Channel()
    old = _Message(7)
    channel.messages[7] = old
    await cog.data.set_setting("panel_message_id", "7")  # pre-split layout

    await cog.publish_all_panels(channel)

    assert old.deleted is True
    assert await cog.data.get_setting("panel_message_id") != "7"
    assert len(channel.sent_order) == 3


@pytest.mark.asyncio
async def test_only_forever_role_changes_schedule_a_counter_refresh(
    tmp_path, patch_logged_task
):
    cog = await _cog_with_db(tmp_path, patch_logged_task)
    cog._schedule_forever_refresh = MagicMock()

    def member(role_ids):
        m = MagicMock()
        roles = []
        for rid in role_ids:
            r = MagicMock()
            r.id = rid
            roles.append(r)
        m.roles = roles
        return m

    await cog.on_member_update(member([]), member([42]))
    cog._schedule_forever_refresh.assert_not_called()

    await cog.on_member_update(member([]), member([HORDE_HC]))
    cog._schedule_forever_refresh.assert_called_once()
    assert HORDE_HC in FACTION_ROLE_IDS and len(FACTION_ROLE_IDS) == len(FOREVER_ROLES)


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
