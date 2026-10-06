from __future__ import annotations

from dataclasses import dataclass

import discord

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)

FOREVER_GOLD = 0xF5C542
CUSTOM_ID_PREFIX = "forever_role:"


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

_FACTIONS = (
    # key, Titel, Emoji-Name (Server-Emoji), Fallback, Button-Stil
    ("horde", "Horde", "wcr_horde", "🔴", discord.ButtonStyle.danger),
    ("alliance", "Allianz", "wcr_alliance", "🔵", discord.ButtonStyle.primary),
)

PANEL_HEADER = (
    "## ♾️ WoW: Forever – Gilden-Rollen\n"
    "Gilden für **World of Warcraft: Forever** (Release 4. November 2026) — "
    "nicht für Classic Hardcore."
)

PANEL_HOWTO = (
    "Wähle, in welchen Gilden du mitspielen möchtest. "
    "**Mehrfachauswahl ist möglich** — ein Klick vergibt die Rolle, "
    "ein zweiter Klick entfernt sie wieder.\n"
    "-# Alles nur Planung: Welche Gilden wirklich starten, entscheidet sich "
    "an der Anzahl der Interessenten."
)

PANEL_FOOTER = "-# Rollen jederzeit änderbar · Antworten sieht nur du"


def roles_for_faction(faction: str) -> list[ForeverGuildRole]:
    return [r for r in FOREVER_ROLES if r.faction == faction]


def role_title(role: ForeverGuildRole) -> str:
    faction = "Horde" if role.faction == "horde" else "Allianz"
    return f"{faction} · {role.label}"


async def toggle_forever_role(
    member: discord.Member, role: discord.Role, entry: ForeverGuildRole
) -> bool:
    """Schaltet die Rolle um. Gibt True zurück, wenn sie jetzt vergeben ist."""
    if role in member.roles:
        await member.remove_roles(role, reason=f"Forever-Panel: {role_title(entry)}")
        return False
    await member.add_roles(role, reason=f"Forever-Panel: {role_title(entry)}")
    return True


def selection_summary(role_ids: set[int]) -> str:
    mine = [role_title(r) for r in FOREVER_ROLES if r.role_id in role_ids]
    if not mine:
        return "Aktuell hast du **keine** Forever-Gildenrolle."
    return "Deine Forever-Gilden: " + ", ".join(f"**{t}**" for t in mine)


class ForeverRoleButton(discord.ui.Button):
    def __init__(self, entry: ForeverGuildRole, style: discord.ButtonStyle) -> None:
        super().__init__(
            label=entry.label,
            emoji=entry.emoji,
            style=style,
            custom_id=f"{CUSTOM_ID_PREFIX}{entry.role_id}",
        )
        self.entry = entry

    async def callback(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        member = interaction.user
        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Das geht nur auf dem Server.", ephemeral=True
            )
            return

        role = guild.get_role(self.entry.role_id)
        if role is None:
            logger.error("[ForeverRoles] Rolle %s nicht gefunden.", self.entry.role_id)
            await interaction.response.send_message(
                "Diese Rolle existiert nicht mehr — bitte melde das dem Mod-Team.",
                ephemeral=True,
            )
            return

        try:
            added = await toggle_forever_role(member, role, self.entry)
        except discord.Forbidden:
            logger.error(
                "[ForeverRoles] Keine Rechte für Rolle %s (Hierarchie prüfen).",
                self.entry.role_id,
            )
            await interaction.response.send_message(
                "Ich darf diese Rolle gerade nicht vergeben — bitte melde das dem Mod-Team.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as exc:
            logger.warning("[ForeverRoles] Rollen-Update fehlgeschlagen: %s", exc)
            await interaction.response.send_message(
                "Das hat gerade nicht geklappt, versuch es bitte gleich nochmal.",
                ephemeral=True,
            )
            return

        verb = "hinzugefügt ✅" if added else "entfernt ❌"
        # Das Member-Objekt aus der Interaktion kennt die Änderung noch nicht.
        projected = {r.id for r in member.roles}
        (projected.add if added else projected.discard)(role.id)
        await interaction.response.send_message(
            f"**{role_title(self.entry)}** {verb}\n{summary}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


class ForeverRolesLayoutView(discord.ui.LayoutView):
    """Persistentes Components-V2 Panel zur Selbstvergabe der Forever-Gildenrollen."""

    def __init__(self, emojis: dict[str, str] | None = None) -> None:
        super().__init__(timeout=None)
        emojis = emojis or {}

        children: list[discord.ui.Item] = [
            discord.ui.TextDisplay(PANEL_HEADER),
            discord.ui.Separator(),
            discord.ui.TextDisplay(PANEL_HOWTO),
        ]
        for key, title, emoji_name, fallback, style in _FACTIONS:
            icon = emojis.get(emoji_name) or fallback
            children.append(discord.ui.Separator())
            children.append(discord.ui.TextDisplay(f"### {icon} {title}"))
            children.append(
                discord.ui.ActionRow(
                    *(ForeverRoleButton(r, style) for r in roles_for_faction(key))
                )
            )
        children.append(discord.ui.Separator())
        children.append(discord.ui.TextDisplay(PANEL_FOOTER))

        self.add_item(discord.ui.Container(*children, accent_color=FOREVER_GOLD))
