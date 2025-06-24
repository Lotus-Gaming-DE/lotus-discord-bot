import pytest

from lotusbot.cogs.champion.slash_commands import leaderboard, rank


class DummyMember:
    def __init__(self, uid, name):
        self.id = uid
        self.display_name = name
        self.mention = f"<@{uid}>"


class DummyData:
    def __init__(self):
        self.rank_calls = []

    async def get_leaderboard(self, limit=30):
        return [("1", 60), ("2", 30), ("3", 10)]

    async def get_rank(self, uid):
        self.rank_calls.append(uid)
        if uid == "1":
            return (2, 30)
        if uid == "2":
            return (1, 60)
        return None


class DummyRole:
    def __init__(self, name, threshold):
        self.name = name
        self.threshold = threshold


class DummyCog:
    def __init__(self):
        self.data = DummyData()
        self.roles = [DummyRole("Gold", 50), DummyRole("Silver", 20)]

    def get_current_role(self, score):
        for role in self.roles:
            if score >= role.threshold:
                return role
        return None


class DummyResponseDefer:
    def __init__(self):
        self.deferred = False

    async def defer(self, thinking=False):
        self.deferred = thinking


class DummyFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, message, ephemeral=False):
        self.sent.append((message, ephemeral))


class DummyResponseMsg:
    def __init__(self):
        self.messages = []

    async def send_message(self, msg, ephemeral=False):
        self.messages.append((msg, ephemeral))


class DummyGuild:
    def __init__(self):
        self.members = {
            1: DummyMember(1, "Alice"),
            2: DummyMember(2, "Bob"),
            3: DummyMember(3, "Cara"),
        }

    def get_member(self, uid):
        return self.members.get(uid)

    async def fetch_member(self, uid):
        return self.members.get(uid)


class DummyBot:
    def __init__(self):
        self._cog = DummyCog()
        self.data = {"emojis": {}}

    def get_cog(self, name):
        return self._cog if name == "ChampionCog" else None


class DummyInteractionBoard:
    def __init__(self, bot, guild):
        self.client = bot
        self.user = DummyMember(99, "Tester")
        self.guild = guild
        self.response = DummyResponseDefer()
        self.followup = DummyFollowup()


class DummyInteractionRank:
    def __init__(self, bot, user):
        self.client = bot
        self.user = user
        self.guild = None
        self.response = DummyResponseMsg()
        self.followup = DummyResponseMsg()


@pytest.mark.asyncio
async def test_leaderboard_groups_and_public():
    bot = DummyBot()
    guild = DummyGuild()
    inter = DummyInteractionBoard(bot, guild)

    await leaderboard.callback(inter)

    assert inter.response.deferred is True
    assert inter.followup.sent
    msg, ephemeral = inter.followup.sent[0]
    assert "Gold" in msg
    assert "Silver" in msg
    assert "Champion" in msg
    assert "Alice" in msg and "Bob" in msg and "Cara" in msg
    assert ephemeral is False


@pytest.mark.asyncio
async def test_rank_self_and_other():
    bot = DummyBot()
    inter1 = DummyInteractionRank(bot, DummyMember(1, "Self"))

    await rank.callback(inter1, None)

    assert inter1.response.messages
    msg, ephemeral = inter1.response.messages[0]
    assert "Du bist Rang 2" in msg
    assert ephemeral is False

    target = DummyMember(2, "Other")
    inter2 = DummyInteractionRank(bot, DummyMember(1, "Self"))

    await rank.callback(inter2, target)

    assert inter2.response.messages
    msg2, ephemeral2 = inter2.response.messages[0]
    assert "Other ist Rang 1" in msg2
    assert ephemeral2 is False
    assert bot._cog.data.rank_calls == ["1", "2"]
