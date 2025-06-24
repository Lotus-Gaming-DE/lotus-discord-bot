import json
from pathlib import Path

import aiohttp
import pytest

from cogs.wcr.utils import fetch_wcr_data


class DummyResponse:
    def __init__(self, data):
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def raise_for_status(self):
        pass

    async def json(self):
        return self._data


class DummySession:
    def __init__(self, data_map):
        self.data_map = data_map

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def get(self, url):
        endpoint = url.rsplit("/", 1)[-1]
        return DummyResponse(self.data_map[endpoint])


@pytest.mark.asyncio
async def test_fetch_wcr_data_merges_faction_meta(monkeypatch):
    base = Path("data/wcr")
    data_map = {
        "units": {},
        "categories": json.load(open(base / "categories.json", encoding="utf-8")),
        "pictures": {},
        "stat_labels": {},
    }

    monkeypatch.setattr(
        aiohttp, "ClientSession", lambda *_, **__: DummySession(data_map)
    )

    result = await fetch_wcr_data("http://api.test")

    meta = json.load(open(base / "faction_meta.json", encoding="utf-8"))
    for item in meta.get("factions", []):
        faction = next(
            f for f in result["categories"]["factions"] if f["id"] == item["id"]
        )
        assert faction["icon"] == item["icon"]
        assert faction["color"] == item["color"]
