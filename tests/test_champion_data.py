import os
import sys
import pytest

# Add the project root to sys.path so that `cogs` can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cogs.champion.cog import ChampionData

@pytest.mark.asyncio
async def test_add_and_get_total(tmp_path):
    db_path = tmp_path / "subdir" / "points.db"
    data = ChampionData(str(db_path))

    total = await data.add_delta("user1", 10, "start")
    assert total == 10
    total = await data.add_delta("user1", -3, "deduct")
    assert total == 7

    final_total = await data.get_total("user1")
    assert final_total == 7

    assert db_path.exists()
    db_path.unlink()
    assert not db_path.exists()

@pytest.mark.asyncio
async def test_get_history(tmp_path):
    db_path = tmp_path / "history" / "points.db"
    data = ChampionData(str(db_path))

    await data.add_delta("user1", 1, "first")
    await data.add_delta("user1", 2, "second")
    await data.add_delta("user1", 3, "third")

    history = await data.get_history("user1", limit=3)
    assert [entry["delta"] for entry in history] == [3, 2, 1]
    assert [entry["reason"] for entry in history] == ["third", "second", "first"]

    db_path.unlink()
    assert not db_path.exists()

@pytest.mark.asyncio
async def test_leaderboard_and_rank(tmp_path):
    db_path = tmp_path / "leaderboard" / "points.db"
    data = ChampionData(str(db_path))

    await data.add_delta("A", 5, "A")
    await data.add_delta("B", 10, "B")
    await data.add_delta("C", 7, "C")

    leaderboard = await data.get_leaderboard(limit=3)
    assert leaderboard == [("B", 10), ("C", 7), ("A", 5)]

    rank = await data.get_rank("C")
    assert rank == (2, 7)

    db_path.unlink()
    assert not db_path.exists()
