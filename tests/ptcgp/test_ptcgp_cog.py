import pytest

from lotusbot.cogs.ptcgp.cog import PTCGPCog
import lotusbot.cogs.ptcgp.api as api_mod


class DummyBot:
    def __init__(self):
        self.main_guild = None
        self.data = {}

    def get_cog(self, name):
        return self._cog if name == "PTCGPCog" else None


class DummyResponse:
    def __init__(self):
        self.deferred = False
        self.sent = []

    async def defer(self, ephemeral=False, thinking=False):
        self.deferred = True

    async def send_message(self, msg, ephemeral=False):
        self.sent.append((msg, ephemeral))

    async def send(self, msg):
        self.sent.append(msg)


class DummyInteraction:
    def __init__(self, bot):
        self.user = "tester"
        self.client = bot
        self.response = DummyResponse()
        self.followup = DummyResponse()
        self.guild = None


@pytest.mark.asyncio
async def test_update_command(monkeypatch, tmp_path):
    bot = DummyBot()
    cog = PTCGPCog(bot)
    bot._cog = cog
    cog.data = cog.data.__class__(str(tmp_path / "cards.db"))

    async def fake_fetch(lang):
        if lang == "en":
            return [{"id": "1", "name": "Pika"}]
        return [{"id": "1", "name": "Pika"}]

    monkeypatch.setattr(api_mod, "fetch_all_cards", fake_fetch)
    import lotusbot.cogs.ptcgp.cog as cog_mod

    monkeypatch.setattr(cog_mod, "fetch_all_cards", fake_fetch)

    from lotusbot.cogs.ptcgp.slash_commands import update

    inter = DummyInteraction(bot)
    await update.callback(inter)

    assert inter.response.deferred
    assert inter.followup.sent
    counts = await cog.data.count_cards()
    assert counts == {"en": 1, "de": 1}

    await cog.cog_unload()
    await cog.wait_closed()
