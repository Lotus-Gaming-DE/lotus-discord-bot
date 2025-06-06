import asyncio
import pytest


from cogs.champion.cog import ChampionCog
from cogs.champion.data import ChampionData
import cogs.champion.cog as champion_cog_mod


class DummyBot:
    def __init__(self):
        self.data = {"champion": {"roles": []}}
        self.main_guild = None
        self.guilds = []


class DummyRole:
    def __init__(self, name):
        self.name = name


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

    async def fetch_member(self, uid):
        self.fetch_calls += 1
        return await super().fetch_member(uid)


@pytest.mark.asyncio
async def test_update_user_score_saves_and_calls(
    monkeypatch, patch_logged_task, tmp_path
):
    bot = DummyBot()
    cog = ChampionCog(bot)
    cog.data = ChampionData(str(tmp_path / "points.db"))

    called = []

    async def fake_apply(user_id, score):
        called.append((user_id, score))

    patch_logged_task(champion_cog_mod)

    tasks = []

    def schedule_task(coro, logger=None):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    monkeypatch.setattr(champion_cog_mod, "create_logged_task", schedule_task)
    monkeypatch.setattr(cog, "_apply_champion_role", fake_apply)

    total = await cog.update_user_score(123, 5, "test")
    await asyncio.gather(*tasks)
    assert total == 5
    assert called == [("123", 5)]
    cog.cog_unload()
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_get_current_role(patch_logged_task):
    patch_logged_task(champion_cog_mod)
    bot = DummyBot()
    bot.data["champion"]["roles"] = [
        {"name": "Gold", "threshold": 50},
        {"name": "Silver", "threshold": 20},
    ]
    cog = ChampionCog(bot)

    assert cog.get_current_role(55) == "Gold"
    assert cog.get_current_role(25) == "Silver"
    assert cog.get_current_role(10) is None
    cog.cog_unload()


@pytest.mark.asyncio
async def test_apply_role_removes_when_below_threshold(monkeypatch, patch_logged_task):
    patch_logged_task(champion_cog_mod)
    bot = DummyBot()
    bot.data["champion"]["roles"] = [{"name": "Silver", "threshold": 5}]

    silver = DummyRole("Silver")
    member = DummyMember([silver])
    guild = DummyGuild(member, [silver])
    bot.main_guild = guild

    monkeypatch.setattr(champion_cog_mod.discord, "Guild", DummyGuild)
    monkeypatch.setattr(
        champion_cog_mod.discord.utils,
        "get",
        lambda seq, *, name=None: next((r for r in seq if r.name == name), None),
    )

    cog = ChampionCog(bot)

    await cog._apply_champion_role("123", 0)

    assert member.removed == [silver]
    assert member.added == []
    cog.cog_unload()
    await cog.data.close()


@pytest.mark.asyncio
async def test_apply_role_prefers_get_member(monkeypatch):
    bot = DummyBot()
    member = DummyMember([])
    guild = DummyGuildGet(member, [])
    bot.main_guild = guild

    monkeypatch.setattr(champion_cog_mod.discord, "Guild", DummyGuildGet)
    monkeypatch.setattr(
        champion_cog_mod.discord.utils,
        "get",
        lambda seq, *, name=None: next((r for r in seq if r.name == name), None),
    )

    cog = ChampionCog(bot)

    await cog._apply_champion_role("123", 0)

    assert guild.get_calls == 1
    assert guild.fetch_calls == 0
    cog.cog_unload()
    await cog.data.close()
