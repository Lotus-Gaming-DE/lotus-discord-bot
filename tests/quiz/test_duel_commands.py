import pytest


class DummyChampionData:
    def __init__(self):
        self.stats_calls = []
        self.leader_calls = []

    async def get_duel_stats(self, uid):
        self.stats_calls.append(uid)
        return {"win": 1, "loss": 2, "tie": 0}

    async def get_duel_leaderboard(self, limit=10):
        self.leader_calls.append(limit)
        return [("1", 3, 0, 0), ("2", 2, 1, 0)]

    async def record_duel_result(self, uid, res):
        pass


class DummyChampionCog:
    def __init__(self):
        self.data = DummyChampionData()


class DummyMember:
    def __init__(self, uid, name="user"):
        self.id = int(uid)
        self.display_name = name
        self.mention = f"<@{uid}>"


class DummyGuild:
    def __init__(self):
        self.members = {1: DummyMember(1, "user1"), 2: DummyMember(2, "user2")}

    def get_member(self, uid):
        return self.members.get(uid)

    async def fetch_member(self, uid):
        return self.members.get(uid)


class DummyBot:
    def __init__(self):
        self._champion = DummyChampionCog()

    def get_cog(self, name):
        if name == "ChampionCog":
            return self._champion
        return None


class SlashResponse:
    def __init__(self):
        self.messages = []
        self.deferred = False

    async def send_message(self, msg, **kwargs):
        self.messages.append((msg, kwargs))

    async def defer(self, thinking=False):
        self.deferred = True


class SlashFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, content):
        self.sent.append(content)


class SlashInteraction:
    def __init__(self, bot, user, guild):
        self.client = bot
        self.user = user
        self.guild = guild
        self.response = SlashResponse()
        self.followup = SlashFollowup()


@pytest.mark.asyncio
async def test_duelstats_command():
    from lotusbot.cogs.quiz.slash_commands import duelstats

    bot = DummyBot()
    guild = DummyGuild()
    inter = SlashInteraction(bot, DummyMember(1, "u1"), guild)

    await duelstats.callback(inter)

    assert bot._champion.data.stats_calls == ["1"]
    assert inter.response.messages


@pytest.mark.asyncio
async def test_duelleaderboard_command():
    from lotusbot.cogs.quiz.slash_commands import duelleaderboard

    bot = DummyBot()
    guild = DummyGuild()
    inter = SlashInteraction(bot, DummyMember(1, "u1"), guild)

    await duelleaderboard.callback(inter)

    assert inter.response.deferred is True
    assert bot._champion.data.leader_calls == [10]
    assert inter.followup.sent
