# cogs/quiz/utils.py

import logging
import re
import difflib
from unidecode import unidecode

logger = logging.getLogger(__name__)  # z. B. 'cogs.quiz.utils'


def check_answer(user_answer: str, correct_answers: list[str], threshold: float = 0.6) -> bool:
    """
    Prüft, ob eine Nutzerantwort mit einer der richtigen Antworten übereinstimmt.
    Verwendet Normalisierung, Teilstringsuche und Levenshtein-Ähnlichkeit.
    """
    normalized_user = normalize_text(user_answer)

    for correct in correct_answers:
        normalized_correct = normalize_text(correct)

        # Teilstring oder vollständige Übereinstimmung
        if normalized_user in normalized_correct or normalized_correct in normalized_user:
            logger.debug(
                f"[check_answer] partial match: '{normalized_user}' <-> '{normalized_correct}'"
            )
            return True

        # Levenshtein-basierte Ähnlichkeit
        similarity = difflib.SequenceMatcher(
            None, normalized_user, normalized_correct).ratio()
        if similarity >= threshold:
            logger.debug(
                f"[check_answer] fuzzy match: '{normalized_user}' <-> '{normalized_correct}' ({similarity:.2f})"
            )
            return True

    logger.debug(f"[check_answer] no match: '{user_answer}'")
    return False


def create_permutations(answer: str) -> list[str]:
    """
    Erzeugt Varianten einer Antwort (Kleinschreibung, ASCII, ohne Sonderzeichen).
    Wird z. B. für Fuzzy Matching oder alternative Datenquellen verwendet.
    """
    perms = {answer.lower(), unidecode(answer.lower())}
    cleaned = re.sub(r'[^\w\s]', '', answer.lower())
    perms.add(cleaned)
    perms.add(unidecode(cleaned))
    return list(perms)


def create_permutations_list(answers: list[str]) -> list[str]:
    """
    Erstellt eine kombinierte Permutationsliste für mehrere Antworten.
    """
    all_perms = set()
    for ans in answers:
        all_perms.update(create_permutations(ans))
    return list(all_perms)


def normalize_text(text: str) -> str:
    """
    Entfernt Akzente, vereinfacht auf lowercase, reduziert Leerzeichen und
    entfernt Sonderzeichen.
    """
    txt = unidecode(text.strip().lower())
    txt = re.sub(r'\s+', ' ', txt)
    txt = re.sub(r'[^\w\s]', '', txt)
    return txt
