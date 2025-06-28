import json
from pathlib import Path
from lotus_bot.cogs.quiz.area_providers.wcr import WCRQuestionProvider


class DummyBot:
    def __init__(self, data):
        self.data = data


def create_provider():
    base = Path("tests/data")
    units = json.load(open(base / "wcr_units.json", encoding="utf-8"))
    categories = json.load(open(base / "wcr_categories.json", encoding="utf-8"))
    data = {
        "wcr": {
            "units": {"units": units},
            "locals": {},
            "categories": categories,
        },
        "quiz": {"templates": {"wcr": {"de": {"type_3": "{unit_name}"}}}},
    }
    bot = DummyBot(data)
    return WCRQuestionProvider(bot, language="de")


def test_generate_type_3():
    provider = create_provider()
    q = provider.generate_type_3()
    assert q
    assert "frage" in q and "antwort" in q
