from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from lotus_bot.cogs.forever import cog as forever
from lotus_bot.cogs.forever.logic import (
    CRIMSON_LAYOUT,
    GUILDS,
    GUILDS_BY_SLUG,
    build_report,
    milestones_reached,
)
from lotus_bot.cogs.forever.registry import (
    GuildMember,
    LinkedCharacter,
    RunAttendance,
    Snapshot,
)
from lotus_bot.cogs.forever.store import ForeverStore

T0 = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
CRIMSON = "crimson-lotus"
ME, OTHER = 111, 222


def char(cid=1, level=30, user=ME, guild=CRIMSON, name=None):
    return LinkedCharacter(cid, 1000 + cid, user, name or f"Char{cid}", level, guild)


def member(cid=1, level=30, rank=7, guild=CRIMSON, name=None):
    return GuildMember(guild, 1000 + cid, name or f"Char{cid}", level, rank)


class FakeRegistry:
    def __init__(self):
        self.linked = []
        self.members = []
        self.runs = []
        self.loaded = {CRIMSON}

    async def snapshot(self, guild_slugs, host):
        return Snapshot(
            tuple(self.linked),
            tuple(self.members),
            tuple(self.runs),
            frozenset(self.loaded),
        )

    async def close(self):
        pass


class FakeChampion:
    def __init__(self):
        self.calls = []
        self.fail = False

    async def update_user_score(self, user_id, delta, reason):
        if self.fail:
            raise RuntimeError("db locked")
        self.calls.append((user_id, delta, reason))
        return delta


class FakeMessage:
    def __init__(self, message_id, content):
        self.id = message_id
        self.content = content


class FakeChannel:
    id = forever.DEFAULT_LOG_CHANNEL_ID

    def __init__(self):
        self.sent = []
        self.kwargs = []

    async def send(self, content, **kwargs):
        self.sent.append(content)
        self.kwargs.append(kwargs)
        return FakeMessage(len(self.sent), content)


class FakeBot:
    main_guild_id = 42

    def __init__(self):
        self.champion = FakeChampion()
        self.channel = FakeChannel()
        self.guild = None

    def get_cog(self, name):
        return self.champion if name == "ChampionCog" else None

    def get_channel(self, channel_id):
        return self.channel if channel_id == forever.DEFAULT_LOG_CHANNEL_ID else None

    def get_guild(self, guild_id):
        return self.guild


@pytest.fixture
async def setup(tmp_path):
    bot = FakeBot()
    registry = FakeRegistry()
    store = ForeverStore(str(tmp_path / "forever.db"))
    cog = forever.ForeverCog(bot, registry, store, start_loop=False)
    yield cog, bot, registry
    await store.close()


def points(bot):
    return sorted((user, delta) for user, delta, _ in bot.champion.calls)


def test_milestones_only_count_after_the_baseline():
    assert milestones_reached(34, 41) == [40]
    assert milestones_reached(45, 45) == []
    assert milestones_reached(19, 60) == [20, 30, 40, 50, 60]


async def test_already_linked_char_starts_now_without_back_pay(setup):
    cog, bot, registry = setup
    registry.linked = [char(level=45)]
    registry.members = [member(level=45)]
    await cog.sync(T0)
    assert bot.champion.calls == []
    assert len(bot.channel.sent) == 1 and f"<@{ME}>" in bot.channel.sent[0]


async def test_level_reached_after_linking_gives_points_once(setup):
    cog, bot, registry = setup
    registry.linked = [char(level=34)]
    await cog.sync(T0)
    registry.linked = [char(level=41)]
    await cog.sync(T0 + timedelta(minutes=10))
    await cog.sync(T0 + timedelta(minutes=20))
    assert points(bot) == [(ME, 10)]


async def test_roster_level_counts_when_it_is_fresher(setup):
    cog, bot, registry = setup
    registry.linked = [char(level=29)]
    await cog.sync(T0)
    registry.members = [member(level=31)]
    await cog.sync(T0)
    assert points(bot) == [(ME, 5)]


async def test_twinks_count_fully(setup):
    cog, bot, registry = setup
    registry.linked = [char(1, level=19), char(2, level=19)]
    await cog.sync(T0)
    registry.linked = [char(1, level=20), char(2, level=20)]
    await cog.sync(T0)
    assert points(bot) == [(ME, 3), (ME, 3)]


