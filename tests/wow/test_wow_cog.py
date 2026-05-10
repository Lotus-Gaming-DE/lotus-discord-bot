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
        self.data = {}

    def get_channel(self, channel_id):
        return self.channel

    def add_view(self, view):
        self.views.append(view)


class MultiChannelBot(DummyBot):
    def __init__(self, public_channel=None, officer_channel=None):
        super().__init__(channel=public_channel)
        self.public_channel = public_channel
        self.officer_channel = officer_channel

    def get_channel(self, channel_id):
        if channel_id == wow_cog_mod.DEFAULT_CLAIM_REVIEW_CHANNEL_ID:
            return self.officer_channel
        return self.public_channel


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


def member(
    key="id:1",
    name="Lyxendra",
    level=1,
    class_id=4,
    race_id=8,
    is_ghost=False,
):
    return RosterMember(
        character_key=key,
        character_id=1,
        name=name,
        realm_slug="soulseeker",
        level=level,
        class_id=class_id,
        race_id=race_id,
        faction="HORDE",
        guild_rank=1,
        is_ghost=is_ghost,
    )


def crafting_data():
    return {
        "professions": [
            {"id": "alchemy", "name": {"de": "Alchemie", "en": "Alchemy"}},
            {
                "id": "blacksmithing",
                "name": {"de": "Schmiedekunst", "en": "Blacksmithing"},
            },
        ],
        "items": [
            {
                "id": "item.118",
                "name": {"de": "Schwacher Heiltrank", "en": "Minor Healing Potion"},
            },
            {
                "id": "item.2459",
                "name": {"de": "Swiftnesstrank", "en": "Swiftness Potion"},
            },
            {
                "id": "item.999",
                "name": {"de": "Schwacher Manatrank", "en": "Minor Mana Potion"},
            },
        ],
        "profession_recipes": [
            {
                "id": "recipe.minor_healing_potion",
                "profession_id": "alchemy",
                "creates_item_id": "item.118",
                "required_skill": 1,
                "learned_from": "trainer",
                "hardcore_valid": True,
            },
            {
                "id": "recipe.swiftness_potion",
                "profession_id": "alchemy",
                "creates_item_id": "item.2459",
                "required_skill": 60,
                "learned_from": "recipe",
                "hardcore_valid": True,
            },
        ],
    }


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
    assert [m.level for m in milestones] == [50]


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
async def test_activity_detects_new_character(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    activity = await cog._detect_activity({}, [member(name="Voidok", level=23)])

    assert [m.name for m in activity.new_members] == ["Voidok"]
    assert activity.milestones == []
    assert activity.public_count == 1


@pytest.mark.asyncio
async def test_level_31_no_longer_announces(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    previous = {"id:1": member(level=30)}

    milestones = await cog._detect_milestones(previous, [member(level=31)])

    assert milestones == []


@pytest.mark.asyncio
async def test_digest_posts_one_message_for_multiple_events(
    tmp_path, patch_logged_task, monkeypatch
):
    channel = DummyChannel()
    cog = await create_cog(tmp_path, patch_logged_task, channel=channel)
    await cog.set_announcement_channel(123)
    await cog.data.replace_snapshot([member(level=49)])

    async def fake_roster():
        return [
            member(level=50),
            member(key="id:2", name="Voidok", level=23, class_id=1, race_id=8),
        ]

    monkeypatch.setattr(wow_cog_mod.random, "choice", lambda seq: seq[0])
    cog.fetch_roster = fake_roster
    result = await cog.scan(post=True, persist=True)

    assert result.posted == 1
    assert len(channel.sent) == 1
    msg = channel.sent[0][0]
    assert "Schaut mal" in msg
    assert "Wir begrüßen" in msg
    assert "Troll Krieger Voidok" in msg
    assert "Level **50**" in msg
    assert "Wir gratulieren" in msg


@pytest.mark.asyncio
async def test_digest_mentions_claimed_character(
    tmp_path, patch_logged_task, monkeypatch
):
    channel = DummyChannel()
    cog = await create_cog(tmp_path, patch_logged_task, channel=channel)
    claimed = member(level=39, class_id=1, race_id=8)
    await cog.data.replace_snapshot([claimed])
    await cog.data.create_claim(claimed, 42)
    activity = wow_cog_mod.ActivityDiff(
        new_members=[],
        milestones=[wow_cog_mod.Milestone(member(level=40, class_id=1, race_id=8), 40)],
        deaths=[],
        officer_notes=[],
    )
    monkeypatch.setattr(wow_cog_mod.random, "choice", lambda seq: seq[0])

    msg = await cog.format_activity_digest(activity)

    assert "<@42> hat mit **Troll Krieger Lyxendra** Level **40** erreicht." in msg


@pytest.mark.asyncio
async def test_disappeared_dead_profile_creates_public_death(
    tmp_path, patch_logged_task, monkeypatch
):
    cog = await create_cog(tmp_path, patch_logged_task)
    previous = {"id:1": member(name="Voidok", level=37)}

    async def fake_profile(*args, **kwargs):
        return {"is_ghost": True}

    monkeypatch.setattr(wow_cog_mod, "fetch_character_profile", fake_profile)
    activity = await cog._detect_activity(previous, [])

    assert [d.member.name for d in activity.deaths] == ["Voidok"]
    assert activity.deaths[0].confirmed is True
    assert activity.officer_notes == []
    assert "Level **37** gestorben" in cog._format_death_line(activity.deaths[0])


@pytest.mark.asyncio
async def test_disappeared_alive_profile_creates_officer_note(
    tmp_path, patch_logged_task, monkeypatch
):
    cog = await create_cog(tmp_path, patch_logged_task)
    previous = {"id:1": member(name="Voidok")}

    async def fake_profile(*args, **kwargs):
        return {"is_ghost": False}

    monkeypatch.setattr(wow_cog_mod, "fetch_character_profile", fake_profile)
    activity = await cog._detect_activity(previous, [])

    assert activity.deaths == []
    assert "nicht mehr Teil" in activity.officer_notes[0].message


@pytest.mark.asyncio
async def test_disappeared_unknown_profile_creates_presumed_death(
    tmp_path, patch_logged_task, monkeypatch
):
    cog = await create_cog(tmp_path, patch_logged_task)
    previous = {"id:1": member(name="Voidok", level=42)}

    async def fake_profile(*args, **kwargs):
        raise wow_cog_mod.WoWAPIError("not found", status=404)

    monkeypatch.setattr(wow_cog_mod, "fetch_character_profile", fake_profile)
    activity = await cog._detect_activity(previous, [])

    assert activity.officer_notes == []
    assert [d.member.name for d in activity.deaths] == ["Voidok"]
    assert activity.deaths[0].confirmed is False
    death_line = cog._format_death_line(activity.deaths[0])
    assert "Level **42**" in death_line
    assert "nicht mehr auffindbar" in death_line


@pytest.mark.asyncio
async def test_public_death_from_roster_ghost_is_deduplicated(
    tmp_path, patch_logged_task
):
    cog = await create_cog(tmp_path, patch_logged_task)
    previous = {"id:1": member(is_ghost=False)}
    current = [member(is_ghost=True)]

    activity = await cog._detect_activity(previous, current)
    assert len(activity.deaths) == 1
    await cog._record_public_events(activity)

    activity = await cog._detect_activity(previous, current)
    assert activity.deaths == []


@pytest.mark.asyncio
async def test_only_officer_notes_persist_without_public_channel(
    tmp_path, patch_logged_task, monkeypatch
):
    officer = DummyChannel()
    bot = MultiChannelBot(public_channel=None, officer_channel=officer)
    patch_logged_task(wow_cog_mod, log_setup)
    cog = WoWCog(bot)
    cog.data = WoWData(str(tmp_path / "wow.db"))
    CREATED_COGS.append(cog)
    await cog.data.replace_snapshot([member(name="Voidok")])

    async def fake_roster():
        return []

    async def fake_profile(*args, **kwargs):
        return {"is_ghost": False}

    monkeypatch.setattr(wow_cog_mod, "fetch_character_profile", fake_profile)
    cog.fetch_roster = fake_roster
    result = await cog.scan(post=True, persist=True)

    assert result.posted == 0
    assert "nicht mehr Teil" in officer.sent[0][0]
    assert await cog.data.member_count() == 0


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
async def test_crafting_set_profile_requires_own_claim_or_mod(
    tmp_path, patch_logged_task
):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    await cog.data.replace_snapshot([member(name="Voidok")])
    await cog.claim_character(42, "Voidok")

    own = await cog.set_crafting_profile(42, "Voidok", "Alchemie", 250, "Elixiere")
    assert own.reason == "saved"
    assert own.profession.skill_level == 250

    forbidden = await cog.set_crafting_profile(43, "Voidok", "Alchemie", 260, None)
    assert forbidden.reason == "forbidden"

    mod = await cog.set_crafting_profile(
        43, "Voidok", "Alchemy", 260, None, is_mod=True
    )
    assert mod.reason == "saved"
    assert mod.profession.skill_level == 260


@pytest.mark.asyncio
async def test_crafting_search_finds_claimed_trainer_recipe(
    tmp_path, patch_logged_task
):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    await cog.data.replace_snapshot([member(name="Voidok")])
    claim, _ = await cog.data.create_claim(member(name="Voidok"), 42)
    await cog.data.set_character_profession(claim, "alchemy", 75)

    result = await cog.search_crafting("Schwacher Heiltrank")

    assert result.status == "ok"
    assert result.crafters[0].character_name == "Voidok"
    assert "Voidok" in cog.format_crafting_search_result(result)


@pytest.mark.asyncio
async def test_crafting_search_ignores_unclaimed_crafters(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    await cog.data.replace_snapshot([member(name="Voidok")])
    claim, _ = await cog.data.create_claim(member(name="Voidok"), 42)
    await cog.data.set_character_profession(claim, "alchemy", 75)
    await cog.data.remove_claim(claim.character_key)

    result = await cog.search_crafting("Minor Healing Potion")

    assert result.status == "no_crafter"


@pytest.mark.asyncio
async def test_crafting_search_reports_manual_recipe_and_ambiguity(
    tmp_path, patch_logged_task
):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}

    manual = await cog.search_crafting("Swiftnesstrank")
    ambiguous = await cog.search_crafting("Schwacher")

    assert manual.status == "manual_recipe"
    assert "kein Trainerrezept" in cog.format_crafting_search_result(manual)
    assert ambiguous.status == "ambiguous_item"


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
