import json
import pytest

from cogs.wcr.cog import WCRCog
from cogs.wcr.views import MiniSelectView


class DummyBot:
    def __init__(self):
        self.data = {
            "emojis": {},
            "wcr": {
                "units": json.load(open("data/wcr/units.json", "r", encoding="utf-8")),
                "locals": {
                    "de": json.load(open("data/wcr/locals/de.json", "r", encoding="utf-8")),
                    "en": json.load(open("data/wcr/locals/en.json", "r", encoding="utf-8")),
                },
                "pictures": json.load(open("data/wcr/pictures.json", "r", encoding="utf-8")),
            },
        }


class DummyResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content, view=None, ephemeral=False):
        self.messages.append({"content": content, "view": view, "ephemeral": ephemeral})


class DummyInteraction:
    def __init__(self):
        self.user = "tester"
        self.response = DummyResponse()


@pytest.mark.asyncio
async def test_cmd_filter_no_emojis():
    bot = DummyBot()
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_filter(inter, cost="6", lang="de")

    assert inter.response.messages
    msg = inter.response.messages[0]
    assert isinstance(msg["view"], MiniSelectView)
    assert msg["ephemeral"] is True
