import json
import os
import time
from pathlib import Path
import pytest
from lotus_bot.cogs.wcr import utils


@pytest.mark.asyncio
async def test_load_wcr_data(monkeypatch):
    async def fake_fetch(url):
        base = Path("tests/data")
        return {
            "units": {
                "units": json.load(open(base / "wcr_units.json", encoding="utf-8"))
            },
            "categories": json.load(
                open(base / "wcr_categories.json", encoding="utf-8")
            ),
            "faction_combinations": {},
        }

    monkeypatch.setattr(utils, "fetch_wcr_data", fake_fetch)
    monkeypatch.setattr(utils, "CACHE_FILE", Path("tests/data/cache.json"))
    data = await utils.load_wcr_data("http://test")
    assert len(data["units"]) == 3
    assert "en" in data["locals"]


ONE_UNIT = {"units": {"units": [{"id": 1, "names": {"en": "Grunt"}}]}}


@pytest.mark.asyncio
async def test_load_wcr_data_adds_missing_url_scheme(monkeypatch, tmp_path):
    # Production had WCR_API_URL=wcr-api.up.railway.app — aiohttp rejects that.
    seen = []

    async def fake_fetch(url):
        seen.append(url)
        return {**ONE_UNIT, "categories": {}}

    monkeypatch.setattr(utils, "fetch_wcr_data", fake_fetch)
    monkeypatch.setattr(utils, "CACHE_FILE", tmp_path / "cache.json")

    await utils.load_wcr_data("wcr-api.up.railway.app")

    assert seen == ["https://wcr-api.up.railway.app"]


@pytest.mark.asyncio
async def test_failed_fetch_keeps_last_good_cache(monkeypatch, tmp_path):
    cache = tmp_path / "cache.json"
    good = {"units": [{"id": 1}], "locals": {}, "categories": {}}
    cache.write_text(json.dumps(good), encoding="utf-8")
    expired = time.time() - utils.CACHE_TTL - 60
    os.utime(cache, (expired, expired))

    async def failing_fetch(url):
        return {"units": {}, "categories": {}}

    monkeypatch.setattr(utils, "fetch_wcr_data", failing_fetch)
    monkeypatch.setattr(utils, "CACHE_FILE", cache)

    data = await utils.load_wcr_data("https://test")

    assert data["units"] == [{"id": 1}]
    # The last good state must survive — not be replaced by empty data.
    assert json.loads(cache.read_text(encoding="utf-8")) == good


@pytest.mark.asyncio
async def test_fresh_but_empty_cache_is_refetched(monkeypatch, tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"units": [], "locals": {}}), encoding="utf-8")
    calls = []

    async def fake_fetch(url):
        calls.append(url)
        return {**ONE_UNIT, "categories": {}}

    monkeypatch.setattr(utils, "fetch_wcr_data", fake_fetch)
    monkeypatch.setattr(utils, "CACHE_FILE", cache)

    data = await utils.load_wcr_data("https://test")

    assert len(calls) == 1
    assert len(data["units"]) == 1
