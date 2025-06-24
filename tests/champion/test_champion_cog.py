import asyncio
import json
import logging
import pytest


from cogs.champion.cog import ChampionCog
from cogs.champion.data import ChampionData
import cogs.champion.cog as champion_cog_mod
import log_setup


class DummyBot:
    def __init__(self):
        self.data = {"champion": {"roles": []}}
        self.main_guild = None
        self.guilds = []


class DummyRole:
    def __init__(self, name, rid=0):
        self.name = name
        self.id = rid


class DummyMember:
    def __init__(self, roles):
        self.roles = roles
        self.display_name = "Member"
        self.removed = []
        self.added = []

    async def remove_roles(self, *roles):
        self.removed.extend(roles)

    async def add_roles(self, role):
        self.added.append(role)


class DummyGuild:
    def __init__(self, member, roles):
        self._member = member
        self.roles = roles

    def get_member(self, uid):
        return None

    def get_role(self, rid):
        return next((r for r in self.roles if getattr(r, "id", None) == rid), None)

    async def fetch_member(self, uid):
        return self._member


class DummyGuildGet(DummyGuild):
    def __init__(self, member, roles):
        super().__init__(member, roles)
        self.get_calls = 0
        self.fetch_calls = 0

    def get_member(self, uid):
        self.get_calls += 1
        return self._member

    def get_role(self, rid):
        return super().get_role(rid)

    async def fetch_member(self, uid):
        self.fetch_calls += 1
        return await super().fetch_member(uid)


@pytest.mark.asyncio
async def test_update_user_score_saves_and_calls(
    monkeypatch, patch_logged_task, tmp_path
):
    bot = DummyBot()
    patch_logged_task(champion_cog_mod, log_setup)
    tasks = []

    def schedule_task(coro, logger=None):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    monkeypatch.setattr(log_setup, "create_logged_task", schedule_task)
    cog = ChampionCog(bot)
    cog.data = ChampionData(str(tmp_path / "points.db"))

    called = []

    async def fake_apply(user_id, score):
        called.append((user_id, score))

    monkeypatch.setattr(cog, "_apply_champion_role", fake_apply)

    total = await cog.update_user_score(123, 5, "test")
    await cog.update_queue.join()
    assert total == 5
    assert called == [("123", 5)]
    await cog.cog_unload()


@pytest.mark.asyncio
async def test_updates_processed_in_order(monkeypatch, patch_logged_task, tmp_path):
    bot = DummyBot()
    patch_logged_task(champion_cog_mod, log_setup)
    tasks = []

    def schedule_task(coro, logger=None):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    monkeypatch.setattr(log_setup, "create_logged_task", schedule_task)
    cog = ChampionCog(bot)
    cog.data = ChampionData(str(tmp_path / "points.db"))

    order = []

    async def fake_apply(user_id, score):
        await asyncio.sleep(0)
        order.append((user_id, score))

    monkeypatch.setattr(cog, "_apply_champion_role", fake_apply)

    for i in range(3):
        await cog.update_user_score(123 + i, i + 1, "test")

    await cog.update_queue.join()

    assert order == [("123", 1), ("124", 2), ("125", 3)]
    await cog.cog_unload()


@pytest.mark.asyncio
async def test_get_current_role(patch_logged_task):
    patch_logged_task(champion_cog_mod, log_setup)
    bot = DummyBot()
    bot.data["champion"]["roles"] = [
        {"name": "Gold", "threshold": 50, "id": 1},
        {"name": "Silver", "threshold": 20, "id": 2},
    ]
    cog = ChampionCog(bot)

    assert cog.get_current_role(55).name == "Gold"
    assert cog.get_current_role(25).name == "Silver"
    assert cog.get_current_role(10) is None
    await cog.cog_unload()


@pytest.mark.asyncio
async def test_apply_role_removes_when_below_threshold(monkeypatch, patch_logged_task):
    patch_logged_task(champion_cog_mod, log_setup)
    bot = DummyBot()
    bot.data["champion"]["roles"] = [{"name": "Silver", "threshold": 5, "id": 1}]

    silver = DummyRole("Silver", 1)
    member = DummyMember([silver])
    guild = DummyGuild(member, [silver])
    bot.main_guild = guild

    monkeypatch.setattr(champion_cog_mod.discord, "Guild", DummyGuild)

    cog = ChampionCog(bot)

    await cog._apply_champion_role("123", 0)

    assert member.removed == [silver]
    assert member.added == []
    await cog.cog_unload()


@pytest.mark.asyncio
async def test_apply_role_prefers_get_member(monkeypatch, patch_logged_task):
    bot = DummyBot()
    patch_logged_task(champion_cog_mod, log_setup)
    member = DummyMember([])
    guild = DummyGuildGet(member, [])
    bot.main_guild = guild

    monkeypatch.setattr(champion_cog_mod.discord, "Guild", DummyGuildGet)

    cog = ChampionCog(bot)

    await cog._apply_champion_role("123", 0)

    assert guild.get_calls == 1
    assert guild.fetch_calls == 0
    await cog.cog_unload()


@pytest.mark.asyncio
async def test_apply_role_ignores_same_name_if_id_missing(
    monkeypatch, patch_logged_task
):
    patch_logged_task(champion_cog_mod, log_setup)
    bot = DummyBot()
    bot.data["champion"]["roles"] = [{"name": "Silver", "threshold": 5, "id": 999}]

    silver_real = DummyRole("Silver", 1)
    member = DummyMember([])
    guild = DummyGuild(member, [silver_real])
    bot.main_guild = guild

    monkeypatch.setattr(champion_cog_mod.discord, "Guild", DummyGuild)

    cog = ChampionCog(bot)

    await cog._apply_champion_role("123", 5)

    assert member.added == []
    await cog.cog_unload()


@pytest.mark.asyncio
async def test_worker_cancelled_on_unload(monkeypatch, patch_logged_task):
    bot = DummyBot()

    patch_logged_task(champion_cog_mod, log_setup)

    tasks = []

    def schedule_task(coro, logger=None):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    monkeypatch.setattr(log_setup, "create_logged_task", schedule_task)

    cog = ChampionCog(bot)

    await cog.cog_unload()

    assert cog.worker_task.cancelled()


@pytest.mark.asyncio
async def test_queue_raises_when_full(monkeypatch, patch_logged_task, caplog):
    patch_logged_task(champion_cog_mod, log_setup)
    bot = DummyBot()

    # erzwinge eine kleine Warteschlange für den Test
    original_queue = asyncio.Queue

    def small_queue(*args, **kwargs):
        return original_queue(maxsize=2)

    monkeypatch.setattr(champion_cog_mod.asyncio, "Queue", small_queue)
    cog = ChampionCog(bot)

    async def fake_add(user_id, delta, reason):
        return delta

    monkeypatch.setattr(cog.data, "add_delta", fake_add)

    await cog.update_user_score(1, 1, "a")
    await cog.update_user_score(2, 1, "b")
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError):
            await cog.update_user_score(3, 1, "c")

    events = [json.loads(r.getMessage()).get("event", "") for r in caplog.records]
    assert any("update_queue voll" in e for e in events)

    await cog.cog_unload()
