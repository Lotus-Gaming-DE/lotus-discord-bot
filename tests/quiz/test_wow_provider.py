from lotus_bot.bot import load_wow_data
from lotus_bot.cogs.quiz.area_providers.wow import WoWQuestionProvider


class DummyBot:
    def __init__(self):
        self.data = {
            "wow": load_wow_data("data/wow/classic_hc"),
            "quiz": {
                "templates": {
                    "wow": {
                        "de": {
                            "talent_tree": "{talent_name}",
                            "talent_description": "{description}",
                            "ability_class": "{ability_name}",
                            "dungeon_level": "{dungeon_name}",
                        },
                        "en": {
                            "talent_tree": "{talent_name}",
                            "talent_description": "{description}",
                            "ability_class": "{ability_name}",
                            "dungeon_level": "{dungeon_name}",
                        },
                    }
                }
            },
        }


def test_wow_provider_generates_all_types():
    provider = WoWQuestionProvider(DummyBot(), language="de")
    questions = provider.generate_all_types()

    assert len(questions) == 4
    assert all("frage" in q and "antwort" in q and "id" in q for q in questions)


def test_wow_provider_uses_question_language_and_bilingual_answers(monkeypatch):
    provider = WoWQuestionProvider(DummyBot(), language="de")
    monkeypatch.setattr("random.choice", lambda records: records[0])

    question = provider.generate_talent_tree()

    assert "Riposte" in question["frage"]
    assert "kampf" in question["antwort"]
    assert "combat" in question["antwort"]


def test_wow_provider_ids_are_stable(monkeypatch):
    provider = WoWQuestionProvider(DummyBot(), language="de")
    monkeypatch.setattr("random.choice", lambda records: records[0])

    first = provider.generate_talent_tree()["id"]
    second = provider.generate_talent_tree()["id"]

    assert first == second
