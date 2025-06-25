import pytest

import lotus_bot.cogs.ptcgp.api as api_mod


class DummyResponse:
    def __init__(self):
        self.status = 200
        self.json_called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def json(self):
        self.json_called = True
        return []


class DummySession:
    def __init__(self, called):
        self.called = called

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def get(self, url, *, ssl=None):
        self.called["ssl"] = ssl
        return DummyResponse()


@pytest.mark.asyncio
async def test_fetch_respects_env(monkeypatch):
    called = {}
    monkeypatch.setenv("PTCGP_SKIP_SSL_VERIFY", "1")
    monkeypatch.setattr(api_mod.aiohttp, "ClientSession", lambda: DummySession(called))
    await api_mod.fetch_all_cards("en")
    assert called["ssl"] is False
