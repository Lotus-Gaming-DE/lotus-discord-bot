from lotus_bot.cogs.wow.data import CharacterClaim, CharacterProfession, RosterMember
from lotus_bot.cogs.wow.slash_commands import (
    claim,
    claim_release,
    claim_remove,
    claims_list,
    claims_mine,
    crafting_list,
    crafting_mine,
    crafting_remove,
    crafting_search,
    crafting_set,
    scan,
    setup,
    status,
)
import pytest

pytestmark = pytest.mark.asyncio


class DummyCog:
    def __init__(self):
        self.channel_id = None
        self.scan_calls = []
        self.claim_results = {}
        self.crafting_set_calls = []
        self.crafting_remove_calls = []
        self.crafting_set_result = None
        self.crafting_remove_result = None
        self.crafting_search_result = None
        self.data = DummyData()

    async def set_announcement_channel(self, channel_id):
        self.channel_id = channel_id

    async def status(self):
        return {
            "guild": "Black Lotus",
            "realm": "soulseeker",
            "channel_id": self.channel_id,
            "last_scan_at": "now",
            "member_count": 12,
            "poll_interval": 10800,
        }

    async def scan(self, *, post=True, persist=True):
        self.scan_calls.append((post, persist))
        return type("Result", (), {"member_count": 12, "milestones": [], "posted": 0})()

    async def claim_character(self, user_id, char):
        return self.claim_results[char]

    async def set_crafting_profile(
        self, user_id, char, profession, skill, specialization, *, is_mod=False
    ):
        self.crafting_set_calls.append(
            (user_id, char, profession, skill, specialization, is_mod)
        )
        return self.crafting_set_result

    async def remove_crafting_profile(self, user_id, char, profession, *, is_mod=False):
        self.crafting_remove_calls.append((user_id, char, profession, is_mod))
        return self.crafting_remove_result

    async def search_crafting(self, item):
        return self.crafting_search_result

    def _profession_name(self, profession_id):
        return {"alchemy": "Alchemie"}.get(profession_id, profession_id)

    def resolve_profession_id(self, profession):
        if profession in (None, "alchemy", "Alchemie"):
            return "alchemy"
        return None

    def format_profession(self, profile):
        return f"**{profile.character_name}** - Alchemie {profile.skill_level}"

    def format_crafting_search_result(self, result):
        return result.message


def roster_member(name="Lyxendra"):
    return RosterMember(
        character_key="id:1",
        character_id=1,
        name=name,
        realm_slug="soulseeker",
        level=44,
        class_id=4,
        race_id=8,
        faction="HORDE",
        guild_rank=1,
    )


def character_claim(name="Lyxendra", user_id=42, status="unverified"):
    return CharacterClaim(
        character_key="id:1",
        character_name=name,
        realm_slug="soulseeker",
        discord_user_id=user_id,
        status=status,
        claimed_at="now",
        verified_at=None,
        verified_by=None,
        review_message_id=None,
    )


def character_profession(name="Lyxendra", user_id=42, profession_id="alchemy"):
    return CharacterProfession(
        character_key="id:1",
        character_name=name,
        realm_slug="soulseeker",
        discord_user_id=user_id,
        profession_id=profession_id,
        skill_level=250,
        specialization="Elixiere",
        updated_at="now",
    )


class DummyData:
    def __init__(self):
        self.member = roster_member()
        self.claim = None
        self.professions = []
        self.removed = []

    async def find_roster_member_by_name(self, char):
        if char.lower() == self.member.name.lower():
            return self.member
        return None

    async def release_claim(self, character_key, user_id):
        if self.claim and self.claim.discord_user_id == user_id:
            self.claim = None
            return True
        return False

    async def get_claim(self, character_key):
        return self.claim

    async def get_claim_by_name(self, char):
        if self.claim and char.lower() == self.claim.character_name.lower():
            return self.claim
        return None

    async def remove_claim(self, character_key):
        self.removed.append(character_key)
        self.claim = None

    async def claims_for_user(self, user_id):
        return (
            [self.claim] if self.claim and self.claim.discord_user_id == user_id else []
        )

    async def list_claims(self, status="all"):
        if not self.claim:
            return []
        if status != "all" and self.claim.status != status:
            return []
        return [self.claim]

    async def professions_for_user(self, user_id):
        return [
            profession
            for profession in self.professions
            if profession.discord_user_id == user_id
        ]

    async def list_professions(self, profession_id=None):
        if profession_id:
            return [
                profession
                for profession in self.professions
                if profession.profession_id == profession_id
            ]
        return self.professions


class DummyBot:
    def __init__(self, cog):
        self.cog = cog

    def get_cog(self, name):
        return self.cog if name == "WoWCog" else None


class DummyResponse:
    def __init__(self):
        self.messages = []
        self.deferred = False

    async def send_message(self, msg, **kwargs):
        self.messages.append((msg, kwargs))

    async def defer(self, **kwargs):
        self.deferred = True


class DummyFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, msg, **kwargs):
        self.messages.append((msg, kwargs))


class DummyInteraction:
    def __init__(self, cog, *, manage_guild=False):
        self.client = DummyBot(cog)
        self.response = DummyResponse()
        self.followup = DummyFollowup()
        permissions = type("Permissions", (), {"manage_guild": manage_guild})()
        self.user = type(
            "User",
            (),
            {
                "id": 42,
                "guild_permissions": permissions,
                "__str__": lambda self: "tester",
            },
        )()


class DummyChannel:
    id = 123
    mention = "<#123>"


async def test_setup_command_persists_channel():
    cog = DummyCog()
    inter = DummyInteraction(cog)
    await setup.callback(inter, DummyChannel())

    assert cog.channel_id == 123
    assert inter.response.messages


