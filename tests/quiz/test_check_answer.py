from cogs.quiz.utils import check_answer


def test_exact_match():
    assert check_answer("Paris", ["Paris"]) is True


def test_partial_match():
    # user answer is substring of correct answer
    assert check_answer("nvidia", ["NVIDIA Corporation"]) is True
    # correct answer is substring of user answer
    assert check_answer("League of Legends", ["League"]) is True


def test_fuzzy_match():
    # close but not substring
    assert check_answer("pokeman", ["Pokemon"]) is True


def test_mismatch():
    assert check_answer("London", ["Paris"]) is False


def test_empty_normalized_input():
    assert check_answer("//", ["Paris"]) is False


def test_whitespace_input():
    assert check_answer("   ", ["Paris"]) is False
