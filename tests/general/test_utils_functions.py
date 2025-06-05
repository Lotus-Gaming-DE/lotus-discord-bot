import os
import sys


from cogs.quiz.utils import create_permutations, create_permutations_list, normalize_text


def test_create_permutations():
    perms = set(create_permutations("Café-au Lait!"))
    expected = {"café-au lait!", "cafe-au lait!", "caféau lait", "cafeau lait"}
    assert perms == expected


def test_create_permutations_list():
    result = set(create_permutations_list(["Café", "Tea"]))
    expected = set(create_permutations("Café")) | set(create_permutations("Tea"))
    assert result == expected


def test_normalize_text():
    assert normalize_text("  Héllo,   Wörld!! ") == "hello world"