async def test_chars_outside_the_lotus_guilds_are_ignored(setup):
    cog, bot, registry = setup
    registry.linked = [char(level=19, guild="other-guild")]
    await cog.sync(T0)
    registry.linked = [char(level=30, guild="other-guild")]
    await cog.sync(T0)
    assert bot.champion.calls == [] and bot.channel.sent == []


async def test_roster_guild_wins_over_the_older_profile(setup):
    cog, bot, registry = setup
    registry.linked = [char(guild=None)]
    registry.members = [member()]
    await cog.sync(T0)
    assert len(bot.channel.sent) == 1


async def test_a_char_that_leaves_is_forgotten_and_starts_anew(setup):
    cog, bot, registry = setup
    registry.linked = [char(level=19)]
    await cog.sync(T0)
    registry.linked = []
    await cog.sync(T0)
    assert await cog.store.tracked() == {}
    registry.linked = [char(level=35)]
    await cog.sync(T0)
    assert bot.champion.calls == []  # neuer Ausgangsstand, keine Nachzahlung


async def test_runs_count_from_the_start_on_this_server(setup):
    cog, bot, registry = setup
    registry.runs = [RunAttendance(1, ME, True, T0 - timedelta(days=1))]
    await cog.sync(T0)
    registry.runs = [
        RunAttendance(1, ME, True, T0 - timedelta(days=1)),
        RunAttendance(2, ME, True, T0 + timedelta(hours=1)),
        RunAttendance(2, OTHER, False, T0 + timedelta(hours=1)),
    ]
    await cog.sync(T0 + timedelta(hours=2))
    await cog.sync(T0 + timedelta(hours=3))
    assert points(bot) == [(ME, 5), (OTHER, 3)]


async def test_failed_points_are_retried(setup):
    cog, bot, registry = setup
    registry.linked = [char(level=19)]
    await cog.sync(T0)
    registry.linked = [char(level=20)]
    bot.champion.fail = True
    await cog.sync(T0)
    bot.champion.fail = False
    await cog.sync(T0)
    assert points(bot) == [(ME, 3)]


def test_report_lists_ranks_that_do_not_match():
    guild = GUILDS_BY_SLUG[CRIMSON]
    members = [
        member(1, rank=4, name="Ohneclaim"),
        member(2, rank=6, name="Neuling"),  # unverbundener Initiate: nicht melden
        member(3, rank=6, name="Verbunden"),
        member(4, rank=4, name="MainEins"),
        member(5, rank=3, name="MainZwei"),
        member(6, rank=5, name="NurTwink", level=50),
    ]
    owner_of = {1003: ME, 1004: OTHER, 1005: OTHER, 1006: ME}
    report = build_report(guild, members, owner_of)
    assert [m.name for m in report.unlinked_ranked] == ["Ohneclaim"]
    assert [(m.name, o) for m, o in report.linked_initiates] == [("Verbunden", ME)]
    assert [(o, [m.name for m in ms]) for o, ms in report.multi_main] == [
        (OTHER, ["MainZwei", "MainEins"])
    ]
    assert [(o, ms[0].name) for o, ms in report.no_main] == [(ME, "NurTwink")]


def test_officer_twink_is_no_second_main():
    guild = GUILDS_BY_SLUG[CRIMSON]
    members = [member(1, rank=1), member(2, rank=CRIMSON_LAYOUT.officer_twink)]
    report = build_report(guild, members, {1001: ME, 1002: ME})
    assert report.empty


async def test_report_skips_guilds_without_a_roster_and_is_posted_once_a_day(setup):
    cog, bot, registry = setup
    registry.members = [
        member(1, rank=4, name="Ohneclaim"),
        member(2, rank=4, name="Silent", guild="silent-lotus"),
    ]
    snapshot = await registry.snapshot([], 0)
    chunks = cog.report_chunks(snapshot)
    assert len(chunks) == 1 and "Ohneclaim" in chunks[0] and "Silent" not in chunks[0]

    morning = datetime(2026, 11, 9, 9, 30, tzinfo=forever.BERLIN)
    assert await cog._report_due(morning - timedelta(hours=2)) is False
    assert await cog._report_due(morning) is True
    await cog.post_report(snapshot, morning)
    assert await cog._report_due(morning + timedelta(hours=1)) is False
    assert await cog._report_due(morning + timedelta(days=1)) is True


