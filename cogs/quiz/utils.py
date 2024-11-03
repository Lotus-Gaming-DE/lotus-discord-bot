# cogs/quiz/utils.py
import re
from unidecode import unidecode
import difflib


def check_answer(user_answer, correct_answers, threshold=0.8):
    normalized_user_answer = normalize_text(user_answer)
    for ans in correct_answers:
        normalized_correct_answer = normalize_text(ans)
        similarity = difflib.SequenceMatcher(
            None, normalized_user_answer, normalized_correct_answer).ratio()
        if similarity >= threshold:
            return True
    return False


def create_permutations(answer):
    permutations = [answer.lower(), unidecode(answer.lower())]
    # Entferne Sonderzeichen und erstelle weitere Permutationen
    cleaned_answer = re.sub(r'[^\w\s]', '', answer.lower())
    permutations.append(cleaned_answer)
    permutations.append(unidecode(cleaned_answer))
    return list(set(permutations))


def normalize_text(text):
    text = unidecode(text.strip().lower())
    text = re.sub(r'\s+', ' ', text)  # Mehrfache Leerzeichen reduzieren
    text = re.sub(r'[^\w\s]', '', text)  # Sonderzeichen entfernen
    return text
