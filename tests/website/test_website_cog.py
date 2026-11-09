import asyncio
from types import SimpleNamespace

import pytest

from lotus_bot.cogs.website import cog as website

ORIGINAL_LOOP = website.WebsiteCog._loop


def member(bot=False):
    return SimpleNamespace(bot=bot)


def channel(cid, members):
    return SimpleNamespace(id=cid, members=members)


def guild(voice, stage=(), afk=None):
    return SimpleNamespace(
        voice_channels=list(voice),
        stage_channels=list(stage),
        afk_channel=afk,
    )


def test_count_voice_counts_humans_in_voice_and_stage():
    g = guild(
        [channel(1, [member(), member(), member(bot=True)]), channel(2, [member()])],
        stage=[channel(3, [member()])],
    )
    assert website.count_voice(g) == 4


def test_count_voice_skips_afk_channel():
    afk = channel(9, [member(), member()])
    g = guild([channel(1, [member()]), afk], afk=afk)
    assert website.count_voice(g) == 1


def test_count_voice_empty():
    assert website.count_voice(guild([])) == 0


class FakeBot:
    def __init__(self, g):
        self.main_guild_id = 1
        self._g = g
        self.added = []

    def get_guild(self, gid):
        return self._g

    async def wait_until_ready(self):
        return None

    async def add_cog(self, cog):
        self.added.append(cog)


@pytest.mark.asyncio
async def test_report_once_sends_count(monkeypatch):
    sent = []

    async def fake_report(self, count):
        sent.append(count)
        return True

    monkeypatch.setattr(website.WebsiteCog, "report", fake_report)
    monkeypatch.setattr(website.WebsiteCog, "_loop", lambda self: asyncio.sleep(0))
    cog = website.WebsiteCog(FakeBot(guild([channel(1, [member(), member()])])), "t")
    assert await cog.report_once() is True
    assert sent == [2]
    cog.cog_unload()


@pytest.mark.asyncio
async def test_report_once_without_guild(monkeypatch):
    monkeypatch.setattr(website.WebsiteCog, "_loop", lambda self: asyncio.sleep(0))
    cog = website.WebsiteCog(FakeBot(None), "t")
    assert await cog.report_once() is False
    cog.cog_unload()


@pytest.mark.asyncio
async def test_report_handles_network_error(monkeypatch):
    class Boom:
        def __init__(self, *a, **k):
            raise OSError("kein Netz")

    monkeypatch.setattr(website.aiohttp, "ClientSession", Boom)
    monkeypatch.setattr(website.WebsiteCog, "_loop", lambda self: asyncio.sleep(0))
    cog = website.WebsiteCog(FakeBot(None), "t")
    assert await cog.report(3) is False
    cog.cog_unload()


@pytest.mark.asyncio
async def test_report_status_codes(monkeypatch):
    calls = []

    class Resp:
        def __init__(self, status):
            self.status = status

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class Session:
        status = 200

        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def post(self, url, json=None, headers=None):
            calls.append((url, json, headers))
            return Resp(Session.status)

    monkeypatch.setattr(website.aiohttp, "ClientSession", Session)
    monkeypatch.setattr(website.WebsiteCog, "_loop", lambda self: asyncio.sleep(0))
    cog = website.WebsiteCog(FakeBot(None), "geheim", url="https://x/api/voice")
    assert await cog.report(5) is True
    assert calls[0][1] == {"count": 5}
    assert calls[0][2]["Authorization"] == "Bearer geheim"
    Session.status = 401
    assert await cog.report(5) is False
    cog.cog_unload()


@pytest.mark.asyncio
async def test_loop_reports_after_ready(monkeypatch):
    reported = []

    async def fake_report_once(self):
        reported.append(1)
        raise asyncio.CancelledError

    monkeypatch.setattr(website.WebsiteCog, "report_once", fake_report_once)
    monkeypatch.setattr(website.WebsiteCog, "_loop", lambda self: asyncio.sleep(0))
    cog = website.WebsiteCog(FakeBot(None), "t")
    with pytest.raises(asyncio.CancelledError):
        await ORIGINAL_LOOP(cog)
    assert reported == [1]
    cog.cog_unload()


@pytest.mark.asyncio
async def test_setup_without_token_does_nothing(monkeypatch):
    monkeypatch.delenv("WEBSITE_VOICE_TOKEN", raising=False)
    bot = FakeBot(None)
    await website.setup(bot)
    assert bot.added == []


@pytest.mark.asyncio
async def test_setup_with_token_registers(monkeypatch):
    monkeypatch.setenv("WEBSITE_VOICE_TOKEN", "t")
    monkeypatch.setattr(website.WebsiteCog, "_loop", lambda self: asyncio.sleep(0))
    bot = FakeBot(None)
    await website.setup(bot)
    assert len(bot.added) == 1
    bot.added[0].cog_unload()
