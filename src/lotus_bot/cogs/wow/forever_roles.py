from __future__ import annotations

from dataclasses import dataclass

import discord

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)

FOREVER_GOLD = discord.Colour(0xF5C542)


@dataclass(frozen=True)
class ForeverGuildRole:
    """Eine selbst wählbare WoW-Forever-Gildenrolle."""

    role_id: int
    faction: str  # "horde" | "alliance"
    mode: str  # "hc" | "pvp" | "pve"
    label: str
    emoji: str


FOREVER_ROLES: tuple[ForeverGuildRole, ...] = (
    ForeverGuildRole(1556277335500525749, "horde", "hc", "Hardcore", "💀"),
    ForeverGuildRole(1556276890853965884, "horde", "pvp", "PvP", "⚔️"),
    ForeverGuildRole(1556277083880038501, "horde", "pve", "PvE", "🐉"),
    ForeverGuildRole(1556277258023346186, "alliance", "hc", "Hardcore", "💀"),
    ForeverGuildRole(1556276573773111340, "alliance", "pvp", "PvP", "⚔️"),
    ForeverGuildRole(1556276986580566027, "alliance", "pve", "PvE", "🐉"),
)

# key, Titel, Server-Emoji, Fallback
_FACTIONS = (
    ("horde", "Horde", "wcr_horde", "🔴"),
    ("alliance", "Allianz", "wcr_alliance", "🔵"),
)

FOREVER_INTRO = (
    "## ♾️ WoW Forever – Gilden\n"
    "Wähle, in welchen **WoW-Forever-Gilden** du mitspielen möchtest "
    "(Release 4. November 2026). Mehrfachauswahl ist möglich — "
    "was du abwählst, wird entfernt.\n"
    "-# Deine aktuelle Auswahl ist schon markiert. Änderungen gelten sofort."
)


def roles_for_faction(faction: str) -> list[ForeverGuildRole]:
    return [r for r in FOREVER_ROLES if r.faction == faction]


def role_title(role: ForeverGuildRole) -> str:
    faction = "Horde" if role.faction == "horde" else "Allianz"
    return f"{faction} · {role.label}"


def selection_summary(role_ids: set[int]) -> str:
    mine = [role_title(r) for r in FOREVER_ROLES if r.role_id in role_ids]
    if not mine:
        return "Aktuell hast du **keine** Forever-Gildenrolle."
    return "Deine Forever-Gilden: " + ", ".join(f"**{t}**" for t in mine)


class ForeverFactionSelect(discord.ui.Select):
    """Mehrfachauswahl der Gilden einer Fraktion; leere Auswahl entfernt alle."""

    def __init__(self, parent: "ForeverGuildsLayoutView", faction: str, title: str):
        owned = parent.owned_ids
        options = [
            discord.SelectOption(
                label=r.label,
                value=str(r.role_id),
                emoji=r.emoji,
                default=r.role_id in owned,
            )
            for r in roles_for_faction(faction)
        ]
        super().__init__(
            placeholder=f"Keine {title}-Gilde",
            min_values=0,
            max_values=len(options),
            options=options,
        )
        self.parent_view = parent
        self.faction = faction

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.parent_view.apply_selection(
            interaction, self.faction, {int(v) for v in self.values}
        )


class ForeverGuildsLayoutView(discord.ui.LayoutView):
    """Ephemere Auswahl der Forever-Gildenrollen (Horde / Allianz getrennt)."""

    def __init__(
        self,
        owned_ids: set[int],
        emojis: dict[str, str] | None = None,
        status: str | None = None,
    ) -> None:
        super().__init__(timeout=600)
        self.owned_ids = set(owned_ids)
        self.emojis = emojis or {}

        children: list[discord.ui.Item] = [discord.ui.TextDisplay(FOREVER_INTRO)]
        for faction, title, emoji_name, fallback in _FACTIONS:
            icon = self.emojis.get(emoji_name) or fallback
            children.append(discord.ui.Separator())
            children.append(discord.ui.TextDisplay(f"### {icon} {title}"))
            children.append(
                discord.ui.ActionRow(ForeverFactionSelect(self, faction, title))
            )
        children.append(discord.ui.Separator())
        children.append(
            discord.ui.TextDisplay(status or selection_summary(self.owned_ids))
        )
        self.add_item(discord.ui.Container(*children, accent_colour=FOREVER_GOLD))

    async def apply_selection(
        self, interaction: discord.Interaction, faction: str, chosen: set[int]
    ) -> None:
        guild = interaction.guild
        member = interaction.user
        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Das geht nur auf dem Server.", ephemeral=True
            )
            return

        group = {r.role_id for r in roles_for_faction(faction)}
        # Der Stand in der Auswahl-View ist maßgeblich, nicht der (ggf. alte)
        # Member-Cache der Interaktion.
        to_add = chosen - self.owned_ids
        to_remove = (self.owned_ids & group) - chosen
        roles_add = [guild.get_role(i) for i in to_add]
        roles_remove = [guild.get_role(i) for i in to_remove]
        if any(r is None for r in roles_add + roles_remove):
            logger.error("[ForeverRoles] Mindestens eine Rolle fehlt im Server.")
            await interaction.response.send_message(
                "Eine Rolle existiert nicht mehr — bitte melde das dem Mod-Team.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        try:
            if roles_add:
                await member.add_roles(*roles_add, reason="WoW-Hub: Forever-Gilden")
            if roles_remove:
                await member.remove_roles(
                    *roles_remove, reason="WoW-Hub: Forever-Gilden"
                )
        except discord.Forbidden:
            logger.error("[ForeverRoles] Keine Rechte (Rollenhierarchie prüfen).")
            await interaction.followup.send(
                "❌ Mir fehlt die Berechtigung. Der Bot braucht *Manage Roles* "
                "und muss eine Rolle ÜBER den Forever-Gildenrollen haben.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as exc:
            logger.warning("[ForeverRoles] Rollen-Update fehlgeschlagen: %s", exc)
            await interaction.followup.send(
                "❌ Discord-Fehler beim Rollen-Update, bitte gleich nochmal versuchen.",
                ephemeral=True,
            )
            return

        new_owned = (self.owned_ids - group) | chosen
        view = ForeverGuildsLayoutView(
            new_owned,
            self.emojis,
            status="✅ Gespeichert. " + selection_summary(new_owned),
        )
        await interaction.edit_original_response(view=view)
