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
    signup = await data.get_signup(1)
    assert signup is not None
    assert signup.character_name == "Grimjaw"
    assert signup.post_id is None

    await data.set_signup_post(1, 999)
    assert (await data.get_signup(1)).post_id == 999
    by_post = await data.get_signup_by_post(999)
    assert by_post is not None and by_post.discord_user_id == 1

    # Upsert replaces and resets the post id.
    await data.upsert_signup(1, "id:11", "Nightblade", "soulseeker", "we_abend", "hi")
    refreshed = await data.get_signup(1)
    assert refreshed.character_key == "id:11"
    assert refreshed.note == "hi"
    assert refreshed.post_id is None


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
    assert await data.remove_signup(1) is True
    assert await data.remove_signup(1) is False
    assert await data.get_signup(1) is None


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


async def test_settings_round_trip(tmp_path):
    data = _data(tmp_path)
    assert await data.get_setting("hub_thread_id") is None
    await data.set_setting("hub_thread_id", "123")
    assert await data.get_setting("hub_thread_id") == "123"
    await data.set_setting("hub_thread_id", "456")
    assert await data.get_setting("hub_thread_id") == "456"
