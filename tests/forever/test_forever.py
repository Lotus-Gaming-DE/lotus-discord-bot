from datetime import datetime, timedelta, timezone

import pytest

from lotus_bot.cogs.forever import cog as forever
from lotus_bot.cogs.forever.logic import (
    CRIMSON_LAYOUT,
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


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content, **kwargs):
        self.sent.append(content)


class FakeBot:
    main_guild_id = 42

    def __init__(self):
        self.champion = FakeChampion()
        self.channel = FakeChannel()

    def get_cog(self, name):
        return self.champion if name == "ChampionCog" else None

    def get_channel(self, channel_id):
        return self.channel if channel_id == forever.DEFAULT_LOG_CHANNEL_ID else None


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
