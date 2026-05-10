import pytest
import discord
import pytest_asyncio

from lotus_bot.cogs.wow.cog import WoWCog
from lotus_bot.cogs.wow.data import RosterMember, WoWData
import lotus_bot.cogs.wow.cog as wow_cog_mod
import lotus_bot.log_setup as log_setup


CREATED_COGS = []


@pytest_asyncio.fixture(autouse=True)
async def close_created_cogs():
    yield
    for cog in CREATED_COGS:
        await cog.data.close()
    CREATED_COGS.clear()


class DummyChannel:
    def __init__(self):
        self.sent = []
        self.next_message_id = 555

    async def send(self, msg, **kwargs):
        self.sent.append((msg, kwargs))
        return type("Message", (), {"id": self.next_message_id})()


class ForbiddenChannel:
    async def send(self, msg):
        response = type("Response", (), {"status": 403, "reason": "Forbidden"})()
        raise discord.Forbidden(response, {"message": "Missing Access", "code": 50001})


class DummyBot:
    def __init__(self, channel=None):
        self.channel = channel
        self.views = []

    def get_channel(self, channel_id):
        return self.channel

    def add_view(self, view):
        self.views.append(view)


class DummyPermissions:
    def __init__(self, manage_guild=False):
        self.manage_guild = manage_guild


class DummyUser:
    def __init__(self, uid, manage_guild=False):
        self.id = uid
        self.guild_permissions = DummyPermissions(manage_guild)


class DummyReviewResponse:
    def __init__(self):
        self.messages = []
        self.edits = []

    async def send_message(self, msg, **kwargs):
        self.messages.append((msg, kwargs))

    async def edit_message(self, **kwargs):
        self.edits.append(kwargs)


class DummyReviewInteraction:
    def __init__(self, user, message_id=555):
        self.user = user
        self.message = type("Message", (), {"id": message_id})()
        self.response = DummyReviewResponse()


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
    CREATED_COGS.append(cog)
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
async def test_claim_character_creates_unverified_claim_and_review(
    tmp_path, patch_logged_task
):
    channel = DummyChannel()
    cog = await create_cog(tmp_path, patch_logged_task, channel=channel)
    await cog.data.replace_snapshot([member(name="Lyxendra")])

    result = await cog.claim_character(42, "lyxendra")

    assert result.created is True
    assert result.reason == "created"
    assert result.review_posted is True
    claim = await cog.data.get_claim("id:1")
    assert claim.discord_user_id == 42
    assert claim.status == "unverified"
    assert claim.review_message_id == 555
    assert "<@42>" in channel.sent[0][0]
    assert channel.sent[0][1]["view"] is not None


@pytest.mark.asyncio
async def test_claim_character_rejects_unknown_and_taken(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task, channel=DummyChannel())
    await cog.data.replace_snapshot([member(name="Lyxendra")])

    missing = await cog.claim_character(42, "Unknown")
    assert missing.reason == "not_found"

    created = await cog.claim_character(42, "Lyxendra")
    assert created.reason == "created"
    own_repeat = await cog.claim_character(42, "Lyxendra")
    assert own_repeat.reason == "already_own"
    taken = await cog.claim_character(43, "Lyxendra")
    assert taken.reason == "taken"


@pytest.mark.asyncio
async def test_claim_review_verify_button_marks_claim_verified(
    tmp_path, patch_logged_task
):
    channel = DummyChannel()
    cog = await create_cog(tmp_path, patch_logged_task, channel=channel)
    await cog.data.replace_snapshot([member(name="Lyxendra")])
    await cog.claim_character(42, "Lyxendra")
    view = wow_cog_mod.ClaimReviewView(cog)

    interaction = DummyReviewInteraction(DummyUser(99, manage_guild=True))
    await view.children[0].callback(interaction)

    claim = await cog.data.get_claim("id:1")
    assert claim.status == "verified"
    assert claim.verified_by == 99
    assert interaction.response.edits[0]["view"] is None
    assert "Bestätigt" in interaction.response.edits[0]["content"]


@pytest.mark.asyncio
async def test_claim_review_reject_button_removes_claim(tmp_path, patch_logged_task):
    channel = DummyChannel()
    cog = await create_cog(tmp_path, patch_logged_task, channel=channel)
    await cog.data.replace_snapshot([member(name="Lyxendra")])
    await cog.claim_character(42, "Lyxendra")
    view = wow_cog_mod.ClaimReviewView(cog)

    interaction = DummyReviewInteraction(DummyUser(99, manage_guild=True))
    await view.children[1].callback(interaction)

    assert await cog.data.get_claim("id:1") is None
    assert interaction.response.edits[0]["view"] is None
    assert "Abgelehnt" in interaction.response.edits[0]["content"]


@pytest.mark.asyncio
async def test_claim_review_button_rejects_non_mod(tmp_path, patch_logged_task):
    channel = DummyChannel()
    cog = await create_cog(tmp_path, patch_logged_task, channel=channel)
    await cog.data.replace_snapshot([member(name="Lyxendra")])
    await cog.claim_character(42, "Lyxendra")
    view = wow_cog_mod.ClaimReviewView(cog)

    interaction = DummyReviewInteraction(DummyUser(77, manage_guild=False))
    await view.children[0].callback(interaction)

    claim = await cog.data.get_claim("id:1")
    assert claim.status == "unverified"
    assert interaction.response.messages[0][1]["ephemeral"] is True


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