async def test_setup_without_database_url_adds_nothing(monkeypatch):
    monkeypatch.delenv("LOTUS_LINK_DATABASE_URL", raising=False)

    class Bot:
        added = []

        async def add_cog(self, cog):
            self.added.append(cog)

    bot = Bot()
    await forever.setup(bot)
    assert bot.added == []


def test_guilds_without_agreed_ranks_get_no_report():
    guild = GUILDS_BY_SLUG["silent-lotus"]
    report = build_report(guild, [member(1, rank=2, guild="silent-lotus")], {})
    assert report.empty and guild.rank_name(0) == "Rang 1"


# ------------------------------------------------- Rollen, Meldungen, Pings

CRIMSON_ROLE = GUILDS_BY_SLUG[CRIMSON].role_id


class FakeRole:
    def __init__(self, role_id):
        self.id = role_id
        self.members = []


class FakeMember:
    def __init__(self, user_id, guild, roles=()):
        self.id = user_id
        self.name = f"user{user_id}"
        self.bot = False
        self.guild = guild
        self.roles = []
        for role in roles:
            self._give(role)

    def _give(self, role):
        self.roles.append(role)
        role.members.append(self)

    async def add_roles(self, role, reason=None):
        self._give(role)

    async def remove_roles(self, role, reason=None):
        self.roles.remove(role)
        role.members.remove(self)


class FakeGuild:
    id = 42

    def __init__(self):
        self.roles = {g.role_id: FakeRole(g.role_id) for g in GUILDS}
        self.members = {}

    def add(self, user_id, *role_ids):
        member = FakeMember(user_id, self, [self.roles[r] for r in role_ids])
        self.members[user_id] = member
        return member

    def get_role(self, role_id):
        return self.roles.get(role_id)

    def get_member(self, user_id):
        return self.members.get(user_id)

    async def fetch_member(self, user_id):
        if user_id in self.members:
            return self.members[user_id]
        raise discord.NotFound(MagicMock(status=404), "unknown member")


@pytest.fixture
async def world(setup):
    cog, bot, registry = setup
    bot.guild = FakeGuild()
    return cog, bot, registry, bot.guild


def holders(guild, slug=CRIMSON):
    return {m.id for m in guild.roles[GUILDS_BY_SLUG[slug].role_id].members}


async def test_link_posts_a_tagged_card_with_button_and_grants_the_role(world):
    cog, bot, registry, guild = world
    guild.add(ME)
    registry.linked = [char(1, name="Main")]
    registry.members = [member(1, rank=4, name="Main")]
    await cog.sync(T0)

    card = bot.channel.sent[0]
    assert "Crimson Lotus" in card and "Main" in card and f"user{ME}" in card
    assert isinstance(bot.channel.kwargs[0]["view"], forever.ClaimNoticeView)
    assert (await cog.store.notice(1))["kind"] == "link"
    assert holders(guild) == {ME}


async def test_role_leaves_with_the_char_but_only_after_the_grace_period(world):
    cog, bot, registry, guild = world
    guild.add(ME)
    guild.add(OTHER, CRIMSON_ROLE)  # hat die Rolle früher selbst gewählt
    registry.linked = [char(1)]
    registry.members = [member(1, rank=4), member(9, rank=7)]
    await cog.sync(T0)
    assert holders(guild) == {ME, OTHER}  # Übergangsfrist läuft

    registry.members = [member(9, rank=7)]  # Main hat die Gilde verlassen
    await cog.sync(T0 + forever.ROLE_GRACE)
    assert holders(guild) == set()


async def test_roles_stay_when_lotus_link_has_no_roster(world):
    cog, bot, registry, guild = world
    guild.add(OTHER, CRIMSON_ROLE)
    registry.members = []
    await cog.sync(T0 + forever.ROLE_GRACE * 2)
    await cog.sync(T0 + forever.ROLE_GRACE * 3)
    assert holders(guild) == {OTHER}


async def test_stale_profile_does_not_keep_the_role(world):
    cog, bot, registry, guild = world
    guild.add(ME)
    registry.linked = [char(1)]  # Profil sagt noch Crimson
    registry.members = [member(2)]  # die Gildenliste nicht mehr
    await cog.sync(T0)
    assert holders(guild) == set()


