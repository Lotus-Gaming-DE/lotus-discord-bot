import asyncio
import logging

import aiohttp
import pytest

from lotusbot.cogs.wcr.utils import fetch_wcr_data


@pytest.mark.asyncio
async def test_fetch_concurrent(monkeypatch):
    start_events = [asyncio.Event() for _ in range(2)]
    release = asyncio.Event()

    class DummyResponse:
        def __init__(self, idx):
            self.idx = idx

        async def __aenter__(self):
            start_events[self.idx].set()
            await release.wait()
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def json(self):
            return {"id": self.idx}

        def raise_for_status(self):
            pass

    class DummySession:
        def __init__(self, *args, **kwargs):
            self.count = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        def get(self, url):
            resp = DummyResponse(self.count)
            self.count += 1
            return resp

    monkeypatch.setattr(
        "lotusbot.cogs.wcr.utils.aiohttp.ClientSession",
        lambda *args, **kwargs: DummySession(*args, **kwargs),
    )

    task = asyncio.create_task(fetch_wcr_data("http://test"))
    await asyncio.wait_for(
        asyncio.gather(*(e.wait() for e in start_events)), timeout=0.1
    )
    assert all(e.is_set() for e in start_events)
    release.set()
    result = await task
    assert set(result) == {"units", "categories", "faction_combinations"}


@pytest.mark.asyncio
async def test_fetch_timeout(monkeypatch, caplog):
    captured = {}

    class DummyResponse:
        async def __aenter__(self):
            raise asyncio.TimeoutError

        async def __aexit__(self, exc_type, exc, tb):
            pass

        def raise_for_status(self):
            pass

    class DummySession:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        def get(self, url):
            return DummyResponse()

    monkeypatch.setattr(
        "lotusbot.cogs.wcr.utils.aiohttp.ClientSession",
        lambda *args, **kwargs: DummySession(*args, **kwargs),
    )

    with caplog.at_level(logging.ERROR):
        result = await fetch_wcr_data("http://test")

    assert isinstance(captured["timeout"], aiohttp.ClientTimeout)
    assert captured["timeout"].total == 10
    assert result["units"] == {}
    assert any("Timeout" in r.message for r in caplog.records)
