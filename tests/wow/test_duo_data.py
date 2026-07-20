import pytest

from lotus_bot.cogs.wow.duo_data import DuoData

pytestmark = pytest.mark.asyncio


def _data(tmp_path):
    return DuoData(str(tmp_path / "duo.db"))


async def test_signup_upsert_get_and_by_post(tmp_path):
    data = _data(tmp_path)
    await data.upsert_signup(
        1, "id:10", "Grimjaw", "soulseeker", "wd_abend,spaet", None
    )
    signup = await data.get_signup("id:10")
    assert signup is not None
    assert signup.character_name == "Grimjaw"
    assert signup.discord_user_id == 1
    assert signup.post_id is None

    await data.set_signup_post("id:10", 999)
    assert (await data.get_signup("id:10")).post_id == 999
    by_post = await data.get_signup_by_post(999)
    assert by_post is not None and by_post.character_key == "id:10"

    # Re-upserting the SAME character replaces and resets the post id.
    await data.upsert_signup(1, "id:10", "Grimjaw", "soulseeker", "we_abend", "hi")
    refreshed = await data.get_signup("id:10")
    assert refreshed.note == "hi"
    assert refreshed.post_id is None


async def test_signup_new_fields_round_trip(tmp_path):
    data = _data(tmp_path)
    await data.upsert_signup(
        1,
        "id:10",
        "Grimjaw",
        "soulseeker",
        "wd_abend",
        "meist mittwochs",
        kind="reroll",
        self_found=True,
        prefs="selffound,push",
        intensity="grind",
    )
    s = await data.get_signup("id:10")
    assert s.kind == "reroll"
    assert s.self_found is True
    assert s.prefs == "selffound,push"
    assert s.intensity == "grind"
    assert s.note == "meist mittwochs"
    # Defaults when omitted.
    await data.upsert_signup(2, "id:20", "Plain", "r", "we_abend", None)
    plain = await data.get_signup("id:20")
    assert plain.kind == "char"
    assert plain.self_found is False
    assert plain.intensity is None


async def test_stale_signups_filters_by_cutoff(tmp_path):
    data = _data(tmp_path)
    await data.upsert_signup(1, "id:1", "A", "r", "wd_abend", None)
    # Everything is stale relative to a far-future cutoff, nothing to an old one.
    assert {s.character_key for s in await data.stale_signups("2999-01-01")} == {"id:1"}
    assert await data.stale_signups("2000-01-01") == []


async def test_one_signup_per_character_multiple_alts(tmp_path):
    data = _data(tmp_path)
    # Same player, two different alts searching at once.
    await data.upsert_signup(1, "id:10", "Grimjaw", "r", "wd_abend", None)
    await data.upsert_signup(1, "id:11", "Nightblade", "r", "we_abend", None)
    mine = await data.signups_for_user(1)
    assert {s.character_key for s in mine} == {"id:10", "id:11"}
    assert await data.signup_count() == 2


async def test_list_signups_excludes_user(tmp_path):
    data = _data(tmp_path)
    await data.upsert_signup(1, "id:1", "A", "r", "wd_abend", None)
    await data.upsert_signup(2, "id:2", "B", "r", "wd_abend", None)
    all_signups = await data.list_signups()
    assert {s.discord_user_id for s in all_signups} == {1, 2}
    without_1 = await data.list_signups(exclude_user_id=1)
    assert {s.discord_user_id for s in without_1} == {2}
    assert await data.signup_count() == 2


async def test_remove_signup(tmp_path):
    data = _data(tmp_path)
    await data.upsert_signup(1, "id:1", "A", "r", "wd_abend", None)
    assert await data.remove_signup("id:1") is True
    assert await data.remove_signup("id:1") is False
    assert await data.get_signup("id:1") is None


async def test_team_lifecycle_and_lookups(tmp_path):
    data = _data(tmp_path)
    team = await data.create_team(
        "Team Phoenix",
        555,
        [(1, "id:1", "Ashfist"), (2, "id:2", "Nightblade")],
    )
    assert team.status == "active"
    assert team.name == "Team Phoenix"

    assert (await data.get_team_by_thread(555)).team_id == team.team_id
    assert (await data.active_team_for_user(1)).team_id == team.team_id
    assert (await data.active_team_for_user(2)).team_id == team.team_id
    assert (await data.active_team_by_character("id:2")).team_id == team.team_id

    members = await data.team_members(team.team_id)
    assert {m.discord_user_id for m in members} == {1, 2}

    assert await data.used_team_names() == {"Team Phoenix"}
    assert len(await data.active_teams()) == 1


