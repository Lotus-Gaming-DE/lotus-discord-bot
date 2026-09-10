import discord
import pytest

import lotus_bot.cogs.wow.cog as wow_cog_mod
import lotus_bot.log_setup as log_setup
from lotus_bot.cogs.wow import health
from lotus_bot.cogs.wow.cog import WoWCog
from lotus_bot.cogs.wow.data import WoWData

ALL_TEXT = {name: True for name in health.TEXT_CHANNEL}
ALL_FORUM = {name: True for name in health.FORUM_CHANNEL + health.UPLOADS}


class FakeChannel:
    def __init__(self, channel_id, **permissions):
        self.id = channel_id
        self.mention = f"<#{channel_id}>"
        self._permissions = discord.Permissions(**permissions)

    def permissions_for(self, member):
        return self._permissions


class FakeRole:
    def __init__(self, role_id, position):
        self.id = role_id
        self.position = position


class FakeMe:
    def __init__(self, top_position=50, manage_roles=True):
        self.top_role = FakeRole(0, top_position)
        self.guild_permissions = discord.Permissions(manage_roles=manage_roles)


class FakeGuild:
    def __init__(self, channels=(), roles=(), me=None):
        self._channels = {c.id: c for c in channels}
        self._roles = {r.id: r for r in roles}
        self.me = me or FakeMe()

    def get_channel(self, channel_id):
        return self._channels.get(channel_id)

    def get_role(self, role_id):
        return self._roles.get(role_id)


def test_check_channel_lists_missing_permissions():
    guild = FakeGuild([FakeChannel(1, view_channel=True, send_messages=True)])
    requirement = health.ChannelRequirement("Logs", 1, health.TEXT_CHANNEL)

    check = health.check_channel(guild, requirement)

    assert not check.ok
    assert check.missing == ["embed_links", "read_message_history"]


def test_check_channel_reports_unconfigured_and_missing_channels():
    guild = FakeGuild()

    unconfigured = health.check_channel(
        guild, health.ChannelRequirement("Digest", None, health.TEXT_CHANNEL)
    )
    gone = health.check_channel(
        guild, health.ChannelRequirement("Panel", 99, health.TEXT_CHANNEL)
    )

    assert unconfigured.problem == "nicht eingerichtet"
    assert "nicht gefunden" in gone.problem


def test_role_above_bot_role_is_reported():
    guild = FakeGuild(roles=[FakeRole(7, position=80)], me=FakeMe(top_position=50))

    check = health.check_role(guild, "Gilden-Rolle", 7)

    assert not check.ok
    assert "über der Bot-Rolle" in check.problem


def test_report_flags_missing_manage_roles_and_formats_in_german():
    guild = FakeGuild(
        channels=[FakeChannel(1, view_channel=True, send_messages=True)],
        me=FakeMe(manage_roles=False),
    )

    report = health.build_report(
        guild, [health.ChannelRequirement("Logs", 1, health.TEXT_CHANNEL)], []
    )
    text = health.format_report(report)

    assert not report.ok
    assert "2 Problem(e)" in text
    assert "Rollen verwalten" in text
    assert "Links einbetten" in text


def test_report_is_ok_when_everything_is_allowed():
    guild = FakeGuild(
        channels=[FakeChannel(1, **ALL_TEXT)], roles=[FakeRole(7, position=10)]
    )

    report = health.build_report(
        guild,
        [health.ChannelRequirement("Logs", 1, health.TEXT_CHANNEL)],
        [("Gilden-Rolle", 7)],
    )

    assert report.ok
    assert "alles in Ordnung" in health.format_report(report)


def test_role_requirements_include_champion_roles():
    bot = type(
        "Bot", (), {"data": {"champion": {"roles": [{"name": "Gold", "id": 5}]}}}
    )

    roles = health.role_requirements(bot)

    assert ("Gilden-Rolle", wow_cog_mod.GUILD_ROLE_ID) in roles
    assert ("Champion-Rolle Gold", 5) in roles


class DoctorBot:
    def __init__(self, guild):
        self.main_guild = guild
        self.data = {}
        self.channel = None

    def get_channel(self, channel_id):
        return self.channel

    def get_cog(self, name):
        return None


async def _doctor_cog(tmp_path, patch_logged_task, monkeypatch, guild):
    monkeypatch.setattr(wow_cog_mod.discord, "Guild", FakeGuild)
    patch_logged_task(wow_cog_mod, log_setup)
    cog = WoWCog(DoctorBot(guild))
    cog.data = WoWData(str(tmp_path / "wow.db"))
    return cog


@pytest.mark.asyncio
async def test_startup_check_posts_report_when_something_is_wrong(
    tmp_path, patch_logged_task, monkeypatch
):
    # Nothing is configured/visible → every channel is a problem.
    cog = await _doctor_cog(tmp_path, patch_logged_task, monkeypatch, FakeGuild())
    posted = []

    async def fake_post(content):
        posted.append(content)

    monkeypatch.setattr(cog, "_post_officer_text", fake_post)
    try:
        await cog._startup_health_check()
    finally:
        await cog.data.close()

    assert len(posted) == 1
    assert "Bot-Check" in posted[0]
    assert "Offi-Logs" in posted[0]


@pytest.mark.asyncio
async def test_startup_check_stays_quiet_when_all_is_fine(
    tmp_path, patch_logged_task, monkeypatch
):
    channel_ids = [
        wow_cog_mod.DEFAULT_CLAIM_REVIEW_CHANNEL_ID,
        4242,  # announcement channel configured via /wow setup
        wow_cog_mod.DEFAULT_PANEL_CHANNEL_ID,
        wow_cog_mod.DUNGEONS_FORUM_CHANNEL_ID,
        health.DUO_FORUM_CHANNEL_ID,
        health.MARKETPLACE_FORUM_CHANNEL_ID,
        health.COMMUNITY_PANEL_CHANNEL_ID,
    ]
    guild = FakeGuild(
        channels=[FakeChannel(cid, **ALL_FORUM) for cid in channel_ids],
        roles=[FakeRole(wow_cog_mod.GUILD_ROLE_ID, position=10)],
    )
    cog = await _doctor_cog(tmp_path, patch_logged_task, monkeypatch, guild)
    await cog.set_announcement_channel(4242)
    posted = []

    async def fake_post(content):
        posted.append(content)

    monkeypatch.setattr(cog, "_post_officer_text", fake_post)
    try:
        await cog._startup_health_check()
    finally:
        await cog.data.close()

    assert posted == []
