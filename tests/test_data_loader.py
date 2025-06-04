import os
import sys
import json
import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cogs.quiz.data_loader import DataLoader


def test_load_existing_questions():
    # use the provided sample data inside data/quiz
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "quiz"))
    loader = DataLoader(base_path=base_path)
    data = loader.load_questions("de")
    assert isinstance(data, dict)
    # ensure keys from example file are present
    assert "wcr" in data and "d4" in data
    # there should be at least one question
    assert any(len(cat) > 0 for area in data.values() for cat in area.values())


def test_missing_file_returns_empty(tmp_path):
    # point loader to an empty temporary directory
    loader = DataLoader(base_path=str(tmp_path))
    # should not raise and return an empty dict
    result = loader.load_questions("de")
    assert result == {}
