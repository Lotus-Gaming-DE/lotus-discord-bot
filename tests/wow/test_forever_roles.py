from unittest.mock import AsyncMock, MagicMock

import discord

from lotus_bot.cogs.wow.forever_roles import (
    FOREVER_ROLES,
    ForeverFactionSelect,
    ForeverGuildsLayoutView,
    selection_summary,
)

HORDE_HC = 1556277335500525749
HORDE_PVP = 1556276890853965884
ALLIANCE_PVE = 1556276986580566027


def _selects(view):
    return [c for c in view.walk_children() if isinstance(c, ForeverFactionSelect)]


def test_all_six_roles_configured():
    assert {r.role_id for r in FOREVER_ROLES} == {
        1556277335500525749,
        1556277258023346186,
        1556276890853965884,
        1556276573773111340,
        1556277083880038501,
        1556276986580566027,
    }


def test_view_has_one_select_per_faction_with_current_state_preselected():
    view = ForeverGuildsLayoutView({HORDE_HC, ALLIANCE_PVE})
    selects = _selects(view)
    assert {s.faction for s in selects} == {"horde", "alliance"}
    defaults = {int(o.value) for s in selects for o in s.options if o.default}
    assert defaults == {HORDE_HC, ALLIANCE_PVE}
    assert all(s.min_values == 0 for s in selects)  # abwählen erlaubt


def test_view_fits_components_v2_limits():
    view = ForeverGuildsLayoutView(set())
    assert len(list(view.walk_children())) + 1 <= 40


def test_selection_summary():
    assert "keine" in selection_summary(set())
    assert "Horde" in selection_summary({HORDE_HC})


def _interaction(role_ids):
    guild = MagicMock(spec=discord.Guild)
    roles = {}
    for rid in role_ids:
        role = MagicMock(spec=discord.Role)
        role.id = rid
        roles[rid] = role
    guild.get_role.side_effect = roles.get
    member = MagicMock(spec=discord.Member)
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = guild
    interaction.user = member
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction, member, roles


async def test_apply_selection_adds_new_and_removes_unselected_in_faction_only():
    view = ForeverGuildsLayoutView({HORDE_HC, ALLIANCE_PVE})
    interaction, member, roles = _interaction([r.role_id for r in FOREVER_ROLES])

    # Horde: HC abwählen, PvP wählen. Allianz-Rolle darf unberührt bleiben.
    await view.apply_selection(interaction, "horde", {HORDE_PVP})

    member.add_roles.assert_awaited_once()
    assert member.add_roles.await_args.args == (roles[HORDE_PVP],)
    member.remove_roles.assert_awaited_once()
    assert member.remove_roles.await_args.args == (roles[HORDE_HC],)

    new_view = interaction.edit_original_response.await_args.kwargs["view"]
    owned = {int(o.value) for s in _selects(new_view) for o in s.options if o.default}
    assert owned == {HORDE_PVP, ALLIANCE_PVE}


async def test_apply_selection_reports_missing_permission():
    view = ForeverGuildsLayoutView(set())
    interaction, member, _ = _interaction([r.role_id for r in FOREVER_ROLES])
    member.add_roles.side_effect = discord.Forbidden(MagicMock(status=403), "nope")
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    await view.apply_selection(interaction, "horde", {HORDE_HC})

    interaction.followup.send.assert_awaited_once()
    interaction.edit_original_response.assert_not_awaited()


def test_view_serializes_to_discord_payload():
    payload = ForeverGuildsLayoutView({HORDE_HC}).to_components()
    assert payload and payload[0]["type"] == 17  # Container


async def test_hub_button_opens_ephemeral_selection_with_current_roles():
    from lotus_bot.cogs.wow.cog import WoWPanelLayoutView

    cog = MagicMock()
    cog.bot.data = {"emojis": {}}
    hub = WoWPanelLayoutView(cog)

    role = MagicMock(spec=discord.Role)
    role.id = HORDE_HC
    other = MagicMock(spec=discord.Role)
    other.id = 42
    member = MagicMock(spec=discord.Member)
    member.roles = [role, other]
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = MagicMock(spec=discord.Guild)
    interaction.user = member
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    await hub._open_forever_guilds(interaction)

    kwargs = interaction.response.send_message.await_args.kwargs
    assert kwargs["ephemeral"] is True
    view = kwargs["view"]
    owned = {int(o.value) for s in _selects(view) for o in s.options if o.default}
    assert owned == {HORDE_HC}
