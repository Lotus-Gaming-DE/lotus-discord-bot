# cogs/quiz/utils.py
import re
from unidecode import unidecode


def check_answer(user_answer, correct_answers):
    normalized_answer = unidecode(user_answer.strip().lower())
    return any(normalized_answer == unidecode(ans.lower()) for ans in correct_answers)


def create_permutations(answer):
    permutations = [answer.lower(), unidecode(answer.lower())]
    if ' ' in answer:
        words = answer.split()
        permutations += [' '.join(words[::-1]).lower(),
                         unidecode(' '.join(words[::-1])).lower()]
    return permutations
