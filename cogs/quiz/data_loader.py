import json
import os
import logging

logger = logging.getLogger(__name__)


class DataLoader:
    def __init__(self, base_path="./data/quiz"):
        self.base_path = base_path

    def load_questions(self, language):
        file_path = os.path.join(self.base_path, f"questions_{language}.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(
                    f"[DataLoader] Questions loaded from '{file_path}'.")
                return data
        except FileNotFoundError:
            logger.warning(f"[DataLoader] File not found: {file_path}")
            return {}

    def load_all_languages(self):
        questions = {}
        languages = {}
        for lang in ["de", "en"]:
            q = self.load_questions(lang)
            if q:
                logger.info(
                    f"[DataLoader] Fragen geladen: {len(q)} Fragen in {len(q.keys())} Bereichen.")
                questions[lang] = q
                languages[lang] = q
        return questions, languages
