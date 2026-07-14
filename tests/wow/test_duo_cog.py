"""Focused tests for the DuoCog hook logic (milestone/death).

The forum/thread wiring is faked; the point is to lock down the decision
logic: duo bonus only when BOTH partners reached a milestone, exactly once,
and a memorial that flips the team into mourning on a partner's death.
"""

from types import SimpleNamespace

import pytest

from lotus_bot.cogs.wow.duo_cog import DUO_MILESTONE_BONUS, DuoCog
from lotus_bot.cogs.wow.duo_data import DuoData

pytestmark = pytest.mark.asyncio


class FakeWowData:
    def __init__(self, levels, milestones):
        self._levels = levels
        self._milestones = milestones

    async def milestone_exists(self, character_key, level):
        return (character_key, level) in self._milestones

    async def get_snapshot(self):
        return {
            key: SimpleNamespace(
                character_key=key,
                name=key,
                level=level,
                class_id=1,
                race_id=2,
                is_ghost=False,
            )
            for key, level in self._levels.items()
        }


class FakeChampion:
    def __init__(self):
        self.updates = []

    async def update_user_score(self, user_id, delta, reason):
        self.updates.append((user_id, delta, reason))
        return delta


class FakeBot:
    def __init__(self, wow, champion):
        self._wow = wow
        self._champion = champion
        self.views = []

    def add_view(self, view):
        self.views.append(view)

    def get_cog(self, name):
        return {"WoWCog": self._wow, "ChampionCog": self._champion}.get(name)

    def get_channel(self, channel_id):
        return None

    async def wait_until_ready(self):
        return


class FakeThread:
    def __init__(self):
        self.sends = []
        self.edits = []

    async def send(self, content=None, embed=None, **kwargs):
        self.sends.append((content, embed))
        return SimpleNamespace(pin=self._noop)

    async def edit(self, **kwargs):
        self.edits.append(kwargs)

    async def _noop(self):
        return


async def _make_cog(tmp_path, levels, milestones):
    champion = FakeChampion()
    wow = SimpleNamespace(data=FakeWowData(levels, milestones))
    cog = DuoCog(FakeBot(wow, champion))
    # Kill the background startup task and repoint at a throwaway DB before any
    # await touches the default on-disk path.
    for task in list(cog.tasks):
        task.cancel()
    cog.data = DuoData(str(tmp_path / "duo.db"))
    thread = FakeThread()

    async def _fetch(_thread_id):
        return thread

    cog._fetch_thread = _fetch
    return cog, champion, thread


async def test_milestone_bonus_only_when_both_reached_and_once(tmp_path):
    cog, champion, thread = await _make_cog(
        tmp_path,
        levels={"c1": 40, "c2": 40},
        milestones={("c1", 40), ("c2", 40)},
    )
    team = await cog.data.create_team(
        "Team X", 100, [(1, "c1", "Ash"), (2, "c2", "Nyx")]
    )

    await cog.on_character_milestone("c2", 40)

    bonus = DUO_MILESTONE_BONUS[40]
    assert sorted(u[0] for u in champion.updates) == [1, 2]
    assert all(u[1] == bonus for u in champion.updates)
    assert await cog.data.duo_milestone_exists(team.team_id, 40) is True
    assert any("gemeinsam" in (c or "").lower() for c, _ in thread.sends)

    # Re-firing the same milestone must not double-award.
    champion.updates.clear()
    await cog.on_character_milestone("c2", 40)
    assert champion.updates == []


async def test_milestone_nudge_when_only_one_reached(tmp_path):
    cog, champion, thread = await _make_cog(
        tmp_path,
        levels={"c1": 35, "c2": 40},
        milestones={("c2", 40)},
    )
    team = await cog.data.create_team(
        "Team Y", 101, [(1, "c1", "Ash"), (2, "c2", "Nyx")]
    )

    await cog.on_character_milestone("c2", 40)

    assert champion.updates == []
    assert await cog.data.duo_milestone_exists(team.team_id, 40) is False
    assert len(thread.sends) == 1  # a nudge, not a celebration


async def test_death_posts_memorial_and_sets_mourning(tmp_path):
    cog, champion, thread = await _make_cog(
        tmp_path, levels={"c1": 42, "c2": 42}, milestones=set()
    )
    team = await cog.data.create_team(
        "Team Z", 102, [(1, "c1", "Ash"), (2, "c2", "Nyx")]
    )

    await cog.on_character_death("c1", 42)

    assert thread.sends, "expected a memorial message"
    _, embed = thread.sends[0]
    assert embed is not None
    assert (await cog.data.get_team(team.team_id)).status == "mourning"


async def test_milestone_ignores_untracked_level(tmp_path):
    cog, champion, thread = await _make_cog(
        tmp_path, levels={"c1": 42, "c2": 42}, milestones=set()
    )
    await cog.data.create_team("Team Q", 103, [(1, "c1", "A"), (2, "c2", "B")])

    await cog.on_character_milestone("c1", 42)  # 42 is not a milestone level

    assert champion.updates == []
    assert thread.sends == []
