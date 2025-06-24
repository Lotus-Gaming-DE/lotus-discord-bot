import json
import datetime


from lotusbot.bot import load_quiz_config
from lotusbot.cogs.quiz.question_state import QuestionStateManager
from lotusbot.cogs.quiz.question_generator import QuestionGenerator


class DummyBot:
    def __init__(self):
        self.quiz_data = {}
        self.data = {
            "quiz": {
                "questions": {
                    "de": {"wcr": [{"id": 1, "frage": "f", "antwort": "a"}], "d4": []}
                },
                "languages": ["de"],
            },
            "wcr": {"units": [], "locals": {"de": {}, "en": {}}},
        }


def test_load_quiz_config(tmp_path, monkeypatch):
    cfg = {
        "wcr": {
            "channel_id": 1,
            "window_timer": 5,
            "language": "de",
            "active": True,
            "activity_threshold": 3,
        },
        "d4": {"channel_id": 2, "window_timer": 10, "language": "de", "active": False},
    }
    cfg_file = tmp_path / "areas.json"
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(cfg, f)

    state_file = tmp_path / "state.json"

    monkeypatch.setattr("lotusbot.bot.QUIZ_CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr("lotusbot.bot.QUESTION_STATE_PATH", str(state_file))

    bot = DummyBot()
    load_quiz_config(bot)

    assert set(bot.quiz_data.keys()) == {"wcr", "d4"}
    assert bot.quiz_data["wcr"].channel_id == 1
    assert bot.quiz_data["d4"].time_window == datetime.timedelta(minutes=10)
    assert isinstance(bot.quiz_data["wcr"].question_state, QuestionStateManager)
    assert isinstance(bot.quiz_data["wcr"].question_generator, QuestionGenerator)


def test_single_state_manager(tmp_path, monkeypatch):
    cfg = {
        "wcr": {"channel_id": 1, "window_timer": 5, "language": "de"},
        "d4": {"channel_id": 2, "window_timer": 10, "language": "de"},
    }
    cfg_file = tmp_path / "areas.json"
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(cfg, f)

    state_file = tmp_path / "state.json"

    monkeypatch.setattr("lotusbot.bot.QUIZ_CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr("lotusbot.bot.QUESTION_STATE_PATH", str(state_file))

    bot = DummyBot()
    load_quiz_config(bot)

    state1 = bot.quiz_data["wcr"].question_state
    state2 = bot.quiz_data["d4"].question_state
    assert state1 is state2


def test_reload_updates_tracker(tmp_path, monkeypatch):
    cfg1 = {"area": {"channel_id": 1, "window_timer": 5, "language": "de"}}
    cfg2 = {"area": {"channel_id": 2, "window_timer": 5, "language": "de"}}

    cfg_file = tmp_path / "areas.json"
    state_file = tmp_path / "state.json"

    monkeypatch.setattr("lotusbot.bot.QUIZ_CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr("lotusbot.bot.QUESTION_STATE_PATH", str(state_file))

    from lotusbot.cogs.quiz.message_tracker import MessageTracker

    class DummyCog:
        def __init__(self, bot):
            self.tracker = MessageTracker(bot, None)

    bot = DummyBot()
    bot.quiz_cog = DummyCog(bot)

    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(cfg1, f)
    load_quiz_config(bot)
    assert bot.quiz_cog.tracker.channel_to_area == {1: "area"}

    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(cfg2, f)
    load_quiz_config(bot)
    assert bot.quiz_cog.tracker.channel_to_area == {2: "area"}
