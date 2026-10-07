from __future__ import annotations

import math

import discord

from .forever_roles import FOREVER_ROLES, roles_for_faction

# Mitwachsende Ziele: der Balken zeigt immer den Weg zum nächsten.
GOAL_TIERS = (10, 25, 50, 100, 250, 500)
BAR_WIDTH = 5
FACTION_ROLE_IDS = frozenset(r.role_id for r in FOREVER_ROLES)

_FACTION_HEADERS = (
    ("horde", "Horde", "wcr_horde", "🔴"),
    ("alliance", "Allianz", "wcr_alliance", "🔵"),
)

FOREVER_PANEL_INTRO = (
    "## ♾️ WoW: Forever – Gilden\n"
    "Am **4. November** startet **WoW: Forever**. Wir gründen mehrere Gilden — "
    "**sag uns, wo du mitspielen willst**, dann sehen wir, welche zustande kommen.\n"
    "-# Mehrfachauswahl möglich · jederzeit änderbar"
)


def next_goal(count: int) -> int:
    return next((t for t in GOAL_TIERS if count < t), max(count, 1))


def progress_bar(count: int) -> str:
    # Aufrunden: schon die erste Person füllt einen Balkenabschnitt.
    filled = min(BAR_WIDTH, math.ceil(count * BAR_WIDTH / next_goal(count)))
    return "▰" * filled + "▱" * (BAR_WIDTH - filled)


def count_forever_roles(guild: discord.Guild | None) -> tuple[dict[int, int], int]:
    """Anzahl Mitglieder je Forever-Rolle und Zahl der Personen insgesamt."""
    counts = {r.role_id: 0 for r in FOREVER_ROLES}
    if guild is None:
        return counts, 0
    people: set[int] = set()
    for entry in FOREVER_ROLES:
        role = guild.get_role(entry.role_id)
        if role is None:
            continue
        counts[entry.role_id] = len(role.members)
        people.update(m.id for m in role.members)
    return counts, len(people)


def faction_block(faction: str, counts: dict[int, int], emojis: dict[str, str]) -> str:
    _, title, emoji_name, fallback = next(
        f for f in _FACTION_HEADERS if f[0] == faction
    )
    lines = [f"### {emojis.get(emoji_name) or fallback} {title}"]
    for entry in roles_for_faction(faction):
        count = counts.get(entry.role_id, 0)
        done = " ✅" if count >= GOAL_TIERS[0] else ""
        lines.append(
            f"{entry.emoji} **{entry.label}** {progress_bar(count)} **{count}**{done}"
        )
    return "\n".join(lines)


def total_line(total: int) -> str:
    if total == 0:
        return "👥 Noch niemand eingetragen — sei der Erste!"
    noun = "Spieler hat" if total == 1 else "Spieler haben"
    return f"👥 **{total}** {noun} schon gewählt"


def build_forever_panel_children(
    counts: dict[int, int],
    total: int,
    emojis: dict[str, str],
    button: discord.ui.Button,
) -> list[discord.ui.Item]:
    return [
        discord.ui.TextDisplay(FOREVER_PANEL_INTRO),
        discord.ui.Separator(),
        discord.ui.TextDisplay(faction_block("horde", counts, emojis)),
        discord.ui.TextDisplay(faction_block("alliance", counts, emojis)),
        discord.ui.TextDisplay(total_line(total)),
        discord.ui.Separator(),
        discord.ui.ActionRow(button),
    ]
