import json
import os

import pytest

from lotus_bot.cogs.wcr import utils


@pytest.mark.asyncio
async def test_load_wcr_data_cache_hit(monkeypatch, tmp_path):
    data = {
        "units": [],
        "locals": {},
        "categories": {},
        "stat_labels": {},
        "faction_combinations": {},
    }
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps(data), encoding="utf-8")
    os.utime(cache, None)

    monkeypatch.setattr(utils, "CACHE_FILE", cache)
    monkeypatch.setattr(utils, "BASE_PATH", tmp_path)

    called = False

    async def fake_fetch(url):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(utils, "fetch_wcr_data", fake_fetch)

    result = await utils.load_wcr_data("http://test")
    assert result == data
    assert not called


@pytest.mark.asyncio
async def test_load_wcr_data_cache_miss(monkeypatch, tmp_path):
    cache = tmp_path / "cache.json"
    monkeypatch.setattr(utils, "CACHE_FILE", cache)
    monkeypatch.setattr(utils, "BASE_PATH", tmp_path)

    fetch_result = {
        "units": {"units": []},
        "categories": {},
        "faction_combinations": {},
    }

    async def fake_fetch(url):
        return fetch_result

    monkeypatch.setattr(utils, "fetch_wcr_data", fake_fetch)

    result = await utils.load_wcr_data("http://test")

    assert result["units"] == []
    assert cache.exists()
    saved = json.loads(cache.read_text(encoding="utf-8"))
    assert saved["units"] == []
