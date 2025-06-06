import pytest


from cogs.champion.data import ChampionData


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
    await data.close()
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

    await data.close()
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

    await data.close()
    db_path.unlink()
    assert not db_path.exists()


@pytest.mark.asyncio
async def test_delete_user(tmp_path):
    db_path = tmp_path / "cleanup" / "points.db"
    data = ChampionData(str(db_path))

    await data.add_delta("user1", 5, "test")
    await data.add_delta("user2", 3, "test")

    await data.delete_user("user1")

    leaderboard = await data.get_leaderboard(limit=10)
    ids = [uid for uid, _ in leaderboard]
    assert "user1" not in ids
    assert await data.get_total("user1") == 0

    await data.close()
    db_path.unlink()
    assert not db_path.exists()


@pytest.mark.asyncio
async def test_get_history_large_dataset(tmp_path):
    db_path = tmp_path / "large" / "points.db"
    data = ChampionData(str(db_path))

    await data.init_db()
    db = await data._get_db()
    await db.executemany(
        "INSERT INTO history(user_id, delta, reason, date) VALUES (?, ?, ?, ?)",
        [("user1", i, "bulk", "t") for i in range(5000)],
    )
    await db.commit()

    import asyncio

    history = await asyncio.wait_for(data.get_history("user1", limit=5), 0.5)
    assert len(history) == 5

    cur = await db.execute(
        "EXPLAIN QUERY PLAN \n"
        "SELECT delta, reason, date FROM history \n"
        "WHERE user_id = ? ORDER BY date DESC LIMIT ?",
        ("user1", 5),
    )
    plan = " ".join(row[3] for row in await cur.fetchall())
    assert "USING INDEX idx_history_user" in plan

    await data.close()
    db_path.unlink()
    assert not db_path.exists()
