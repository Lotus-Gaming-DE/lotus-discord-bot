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


class DummyPanelMessage:
    def __init__(self, message_id):
        self.id = message_id
        self.edits = []

    async def edit(self, **kwargs):
        self.edits.append(kwargs)


class DummyPanelChannel(DummyChannel):
    id = 1463577361562992807

    def __init__(self, existing_message=None):
        super().__init__()
        self.existing_message = existing_message
        self.fetches = []

    async def fetch_message(self, message_id):
        self.fetches.append(message_id)
        if self.existing_message is None:
            response = type("Response", (), {"status": 404, "reason": "Not Found"})()
            raise discord.NotFound(response, {"message": "Unknown Message"})
        return self.existing_message


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
        self.modals = []

    async def send_message(self, msg, **kwargs):
        self.messages.append((msg, kwargs))

    async def edit_message(self, **kwargs):
        self.edits.append(kwargs)

    async def send_modal(self, modal):
        self.modals.append(modal)


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
            {
                "id": "alchemy",
                "type": "primary",
                "name": {"de": "Alchemie", "en": "Alchemy"},
            },
            {
                "id": "blacksmithing",
                "type": "primary",
                "name": {"de": "Schmiedekunst", "en": "Blacksmithing"},
            },
            {
                "id": "engineering",
                "type": "primary",
                "name": {"de": "Ingenieurskunst", "en": "Engineering"},
            },
            {
                "id": "cooking",
                "type": "secondary",
                "name": {"de": "Kochkunst", "en": "Cooking"},
            },
            {
                "id": "fishing",
                "type": "secondary",
                "name": {"de": "Angeln", "en": "Fishing"},
            },
            {
                "id": "first-aid",
                "type": "secondary",
                "name": {"de": "Erste Hilfe", "en": "First Aid"},
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
        "spells": [
            {
                "id": "spell.2330",
                "name": {
                    "de": "Schwacher Heiltrank herstellen",
                    "en": "Minor Healing Potion",
                },
            },
            {
                "id": "spell.2335",
                "name": {
                    "de": "Swiftnesstrank herstellen",
                    "en": "Swiftness Potion",
                },
            },
        ],
        "profession_recipes": [
            {
                "id": "recipe.minor_healing_potion",
                "profession_id": "alchemy",
                "spell_id": "spell.2330",
                "creates_item_id": "item.118",
                "required_skill": 1,
                "learned_from": "trainer",
                "hardcore_valid": True,
            },
            {
                "id": "recipe.swiftness_potion",
                "profession_id": "alchemy",
                "spell_id": "spell.2335",
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
async def test_panel_publish_creates_and_stores_message(tmp_path, patch_logged_task):
    channel = DummyPanelChannel()
    cog = await create_cog(tmp_path, patch_logged_task)

    result = await cog.publish_panel(channel)

    assert result.created is True
    assert result.channel_id == channel.id
    assert result.message_id == 555
    assert "Black Lotus WoW-Hub" in channel.sent[0][0]
    assert channel.sent[0][1]["view"] is not None
    assert await cog.data.get_setting("panel_channel_id") == str(channel.id)
    assert await cog.data.get_setting("panel_message_id") == "555"


@pytest.mark.asyncio
async def test_panel_publish_updates_existing_message(tmp_path, patch_logged_task):
    existing = DummyPanelMessage(777)
    channel = DummyPanelChannel(existing)
    cog = await create_cog(tmp_path, patch_logged_task)
    await cog.data.set_setting("panel_message_id", "777")

    result = await cog.publish_panel(channel)

    assert result.created is False
    assert channel.fetches == [777]
    assert channel.sent == []
    assert "Black Lotus WoW-Hub" in existing.edits[0]["content"]
    assert existing.edits[0]["view"] is not None


@pytest.mark.asyncio
async def test_panel_claim_button_opens_search_modal(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    view = wow_cog_mod.WoWPanelView(cog)
    interaction = DummyReviewInteraction(DummyUser(42))

    await view.children[0].callback(interaction)

    assert isinstance(
        interaction.response.modals[0], wow_cog_mod.PanelCharacterSearchModal
    )


@pytest.mark.asyncio
async def test_panel_professions_requires_claim(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    view = wow_cog_mod.WoWPanelView(cog)
    interaction = DummyReviewInteraction(DummyUser(42))

    await view.children[2].callback(interaction)

    assert "keinen Charakter" in interaction.response.messages[0][0]
    assert interaction.response.messages[0][1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_panel_my_chars_lists_claims(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    await cog.data.replace_snapshot([member(name="Voidok")])
    await cog.data.create_claim(member(name="Voidok"), 42)
    view = wow_cog_mod.WoWPanelView(cog)
    interaction = DummyReviewInteraction(DummyUser(42))

    await view.children[1].callback(interaction)

    assert "Voidok" in interaction.response.messages[0][0]
    assert interaction.response.messages[0][1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_panel_character_search_limits_matches(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    await cog.data.replace_snapshot(
        [member(key=f"id:{idx}", name=f"Vochar{idx}") for idx in range(30)]
    )
    modal = wow_cog_mod.PanelCharacterSearchModal(cog)
    modal.query._value = "Vo"
    interaction = DummyReviewInteraction(DummyUser(42))

    await modal.on_submit(interaction)

    msg, kwargs = interaction.response.messages[0]
    assert "aus" in msg
    assert kwargs["ephemeral"] is True
    assert len(kwargs["view"].children[0].options) == 25


@pytest.mark.asyncio
async def test_panel_character_search_reports_no_match(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    modal = wow_cog_mod.PanelCharacterSearchModal(cog)
    modal.query._value = "Voidok"
    interaction = DummyReviewInteraction(DummyUser(42))

    await modal.on_submit(interaction)

    assert "Kein Black-Lotus-Charakter" in interaction.response.messages[0][0]


@pytest.mark.asyncio
async def test_panel_roster_select_claims_character(tmp_path, patch_logged_task):
    channel = DummyChannel()
    cog = await create_cog(tmp_path, patch_logged_task, channel=channel)
    await cog.data.replace_snapshot([member(name="Voidok")])
    view = wow_cog_mod.PanelRosterCharacterSelectView(cog, 42, [member(name="Voidok")])
    select = view.children[0]
    select._values = ["Voidok"]
    interaction = DummyReviewInteraction(DummyUser(42))

    await select.callback(interaction)

    assert "verbunden" in interaction.response.edits[0]["content"]
    assert await cog.data.get_claim_by_name("Voidok")


@pytest.mark.asyncio
async def test_panel_profession_flow_saves_profile(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    claim, _ = await cog.data.create_claim(member(name="Voidok"), 42)

    char_view = wow_cog_mod.PanelOwnedCharacterSelectView(
        cog, 42, [claim], "profession"
    )
    char_select = char_view.children[0]
    char_select._values = ["Voidok"]
    char_interaction = DummyReviewInteraction(DummyUser(42))
    await char_select.callback(char_interaction)
    assert isinstance(
        char_interaction.response.edits[0]["view"],
        wow_cog_mod.PanelProfessionSelectView,
    )
    assert "Hauptberuf 1: frei" in char_interaction.response.edits[0]["content"]
    assert "Kochen: frei" in char_interaction.response.edits[0]["content"]

    profession_view = char_interaction.response.edits[0]["view"]
    profession_select = profession_view.children[0]
    profession_select._values = ["alchemy"]
    modal_interaction = DummyReviewInteraction(DummyUser(42))
    await profession_select.callback(modal_interaction)
    modal = modal_interaction.response.modals[0]
    modal.skill._value = "250"
    modal.specialization._value = "Elixiere"
    save_interaction = DummyReviewInteraction(DummyUser(42))
    await modal.on_submit(save_interaction)

    assert "Gespeichert" in save_interaction.response.messages[0][0]
    profiles = await cog.data.professions_for_user(42)
    assert profiles[0].profession_id == "alchemy"


@pytest.mark.asyncio
async def test_panel_profession_modal_rejects_invalid_skill(
    tmp_path, patch_logged_task
):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    claim, _ = await cog.data.create_claim(member(name="Voidok"), 42)
    modal = wow_cog_mod.PanelProfessionEditModal(cog, claim, "alchemy")
    modal.skill._value = "abc"
    modal.specialization._value = ""
    interaction = DummyReviewInteraction(DummyUser(42))

    await modal.on_submit(interaction)

    assert "Skill muss" in interaction.response.messages[0][0]


@pytest.mark.asyncio
async def test_panel_recipes_flow_opens_recipe_selection(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    claim, _ = await cog.data.create_claim(member(name="Voidok"), 42)
    await cog.data.set_character_profession(claim, "alchemy", 75)

    char_view = wow_cog_mod.PanelOwnedCharacterSelectView(cog, 42, [claim], "recipes")
    char_select = char_view.children[0]
    char_select._values = ["Voidok"]
    char_interaction = DummyReviewInteraction(DummyUser(42))
    await char_select.callback(char_interaction)
    recipe_profession_view = char_interaction.response.edits[0]["view"]
    assert isinstance(
        recipe_profession_view, wow_cog_mod.PanelRecipeProfessionSelectView
    )

    profession_select = recipe_profession_view.children[0]
    profession_select._values = ["alchemy"]
    language_interaction = DummyReviewInteraction(DummyUser(42))
    await profession_select.callback(language_interaction)
    language_view = language_interaction.response.edits[0]["view"]
    assert isinstance(language_view, wow_cog_mod.PanelRecipeLanguageSelectView)

    language_select = language_view.children[0]
    language_select._values = ["en"]
    recipe_interaction = DummyReviewInteraction(DummyUser(42))
    await language_select.callback(recipe_interaction)

    assert "Offene Spezialrezepte" in recipe_interaction.response.edits[0]["content"]
    assert "Sprache: English" in recipe_interaction.response.edits[0]["content"]
    assert isinstance(
        recipe_interaction.response.edits[0]["view"],
        wow_cog_mod.CraftingRecipeSelectionView,
    )


@pytest.mark.asyncio
async def test_panel_recipes_requires_profession(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    claim, _ = await cog.data.create_claim(member(name="Voidok"), 42)
    view = wow_cog_mod.PanelOwnedCharacterSelectView(cog, 42, [claim], "recipes")
    select = view.children[0]
    select._values = ["Voidok"]
    interaction = DummyReviewInteraction(DummyUser(42))

    await select.callback(interaction)

    assert "noch keine Berufe" in interaction.response.edits[0]["content"]


@pytest.mark.asyncio
async def test_panel_crafting_search_modal_uses_search(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    modal = wow_cog_mod.PanelCraftingSearchModal(cog)
    modal.item._value = "Swiftnesstrank"
    interaction = DummyReviewInteraction(DummyUser(42))

    await modal.on_submit(interaction)

    assert "Spezialrezept" in interaction.response.messages[0][0]


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
async def test_crafting_set_limits_primary_professions_but_allows_cooking(
    tmp_path, patch_logged_task
):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    claim, _ = await cog.data.create_claim(member(name="Voidok"), 42)
    await cog.data.set_character_profession(claim, "alchemy", 250)
    await cog.data.set_character_profession(claim, "blacksmithing", 200)

    third_primary = await cog.set_crafting_profile(
        42, "Voidok", "engineering", 100, None
    )
    cooking = await cog.set_crafting_profile(42, "Voidok", "cooking", 100, None)

    assert third_primary.reason == "primary_limit"
    assert cooking.reason == "saved"
    assert cooking.profession.profession_id == "cooking"


@pytest.mark.asyncio
async def test_profession_choices_exclude_unwanted_secondaries_and_slot_limit(
    tmp_path, patch_logged_task
):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    claim, _ = await cog.data.create_claim(member(name="Voidok"), 42)
    await cog.data.set_character_profession(claim, "alchemy", 250)
    await cog.data.set_character_profession(claim, "blacksmithing", 200)
    profiles = await cog.data.professions_for_character(claim.character_key)

    all_choices = {value for _, value in cog.profession_choices("")}
    char_choices = {value for _, value, _ in cog.profession_choices_for_claim(profiles)}

    assert "first-aid" not in all_choices
    assert "fishing" not in all_choices
    assert "engineering" not in char_choices
    assert {"alchemy", "blacksmithing", "cooking"} <= char_choices


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
    assert "Spezialrezept" in cog.format_crafting_search_result(manual)
    assert ambiguous.status == "ambiguous_item"


@pytest.mark.asyncio
async def test_crafting_search_finds_saved_manual_recipe(tmp_path, patch_logged_task):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    await cog.data.replace_snapshot([member(name="Voidok")])
    claim, _ = await cog.data.create_claim(member(name="Voidok"), 42)
    await cog.data.set_character_profession(claim, "alchemy", 75)
    await cog.data.add_known_recipes(claim.character_key, "alchemy", ["spell.2335"])

    result = await cog.search_crafting("Swiftnesstrank")

    assert result.status == "ok"
    assert result.manual_recipe is True
    assert result.crafters[0].character_name == "Voidok"
    assert "Spezialrezept gepflegt" in cog.format_crafting_search_result(result)


@pytest.mark.asyncio
async def test_recipe_selection_filters_known_and_low_skill(
    tmp_path, patch_logged_task
):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    await cog.data.replace_snapshot([member(name="Voidok")])
    claim, _ = await cog.data.create_claim(member(name="Voidok"), 42)
    await cog.data.set_character_profession(claim, "alchemy", 50)

    low_skill = await cog.prepare_recipe_selection(42, "Voidok", "alchemy", None)
    assert low_skill.status == "ok"
    assert low_skill.recipes == []

    await cog.data.set_character_profession(claim, "alchemy", 75)
    available = await cog.prepare_recipe_selection(42, "Voidok", "alchemy", None)
    assert [recipe["spell_id"] for recipe in available.recipes] == ["spell.2335"]

    saved = await cog.save_known_recipes(claim, "alchemy", ["spell.2335"])
    assert saved == 1
    available = await cog.prepare_recipe_selection(42, "Voidok", "alchemy", None)
    assert available.recipes == []


@pytest.mark.asyncio
async def test_recipe_selection_view_saves_multiple_recipes(
    tmp_path, patch_logged_task
):
    cog = await create_cog(tmp_path, patch_logged_task)
    cog.bot.data = {"wow": crafting_data()}
    claim, _ = await cog.data.create_claim(member(name="Voidok"), 42)
    profile = await cog.data.set_character_profession(claim, "alchemy", 75)
    recipe = crafting_data()["profession_recipes"][1]
    view = wow_cog_mod.CraftingRecipeSelectionView(cog, 42, claim, profile, [recipe])
    view.selected_spell_ids = {"spell.2335"}

    interaction = DummyReviewInteraction(DummyUser(42))
    await view.children[-1].callback(interaction)

    assert await cog.data.known_recipe_spell_ids(claim.character_key) == {"spell.2335"}
    assert "1 Rezepte" in interaction.response.edits[0]["content"]


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
