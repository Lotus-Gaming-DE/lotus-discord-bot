from __future__ import annotations

import math

import discord

from .forever_roles import FOREVER_ROLES, roles_for_faction

# Eine gemeinsame Skala für alle sechs Balken, die mit der Zahl der Spieler
# mitwächst: voll ist eine Gilde bei MIN_SCALE Spielern oder bei SCALE_SHARE
# aller Interessenten — je nachdem, was größer ist. Gerundet auf SCALE_STEP,
# damit sich die Skala nicht bei jedem neuen Spieler verschiebt.
MIN_SCALE = 20
SCALE_SHARE = 0.6
SCALE_STEP = 5
BAR_WIDTH = 10
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


def bar_scale(total_people: int) -> int:
    """Spielerzahl, bei der ein Balken voll ist (für alle Gilden gleich)."""
    share = math.ceil(total_people * SCALE_SHARE / SCALE_STEP) * SCALE_STEP
    return max(MIN_SCALE, share)


def progress_bar(count: int, scale: int) -> str:
    # Aufrunden: schon die erste Person füllt einen Balkenabschnitt.
    filled = min(BAR_WIDTH, math.ceil(count * BAR_WIDTH / scale))
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


def faction_block(
    faction: str, counts: dict[int, int], emojis: dict[str, str], scale: int
) -> str:
    _, title, emoji_name, fallback = next(
        f for f in _FACTION_HEADERS if f[0] == faction
    )
    lines = [f"### {emojis.get(emoji_name) or fallback} {title}"]
    for entry in roles_for_faction(faction):
        count = counts.get(entry.role_id, 0)
        lines.append(
            f"{entry.emoji} **{entry.label}** {progress_bar(count, scale)} **{count}**"
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
    scale = bar_scale(total)
    return [
        discord.ui.TextDisplay(FOREVER_PANEL_INTRO),
        discord.ui.Separator(),
        discord.ui.TextDisplay(faction_block("horde", counts, emojis, scale)),
        discord.ui.TextDisplay(faction_block("alliance", counts, emojis, scale)),
        discord.ui.TextDisplay(total_line(total)),
        discord.ui.Separator(),
        discord.ui.ActionRow(button),
    ]
