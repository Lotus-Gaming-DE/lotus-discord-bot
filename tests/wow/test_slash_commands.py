from lotus_bot.cogs.wow.slash_commands import setup, status, scan
import pytest

pytestmark = pytest.mark.asyncio


class DummyCog:
    def __init__(self):
        self.channel_id = None
        self.scan_calls = []

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
        self.user = "tester"


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