async def test_swap_member_character(tmp_path):
    data = _data(tmp_path)
    team = await data.create_team("T", 1, [(1, "id:1", "Old"), (2, "id:2", "Keep")])
    await data.swap_member_character(team.team_id, 1, "id:99", "Fresh")
    members = {m.discord_user_id: m for m in await data.team_members(team.team_id)}
    assert members[1].character_key == "id:99"
    assert members[1].character_name == "Fresh"
    assert members[2].character_key == "id:2"
    # The new character is now discoverable, the old one is not.
    assert (await data.active_team_by_character("id:99")).team_id == team.team_id
    assert await data.active_team_by_character("id:1") is None


async def test_disband_hides_team_from_active_lookups(tmp_path):
    data = _data(tmp_path)
    team = await data.create_team("T", 1, [(1, "id:1", "A"), (2, "id:2", "B")])
    await data.disband_team(team.team_id)
    assert await data.active_team_for_user(1) is None
    assert await data.active_team_by_character("id:1") is None
    assert await data.used_team_names() == set()
    assert await data.active_teams() == []
    # Row still exists for history.
    assert (await data.get_team(team.team_id)).status == "disbanded"


async def test_duo_milestone_dedup(tmp_path):
    data = _data(tmp_path)
    team = await data.create_team("T", 1, [(1, "id:1", "A"), (2, "id:2", "B")])
    assert await data.duo_milestone_exists(team.team_id, 40) is False
    assert await data.record_duo_milestone(team.team_id, 40) is True
    assert await data.duo_milestone_exists(team.team_id, 40) is True
    # Second call is a no-op (already recorded).
    assert await data.record_duo_milestone(team.team_id, 40) is False


async def test_active_teams_for_user_lists_all(tmp_path):
    data = _data(tmp_path)
    # Player 1 is in two teams with two different alts.
    t1 = await data.create_team("Team A", 10, [(1, "id:1a", "Main"), (2, "id:2", "P2")])
    t2 = await data.create_team("Team B", 20, [(1, "id:1b", "Alt"), (3, "id:3", "P3")])
    teams = await data.active_teams_for_user(1)
    assert {t.team_id for t in teams} == {t1.team_id, t2.team_id}
    # Each character resolves to its own team.
    assert (await data.active_team_by_character("id:1a")).team_id == t1.team_id
    assert (await data.active_team_by_character("id:1b")).team_id == t2.team_id
    # Disbanding one leaves the other.
    await data.disband_team(t1.team_id)
    remaining = await data.active_teams_for_user(1)
    assert [t.team_id for t in remaining] == [t2.team_id]


async def test_migration_from_user_keyed_signups(tmp_path):
    import aiosqlite

    db_path = str(tmp_path / "duo.db")
    # Simulate the first-release schema: duo_signups keyed on discord_user_id.
    conn = await aiosqlite.connect(db_path)
    await conn.execute("""
        CREATE TABLE duo_signups (
            discord_user_id INTEGER PRIMARY KEY,
            character_key TEXT NOT NULL,
            character_name TEXT NOT NULL,
            realm_slug TEXT NOT NULL,
            time_windows TEXT NOT NULL,
            note TEXT,
            post_id INTEGER,
            created_at TEXT NOT NULL
        )
        """)
    await conn.execute(
        "INSERT INTO duo_signups VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (1, "id:99", "Legacy", "soulseeker", "wd_abend", None, 777, "2026-01-01"),
    )
    await conn.commit()
    await conn.close()

    data = DuoData(db_path)
    await data.init_db()  # triggers migration
    # Row survived and is now addressable by character_key.
    migrated = await data.get_signup("id:99")
    assert migrated is not None
    assert migrated.discord_user_id == 1
    assert migrated.post_id == 777
    # New per-character behaviour works post-migration.
    await data.upsert_signup(1, "id:100", "Second", "r", "we_abend", None)
    assert await data.signup_count() == 2
    await data.close()


async def test_settings_round_trip(tmp_path):
    data = _data(tmp_path)
    assert await data.get_setting("hub_thread_id") is None
    await data.set_setting("hub_thread_id", "123")
    assert await data.get_setting("hub_thread_id") == "123"
    await data.set_setting("hub_thread_id", "456")
    assert await data.get_setting("hub_thread_id") == "456"
