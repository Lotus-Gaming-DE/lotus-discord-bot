import hashlib
import random
from typing import Any

from lotus_bot.log_setup import get_logger

from ..utils import create_permutations_list
from .base import DynamicQuestionProvider

logger = get_logger(__name__)


class WoWQuestionProvider(DynamicQuestionProvider):
    question_generators = [
        "generate_talent_tree",
        "generate_talent_description",
        "generate_ability_class",
        "generate_dungeon_level",
    ]

    def __init__(self, bot, language: str = "de"):
        self.bot = bot
        self.language = language
        self.data = bot.data.get("wow", {})
        self.templates = bot.data.get("quiz", {}).get("templates", {}).get("wow", {})

    def _make_id(self, text: str) -> int:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return int(digest, 16)

    def _text(self, value: dict[str, str] | str | None, lang: str | None = None) -> str:
        if isinstance(value, str):
            return value
        if not value:
            return ""
        lang = lang or self.language
        return value.get(lang) or value.get("de") or value.get("en") or ""

    def _answer_aliases(self, *values: Any) -> list[str]:
        aliases: list[str] = []
        for value in values:
            if isinstance(value, dict):
                aliases.extend(str(v) for v in value.values() if v)
            elif isinstance(value, list):
                aliases.extend(str(v) for v in value if v)
            elif value:
                aliases.append(str(value))
        return create_permutations_list(sorted(set(aliases)))

    def _template(self, name: str) -> str | None:
        return self.templates.get(self.language, {}).get(name)

    def _records(self, key: str) -> list[dict[str, Any]]:
        records = self.data.get(key, [])
        return records if isinstance(records, list) else []

    def generate(self):
        questions = self.generate_all_types()
        if not questions:
            logger.warning("[WoWQuestionProvider] No valid question generated.")
            return None
        question = random.choice(questions)
        logger.info(f"[WoWQuestionProvider] Generated: {question['frage']}")
        return question

    def generate_talent_tree(self):
        records = [r for r in self._records("talents") if r.get("tree")]
        template = self._template("talent_tree")
        if not records or not template:
            return None
        pick = random.choice(records)
        talent_name = self._text(pick.get("name"))
        tree = pick.get("tree", {})
        return {
            "frage": template.format(talent_name=talent_name),
            "antwort": self._answer_aliases(tree, pick.get("answers", {}).get("tree")),
            "category": "Talente",
            "id": self._make_id(f"wow:talent_tree:{self.language}:{pick['id']}"),
        }

    def generate_talent_description(self):
        records = [r for r in self._records("talents") if r.get("description")]
        template = self._template("talent_description")
        if not records or not template:
            return None
        pick = random.choice(records)
        description = self._text(pick.get("description"))
        return {
            "frage": template.format(description=description),
            "antwort": self._answer_aliases(
                pick.get("name"), pick.get("answers", {}).get("name")
            ),
            "category": "Talente",
            "id": self._make_id(f"wow:talent_description:{self.language}:{pick['id']}"),
        }

    def generate_ability_class(self):
        records = [r for r in self._records("abilities") if r.get("class")]
        template = self._template("ability_class")
        if not records or not template:
            return None
        pick = random.choice(records)
        ability_name = self._text(pick.get("name"))
        return {
            "frage": template.format(ability_name=ability_name),
            "antwort": self._answer_aliases(
                pick.get("class"), pick.get("answers", {}).get("class")
            ),
            "category": "Klassen",
            "id": self._make_id(f"wow:ability_class:{self.language}:{pick['id']}"),
        }

    def generate_dungeon_level(self):
        records = [r for r in self._records("dungeons") if r.get("level_range")]
        template = self._template("dungeon_level")
        if not records or not template:
            return None
        pick = random.choice(records)
        dungeon_name = self._text(pick.get("name"))
        return {
            "frage": template.format(dungeon_name=dungeon_name),
            "antwort": self._answer_aliases(
                pick.get("level_range"), pick.get("answers", {}).get("level_range")
            ),
            "category": "Dungeons",
            "id": self._make_id(f"wow:dungeon_level:{self.language}:{pick['id']}"),
        }


def get_provider(bot, language):
    return WoWQuestionProvider(bot, language=language)
