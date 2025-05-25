import logging
import re
import difflib
from unidecode import unidecode

logger = logging.getLogger(__name__)  # e.g. 'cogs.quiz.utils'


def check_answer(user_answer: str, correct_answers: list, threshold: float = 0.6) -> bool:
    """
    Vergleicht die Nutzer-Antwort mit der Liste der korrekten Antworten.
    Liefert True, wenn exact match, Teilstring oder Ähnlichkeit >= threshold.
    """
    normalized_user = normalize_text(user_answer)
    for ans in correct_answers:
        normalized_correct = normalize_text(ans)
        # Direktes Enthalten
        if normalized_user in normalized_correct or normalized_correct in normalized_user:
            return True
        # Levenshtein-ähnlichkeit
        similarity = difflib.SequenceMatcher(
            None, normalized_user, normalized_correct
        ).ratio()
        if similarity >= threshold:
            return True
    return False


def create_permutations(answer: str) -> list:
    """
    Erzeugt verschiedene Normalisierungen einer Antwort (Kleinbuchstaben,
    ohne Akzente, ohne Sonderzeichen).
    """
    perms = {answer.lower(), unidecode(answer.lower())}
    # ohne Sonderzeichen
    cleaned = re.sub(r'[^\w\s]', '', answer.lower())
    perms.add(cleaned)
    perms.add(unidecode(cleaned))
    return list(perms)


def create_permutations_list(answers: list) -> list:
    """
    Kombiniert die Permutationen für mehrere Antworten.
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
