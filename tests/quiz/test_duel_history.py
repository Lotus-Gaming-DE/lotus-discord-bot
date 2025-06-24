import pytest
from lotusbot.cogs.champion.data import ChampionData


@pytest.mark.asyncio
async def test_record_and_stats(tmp_path):
    db_path = tmp_path / "points.db"
    data = ChampionData(str(db_path))

    await data.record_duel_result("A", "win")
    await data.record_duel_result("A", "loss")
    await data.record_duel_result("A", "win")
    await data.record_duel_result("B", "win")

    stats = await data.get_duel_stats("A")
    assert stats == {"win": 2, "loss": 1, "tie": 0}

    leaderboard = await data.get_duel_leaderboard(limit=2)
    assert leaderboard[0][:2] == ("A", 2)
    assert leaderboard[1][:2] == ("B", 1)

    await data.close()
