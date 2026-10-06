from unittest.mock import AsyncMock, MagicMock

import discord

from lotus_bot.cogs.community.forever_view import (
    FOREVER_ROLES,
    ForeverRoleButton,
    ForeverRolesLayoutView,
    selection_summary,
    toggle_forever_role,
)

REQUESTED_ROLE_IDS = {
    1556277335500525749,
    1556277258023346186,
    1556276890853965884,
    1556276573773111340,
    1556277083880038501,
    1556276986580566027,
}


def _walk(view):
    return list(view.walk_children())


def test_all_six_roles_configured():
    assert {r.role_id for r in FOREVER_ROLES} == REQUESTED_ROLE_IDS


def test_view_has_one_unique_button_per_role():
    view = ForeverRolesLayoutView({})
    buttons = [c for c in _walk(view) if isinstance(c, ForeverRoleButton)]
    ids = [b.custom_id for b in buttons]
    assert len(ids) == len(set(ids)) == len(FOREVER_ROLES)
    assert view.timeout is None


def test_view_fits_components_v2_limits():
    view = ForeverRolesLayoutView({"wcr_horde": "<:wcr_horde:1>"})
    assert len(_walk(view)) + 1 <= 40
    text = "".join(
        c.content for c in _walk(view) if isinstance(c, discord.ui.TextDisplay)
    )
    assert len(text) < 4000


def test_selection_summary():
    assert "keine" in selection_summary(set())
    assert "Horde" in selection_summary({1556277335500525749})


async def test_toggle_adds_then_removes():
    entry = FOREVER_ROLES[0]
    role = MagicMock(spec=discord.Role)
    member = MagicMock(spec=discord.Member)
    member.roles = []
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()

    assert await toggle_forever_role(member, role, entry) is True
    member.add_roles.assert_awaited_once()

    member.roles = [role]
    assert await toggle_forever_role(member, role, entry) is False
    member.remove_roles.assert_awaited_once()


async def test_button_click_replies_with_current_selection():
    entry = FOREVER_ROLES[1]
    role = MagicMock(spec=discord.Role)
    role.id = entry.role_id
    member = MagicMock(spec=discord.Member)
    member.roles = []
    member.add_roles = AsyncMock()
    guild = MagicMock(spec=discord.Guild)
    guild.get_role.return_value = role
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = guild
    interaction.user = member
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    await ForeverRoleButton(entry, discord.ButtonStyle.primary).callback(interaction)

    member.add_roles.assert_awaited_once()
    args, kwargs = interaction.response.send_message.await_args
    assert kwargs["ephemeral"] is True
    assert "PvP" in args[0]
