from types import SimpleNamespace

import pytest

from lotus_bot.cogs.forever import overview
from lotus_bot.cogs.forever import slash_commands as cmds
from lotus_bot.cogs.forever.registry import GuildMember, LinkedCharacter, Snapshot

CRIMSON, SILENT = "crimson-lotus", "silent-lotus"
ME, OTHER, STRANGER = 111, 222, 333


def linked(cid, user, name, level=30, guild=CRIMSON):
    return LinkedCharacter(cid, 1000 + cid, user, name, level, guild)


def member(cid, name, rank=4, level=30, guild=CRIMSON, cls="warrior"):
    return GuildMember(guild, 1000 + cid, name, level, rank, cls)


def snap(linked_chars=(), members=(), loaded=(CRIMSON,)):
    return Snapshot(tuple(linked_chars), tuple(members), (), frozenset(loaded))


SNAP = snap(
    linked_chars=[
        linked(1, ME, "Voidok", level=40),
        linked(2, ME, "Voidtwink", guild=SILENT),
        linked(3, OTHER, "Fremdling", guild="other-guild"),
    ],
    members=[
        member(1, "Voidok", rank=4, level=42),
        member(4, "Ohneclaim", rank=5),
        member(5, "Neuling", rank=6),
    ],
)


# --------------------------------------------------------------- logik


def test_roster_wins_over_the_profile_but_level_takes_the_higher():
    info = overview.characters(SNAP)[1001]
    assert (info.owner, info.level, info.rank, info.guild_slug) == (ME, 42, 4, CRIMSON)


def test_profile_guild_is_dropped_when_the_roster_no_longer_lists_the_char():
    s = snap([linked(9, ME, "Weg", guild=CRIMSON)], [])
    assert overview.characters(s)[1009].guild_slug is None


def test_search_finds_both_linked_and_unlinked_chars_exact_first():
    s = snap(
        [linked(1, ME, "Void"), linked(2, OTHER, "Voidwalker")],
        [member(1, "Void"), member(2, "Voidwalker")],
    )
    hits = overview.find_characters("VOID", s)
    assert [h.name for h in hits] == ["Void", "Voidwalker"]
    assert overview.find_characters("ohne", SNAP)[0].owner is None
    assert overview.find_characters("  ", SNAP) == []


def test_search_respects_the_visibility_filter():
    hits = overview.find_characters("fremd", SNAP, lambda i: i.lotus_guild is not None)
    assert hits == []


def test_search_is_capped():
    s = snap(members=[member(i, f"Alt{i}") for i in range(30)])
    assert len(overview.find_characters("alt", s)) == overview.MAX_HITS


def test_player_lists_all_own_chars_lotus_guilds_first():
    chars = overview.characters_of(ME, SNAP)
    assert [c.name for c in chars] == ["Voidtwink", "Voidok"]  # Silent vor Crimson


def test_guild_stats_count_chars_links_players_and_mains():
    [crimson] = overview.guild_stats(SNAP)
    assert (crimson.chars, crimson.linked, crimson.players) == (3, 1, 1)
    assert (crimson.mains, crimson.mains_linked) == (1, 1)
    assert crimson.percent == 33


def test_people_who_left_discord_count_as_unlinked():
    [crimson] = overview.guild_stats(SNAP, absent={ME})
    assert crimson.linked == 0 and crimson.players == 0


def test_guilds_without_roster_are_left_out():
    assert overview.guild_stats(snap(loaded=())) == []
    empty = overview.GuildStats(overview.GUILDS[0], 0, 0, 0, 0, 0)
    assert empty.percent == 0


def test_texts_show_owner_only_where_known():
    name_of = lambda uid: f"<@{uid}>"  # noqa: E731
    single = overview.search_text(
        "voidok", overview.find_characters("voidok", SNAP), SNAP, name_of
    )
    assert f"<@{ME}>" in single and "Voidtwink" in single
    unlinked = overview.search_text(
        "ohneclaim", overview.find_characters("ohneclaim", SNAP), SNAP, name_of
    )
    assert "<@" not in unlinked
    many = overview.search_text(
        "void", overview.find_characters("void", SNAP), SNAP, name_of
    )
    assert many.count(f"<@{ME}>") == 2
    assert "Kein" in overview.search_text("x", [], SNAP, name_of)
    assert "keinen" in overview.player_text("<@1>", [])


def test_guild_label_variants():
    infos = overview.characters(SNAP)
    assert "Crimson Lotus, Member" in overview.guild_label(infos[1001])
    assert overview.guild_label(infos[1003]) == "Other Guild"
    s = snap([linked(7, ME, "Solo", guild=None)])
    assert overview.guild_label(overview.characters(s)[1007]) == "ohne Gilde"


def test_stats_lines_details_only_for_leaders():
    stats = overview.guild_stats(SNAP)
    public = overview.stats_lines(stats, details=False)[0]
    leader = overview.stats_lines(stats, details=True)[0]
    assert "Spieler" not in public and "Spieler" in leader


def test_chunks_split_long_texts():
    text = "\n".join("x" * 100 for _ in range(50))
    chunks = cmds._chunks(text)
    assert len(chunks) > 1 and all(len(c) <= 1900 for c in chunks)