async def test_guild_leave_is_reported_with_listed_since_and_new_guild(world):
    cog, bot, registry, guild = world
    registry.loaded = {CRIMSON, "silent-lotus"}
    registry.members = [member(1, rank=4, name="Weg"), member(2), member(3)]
    await cog.sync(T0)
    assert bot.channel.sent == []  # erster Stand, nichts melden

    registry.members = [member(2), member(3), member(1, guild="silent-lotus")]
    await cog.sync(T0 + timedelta(days=3))
    left = [m for m in bot.channel.sent if "Weg" in m]
    assert len(left) == 1
    assert "Crimson Lotus" in left[0] and "Silent Lotus" in left[0]
    assert "2026-11-08" in left[0]


async def test_implausible_roster_drop_reports_nothing(world):
    cog, bot, registry, guild = world
    registry.members = [member(i) for i in range(1, 21)]
    await cog.sync(T0)
    registry.members = [member(1)]
    await cog.sync(T0)
    assert bot.channel.sent == []


async def test_discord_leave_asks_to_demote_once_and_rejoin_resets(world):
    cog, bot, registry, guild = world
    guild.add(ME)
    registry.linked = [char(1, name="Main"), char(2, name="Neu")]
    registry.members = [
        member(1, rank=4, name="Main"),
        member(2, rank=CRIMSON_LAYOUT.initiate, name="Neu"),
    ]
    await cog.sync(T0)
    bot.channel.sent.clear()
    bot.channel.kwargs.clear()

    left = guild.members.pop(ME)
    await cog.on_member_remove(left)
    await cog.sync(T0)
    demote = [m for m in bot.channel.sent if "Discord verlassen" in m]
    assert len(demote) == 1 and "Main" in demote[0] and "Neu" not in demote[0]
    assert any(
        isinstance(k.get("view"), forever.DemoteNoticeView) for k in bot.channel.kwargs
    )

    guild.add(ME)
    await cog.sync(T0)
    assert await cog.store.departed() == set()


async def test_report_treats_departed_owners_as_unlinked(setup):
    cog, bot, registry = setup
    registry.linked = [char(1)]
    registry.members = [member(1, rank=4, name="Verwaist")]
    snapshot = await registry.snapshot([], 0)
    assert cog.report_chunks(snapshot) == []
    chunks = cog.report_chunks(snapshot, absent={ME})
    assert "Verwaist" in chunks[0]


async def test_pings_are_collected_hourly_per_guild(world):
    cog, bot, registry, guild = world
    assert await cog.ping_if_due(T0) == 0  # Start: erst sammeln

    registry.linked = [char(1), char(2)]
    registry.members = [member(1), member(2)]
    await cog.sync(T0)
    assert await cog.ping_if_due(T0 + timedelta(minutes=30)) == 0

    assert await cog.ping_if_due(T0 + forever.PING_INTERVAL) == 1
    ping = bot.channel.sent[-1]
    assert f"<@&{CRIMSON_ROLE}>" in ping and "2 neue Claims" in ping
    roles = bot.channel.kwargs[-1]["allowed_mentions"].roles
    assert [r.id for r in roles] == [CRIMSON_ROLE]

    # Schon gepingte Meldungen lösen keinen zweiten Ping aus.
    assert await cog.ping_if_due(T0 + forever.PING_INTERVAL * 2) == 0


def _click(message_id, content, user):
    interaction = MagicMock()
    interaction.message = FakeMessage(message_id, content)
    interaction.user = user
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    return interaction


async def test_done_button_needs_guild_leadership_and_works_once(world):
    cog, bot, registry, guild = world
    registry.linked = [char(1)]
    registry.members = [member(1)]
    await cog.sync(T0)
    outsider = SimpleNamespace(
        id=7, roles=[], guild_permissions=SimpleNamespace(manage_guild=False)
    )
    leader = SimpleNamespace(
        id=8,
        roles=[guild.roles[CRIMSON_ROLE]],
        guild_permissions=SimpleNamespace(manage_guild=False),
    )

    click = _click(1, bot.channel.sent[0], outsider)
    await cog.handle_done(click, "In Offi-Note eingetragen")
    click.response.edit_message.assert_not_awaited()

    click = _click(1, bot.channel.sent[0], leader)
    await cog.handle_done(click, "In Offi-Note eingetragen")
    kwargs = click.response.edit_message.await_args.kwargs
    assert kwargs["view"] is None and "<@8>" in kwargs["content"]
    assert await cog.store.open_count(CRIMSON) == 0

    click = _click(1, bot.channel.sent[0], leader)
    await cog.handle_done(click, "In Offi-Note eingetragen")
    click.response.edit_message.assert_not_awaited()