async def test_status_command_reports_state():
    cog = DummyCog()
    cog.channel_id = 123
    inter = DummyInteraction(cog)
    await status.callback(inter)

    msg, kwargs = inter.response.messages[0]
    assert "Black Lotus" in msg
    assert "<#123>" in msg
    assert kwargs.get("ephemeral")


async def test_scan_command_dry_run_does_not_persist():
    cog = DummyCog()
    inter = DummyInteraction(cog)
    await scan.callback(inter, False)

    assert cog.scan_calls == [(False, False)]
    assert inter.response.deferred
    assert inter.followup.messages


async def test_claim_command_creates_claim():
    cog = DummyCog()
    cog.claim_results["Lyxendra"] = type(
        "Result",
        (),
        {
            "reason": "created",
            "claim": character_claim(),
            "created": True,
            "review_posted": True,
        },
    )()
    inter = DummyInteraction(cog)
    await claim.callback(inter, "Lyxendra")

    msg, kwargs = inter.response.messages[0]
    assert "Lyxendra" in msg
    assert "geclaimed" in msg
    assert kwargs.get("ephemeral")


async def test_claim_command_rejects_unknown_character():
    cog = DummyCog()
    cog.claim_results["Unknown"] = type(
        "Result", (), {"reason": "not_found", "claim": None}
    )()
    inter = DummyInteraction(cog)
    await claim.callback(inter, "Unknown")

    msg, kwargs = inter.response.messages[0]
    assert "nicht gefunden" in msg
    assert kwargs.get("ephemeral")


async def test_claim_command_reports_taken_character():
    cog = DummyCog()
    cog.claim_results["Lyxendra"] = type(
        "Result",
        (),
        {"reason": "taken", "claim": character_claim(user_id=99)},
    )()
    inter = DummyInteraction(cog)
    await claim.callback(inter, "Lyxendra")

    assert "bereits geclaimed" in inter.response.messages[0][0]


async def test_claims_mine_shows_user_claims():
    cog = DummyCog()
    cog.data.claim = character_claim()
    inter = DummyInteraction(cog)
    await claims_mine.callback(inter)

    assert "Lyxendra" in inter.response.messages[0][0]
    assert "ungeprüft" in inter.response.messages[0][0]


async def test_claims_list_filters_claims():
    cog = DummyCog()
    cog.data.claim = character_claim(user_id=99, status="verified")
    inter = DummyInteraction(cog)
    await claims_list.callback(inter, "verified")

    msg, kwargs = inter.response.messages[0]
    assert "<@99>" in msg
    assert "bestätigt" in msg
    assert kwargs.get("ephemeral")


async def test_claim_release_removes_own_claim():
    cog = DummyCog()
    cog.data.claim = character_claim()
    inter = DummyInteraction(cog)
    await claim_release.callback(inter, "Lyxendra")

    assert cog.data.claim is None
    assert "freigegeben" in inter.response.messages[0][0]


async def test_claim_remove_removes_claim():
    cog = DummyCog()
    cog.data.claim = character_claim()
    inter = DummyInteraction(cog)
    await claim_remove.callback(inter, "Lyxendra")

    assert cog.data.removed == ["id:1"]
    assert "entfernt" in inter.response.messages[0][0]


async def test_crafting_set_saves_profile():
    cog = DummyCog()
    cog.crafting_set_result = type(
        "Result",
        (),
        {
            "reason": "saved",
            "profession": character_profession(),
            "claim": character_claim(),
        },
    )()
    inter = DummyInteraction(cog)
    await crafting_set.callback(inter, "Lyxendra", "alchemy", 250, "Elixiere")

    msg, kwargs = inter.response.messages[0]
    assert cog.crafting_set_calls == [
        (42, "Lyxendra", "alchemy", 250, "Elixiere", False)
    ]
    assert "Gespeichert" in msg
    assert kwargs.get("ephemeral")


async def test_crafting_set_rejects_foreign_claim():
    cog = DummyCog()
    cog.crafting_set_result = type(
        "Result", (), {"reason": "forbidden", "profession": None}
    )()
    inter = DummyInteraction(cog)
    await crafting_set.callback(inter, "Voidok", "alchemy", 250, None)

    assert "nicht bearbeiten" in inter.response.messages[0][0]


async def test_crafting_remove_removes_profile_as_mod():
    cog = DummyCog()
    cog.crafting_remove_result = type(
        "Result", (), {"reason": "removed", "claim": character_claim()}
    )()
    inter = DummyInteraction(cog, manage_guild=True)
    await crafting_remove.callback(inter, "Lyxendra", "alchemy")

    assert cog.crafting_remove_calls == [(42, "Lyxendra", "alchemy", True)]
    assert "entfernt" in inter.response.messages[0][0]


async def test_crafting_mine_shows_profiles():
    cog = DummyCog()
    cog.data.professions = [character_profession()]
    inter = DummyInteraction(cog)
    await crafting_mine.callback(inter)

    assert "Lyxendra" in inter.response.messages[0][0]
    assert "Alchemie" in inter.response.messages[0][0]


async def test_crafting_list_filters_profiles():
    cog = DummyCog()
    cog.data.professions = [character_profession(user_id=99)]
    inter = DummyInteraction(cog, manage_guild=True)
    await crafting_list.callback(inter, "alchemy")

    msg, kwargs = inter.response.messages[0]
    assert "<@99>" in msg
    assert kwargs.get("ephemeral")


async def test_crafting_search_reports_result():
    cog = DummyCog()
    cog.crafting_search_result = type("Result", (), {"message": "Voidok kann das"})()
    inter = DummyInteraction(cog)
    await crafting_search.callback(inter, "Schwacher Heiltrank")

    assert "Voidok" in inter.response.messages[0][0]
