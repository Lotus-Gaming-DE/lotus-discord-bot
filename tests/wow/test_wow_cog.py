import pytest
import discord

from lotus_bot.cogs.wow.cog import WoWCog
from lotus_bot.cogs.wow.data import RosterMember, WoWData
import lotus_bot.cogs.wow.cog as wow_cog_mod
import lotus_bot.log_setup as log_setup


class DummyChannel:
    def __init__(self):
        self.sent = []

    async def send(self, msg):
        self.sent.append(msg)


class ForbiddenChannel:
    async def send(self, msg):
        response = type("Response", (), {"status": 403, "reason": "Forbidden"})()
        raise discord.Forbidden(response, {"message": "Missing Access", "code": 50001})


class DummyBot:
    def __init__(self, channel=None):
        self.channel = channel

    def get_channel(self, channel_id):
        return self.channel


def member(key="id:1", name="Lyxendra", level=1):
    return RosterMember(
        character_key=key,
        character_id=1,
        name=name,
        realm_slug="soulseeker",
        level=level,
        class_id=4,
        race_id=8,
        faction="HORDE",
        guild_rank=1,
    )


async def create_cog(tmp_path, patch_logged_task, channel=None):
    patch_logged_task(wow_cog_mod, log_setup)
    cog = WoWCog(DummyBot(channel=channel))
    cog.data = WoWData(str(tmp_path / "wow.db"))
    return cog


@pytest.mark.asyncio
async def test_new_character_does_not_create_milestone(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    milestones = await cog._detect_milestones({}, [member(level=60)])
    assert milestones == []


@pytest.mark.asyncio
async def test_level_increase_below_milestone_is_ignored(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    previous = {"id:1": member(level=30)}
    milestones = await cog._detect_milestones(previous, [member(level=31)])
    assert milestones == []


@pytest.mark.asyncio
async def test_level_increase_crossing_milestones(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    previous = {"id:1": member(level=49)}
    milestones = await cog._detect_milestones(previous, [member(level=52)])
    assert [m.level for m in milestones] == [50, 51, 52]


@pytest.mark.asyncio
async def test_duplicate_milestone_is_ignored(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    await cog.data.record_milestone("id:1", 50)
    previous = {"id:1": member(level=49)}
    milestones = await cog._detect_milestones(previous, [member(level=50)])
    assert milestones == []


@pytest.mark.asyncio
async def test_missing_channel_does_not_crash(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task, channel=None)
    await cog.set_announcement_channel(123)
    posted = await cog._post_milestones([wow_cog_mod.Milestone(member(), 30)])
    assert posted == 0


@pytest.mark.asyncio
async def test_scan_dry_run_does_not_post_or_persist(tmp_path, patch_logged_task):
    channel = DummyChannel()
    cog = await create_cog(tmp_path, patch_logged_task, channel=channel)
    await cog.data.replace_snapshot([member(level=49)])

    async def fake_roster():
        return [member(level=50)]

    cog.fetch_roster = fake_roster
    result = await cog.scan(post=False, persist=False)

    assert len(result.milestones) == 1
    assert result.posted == 0
    assert channel.sent == []
    snapshot = await cog.data.get_snapshot()
    assert snapshot["id:1"].level == 49


@pytest.mark.asyncio
async def test_scan_missing_access_does_not_crash_or_persist(
    tmp_path, patch_logged_task
):
    cog = await create_cog(tmp_path, patch_logged_task, channel=ForbiddenChannel())
    await cog.set_announcement_channel(123)
    await cog.data.replace_snapshot([member(level=49)])

    async def fake_roster():
        return [member(level=50)]

    cog.fetch_roster = fake_roster
    result = await cog.scan(post=True, persist=True)

    assert len(result.milestones) == 1
    assert result.posted == 0
    snapshot = await cog.data.get_snapshot()
    assert snapshot["id:1"].level == 49
