import json
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