# ------------------------------------------------------------- befehle


class FakeChannel:
    def __init__(self, viewers):
        self.viewers = viewers

    def permissions_for(self, user):
        return SimpleNamespace(view_channel=user.id in self.viewers)


class FakeStore:
    async def departed(self):
        return set()


class FakeCog:
    def __init__(self, snapshot, viewers=(), members=(ME,)):
        self._last_snapshot = snapshot
        self.channel = FakeChannel(set(viewers))
        self.store = FakeStore()
        self.members = set(members)
        self.synced = 0

    async def _channel(self):
        return self.channel

    async def sync(self):
        self.synced += 1
        return SNAP

    def _member(self, user_id):
        return object() if user_id in self.members else None

    def who(self, user_id):
        return f"<@{user_id}>"


class FakeResponse:
    def __init__(self):
        self.messages = []
        self.deferred = False

    async def send_message(self, content, **kwargs):
        self.messages.append(content)

    async def defer(self, **kwargs):
        self.deferred = True


class FakeFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, content, **kwargs):
        assert kwargs["ephemeral"] is True
        self.messages.append(content)


def interaction(cog, user_id=ME, admin=False):
    perms = SimpleNamespace(manage_guild=admin)
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id, guild_permissions=perms),
        client=SimpleNamespace(get_cog=lambda name: cog),
        response=FakeResponse(),
        followup=FakeFollowup(),
    )


def text(inter):
    return "\n".join(inter.response.messages + inter.followup.messages)


async def test_overview_is_public_but_details_only_for_leaders():
    cog = FakeCog(SNAP, viewers={OTHER})
    everyone = interaction(cog, user_id=ME)
    await cmds.uebersicht.callback(everyone)
    leader = interaction(cog, user_id=OTHER)
    await cmds.uebersicht.callback(leader)
    assert "Crimson" in text(everyone) and "Spieler" not in text(everyone)
    assert "Spieler" in text(leader)


async def test_lookups_are_for_leaders_only():
    cog = FakeCog(SNAP)
    inter = interaction(cog)
    await cmds.charakter.callback(inter, "voidok")
    assert not inter.response.deferred and "Gildenleitungen" in text(inter)
    assert await cmds.charakter_autocomplete(inter, "void") == []


async def test_admin_finds_owner_and_other_chars():
    cog = FakeCog(SNAP)
    inter = interaction(cog, user_id=OTHER, admin=True)
    await cmds.charakter.callback(inter, "voidok")
    assert f"<@{ME}>" in text(inter) and "Voidtwink" in text(inter)


async def test_chars_of_strangers_from_other_servers_stay_hidden():
    cog = FakeCog(SNAP, members=(ME,))
    inter = interaction(cog, admin=True)
    await cmds.charakter.callback(inter, "fremdling")
    assert "Kein Charakter" in text(inter)


async def test_player_lookup_lists_linked_chars():
    cog = FakeCog(SNAP, viewers={OTHER})
    inter = interaction(cog, user_id=OTHER)
    await cmds.spieler.callback(inter, SimpleNamespace(id=ME))
    assert "Voidok" in text(inter) and "Voidtwink" in text(inter)


async def test_autocomplete_offers_unique_names():
    cog = FakeCog(SNAP, viewers={ME})
    inter = interaction(cog)
    choices = await cmds.charakter_autocomplete(inter, "void")
    assert [c.value for c in choices] == ["Voidtwink", "Voidok"]
    assert await cmds.charakter_autocomplete(inter, "v") == []


async def test_missing_snapshot_is_fetched_and_failures_are_reported():
    cog = FakeCog(None, viewers={ME})
    inter = interaction(cog)
    await cmds.uebersicht.callback(inter)
    assert cog.synced == 1 and "Crimson" in text(inter)

    async def broken():
        raise RuntimeError("down")

    cog = FakeCog(None)
    cog.sync = broken
    inter = interaction(cog)
    await cmds.uebersicht.callback(inter)
    assert "antwortet" in text(inter)


async def test_without_cog_or_roster_the_reply_says_so():
    inter = interaction(None)
    await cmds.uebersicht.callback(inter)
    assert "nicht angebunden" in text(inter)
    inter = interaction(FakeCog(snap(loaded=())))
    await cmds.uebersicht.callback(inter)
    assert "Noch keine" in text(inter)


@pytest.mark.parametrize("channel", [None, object()])
async def test_no_log_channel_means_no_leader(channel):
    cog = FakeCog(SNAP)

    async def get():
        return channel

    cog._channel = get
    assert await cmds.is_leader(interaction(cog), cog) is False


async def test_package_setup_registers_the_forever_commands(monkeypatch):
    import lotus_bot.cogs.forever as package

    monkeypatch.delenv("LOTUS_LINK_DATABASE_URL", raising=False)
    added = []
    bot = SimpleNamespace(
        main_guild=object(),
        tree=SimpleNamespace(add_command=lambda cmd, guild: added.append(cmd.name)),
    )
    await package.setup(bot)
    assert added == ["forever"]
