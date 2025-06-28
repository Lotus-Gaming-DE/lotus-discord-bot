import json
import asyncio
from pathlib import Path
from lotus_bot.cogs.wcr.cog import WCRCog
from lotus_bot.cogs.wcr import utils


class DummyBot:
    def __init__(self, data):
        self.data = data
        self.tree = type(
            "T", (), {"add_command": lambda *a, **k: None, "sync": lambda *a, **k: None}
        )()
        self.main_guild = None
        self.main_guild_id = 0


def create_cog():
    base = Path("tests/data")
    units = json.load(open(base / "wcr_units.json", encoding="utf-8"))
    categories = json.load(open(base / "wcr_categories.json", encoding="utf-8"))
    data = {
        "units": {"units": units},
        "categories": categories,
        "faction_combinations": {},
    }
    bot = DummyBot({"emojis": {}})

    # build wcr data using loader to populate locals
    async def fake_fetch(url):
        return data

    utils.fetch_wcr_data = fake_fetch
    utils.CACHE_FILE = Path("tests/data/cache.json")
    wcr_data = asyncio.run(utils.load_wcr_data("http://test"))
    bot.data["wcr"] = wcr_data
    return WCRCog(bot)


def test_create_mini_embed():
    cog = create_cog()
    embed, _ = cog.create_mini_embed("abomination", "en")
    assert embed.title
