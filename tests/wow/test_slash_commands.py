from lotus_bot.cogs.wow.data import CharacterClaim, RosterMember
from lotus_bot.cogs.wow.slash_commands import (
    claim,
    claim_release,
    claim_remove,
    claims_list,
    claims_mine,
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


class DummyData:
    def __init__(self):
        self.member = roster_member()
        self.claim = None
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
    def __init__(self, cog):
        self.client = DummyBot(cog)
        self.response = DummyResponse()
        self.followup = DummyFollowup()
        self.user = type("User", (), {"id": 42, "__str__": lambda self: "tester"})()


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
