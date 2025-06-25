import pytest

from lotus_bot.cogs.champion.slash_commands import champion_group
from lotus_bot.permissions import moderator_only


class DummyPerms:
    def __init__(self, manage):
        self.manage_guild = manage


class DummyUser:
    def __init__(self, manage):
        self.guild_permissions = DummyPerms(manage)


class DummyResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, msg, ephemeral=False):
        self.messages.append((msg, ephemeral))


class DummyInteraction:
    def __init__(self, manage):
        self.user = DummyUser(manage)
        self.permissions = DummyPerms(manage)
        self.response = DummyResponse()


def get_predicate():
    func = moderator_only()(lambda i: None)
    return func.__discord_app_commands_checks__[0]


@pytest.mark.asyncio
async def test_moderator_only_allows_mods():
    predicate = get_predicate()
    inter = DummyInteraction(True)
    assert await predicate(inter) is True
    assert inter.response.messages == []


@pytest.mark.asyncio
async def test_moderator_only_blocks_non_mods():
    predicate = get_predicate()
    inter = DummyInteraction(False)
    assert await predicate(inter) is False
    assert inter.response.messages
    msg, ephemeral = inter.response.messages[0]
    assert "❌" in msg
    assert ephemeral is True


def test_mod_commands_have_default_permissions():
    mod_names = {"give", "remove", "set", "reset", "history", "clean"}
    cmds = {c.name: c for c in champion_group.commands}
    for name in mod_names:
        assert cmds[name].default_permissions.manage_guild is True
