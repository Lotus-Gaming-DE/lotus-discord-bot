"""/forever: Wer ist in Lotus Link verbunden?

* ``/forever uebersicht``: je Gilde Chars gesamt und verbunden, für alle.
* ``/forever charakter``: Char → Discord-Nutzer und dessen weitere Chars.
* ``/forever spieler``: Discord-Nutzer → seine verbundenen Chars.

Wer zu wem gehört, sehen nur die Leitungen (wer #wow-logs sieht, oder Admins),
so sagt es die Datenschutzerklärung von Lotus Link. Antworten sind nur für
den Fragenden sichtbar.
"""

from __future__ import annotations

import discord
from discord import app_commands

from lotus_bot.log_setup import get_logger

from .overview import (
    CharInfo,
    characters_of,
    find_characters,
    guild_stats,
    player_text,
    search_text,
    stats_lines,
)

logger = get_logger(__name__)

forever_group = app_commands.Group(
    name="forever", description="WoW Forever: Wer ist mit Lotus Link verbunden?"
)


async def is_leader(interaction: discord.Interaction, cog) -> bool:
    user = interaction.user
    permissions = getattr(user, "guild_permissions", None)
    if permissions is not None and permissions.manage_guild:
        return True
    channel = await cog._channel()
    if channel is None or not hasattr(channel, "permissions_for"):
        return False
    try:
        return channel.permissions_for(user).view_channel
    except (AttributeError, TypeError):
        return False


async def _snapshot(cog):
    snapshot = cog._last_snapshot
    if snapshot is None:
        snapshot = await cog.sync()
    return snapshot


def _visible(cog):
    """Chars der Lotus-Gilden und Chars von Leuten auf diesem Server."""

    def check(info: CharInfo) -> bool:
        if info.lotus_guild is not None:
            return True
        return info.owner is not None and cog._member(info.owner) is not None

    return check


async def _prepare(interaction: discord.Interaction, *, leaders_only: bool):
    """Gibt (cog, snapshot) zurück oder antwortet selbst und gibt None."""
    cog = interaction.client.get_cog("ForeverCog")
    if cog is None:
        await interaction.response.send_message(
            "Lotus Link ist gerade nicht angebunden.", ephemeral=True
        )
        return None
    if leaders_only and not await is_leader(interaction, cog):
        await interaction.response.send_message(
            "🚫 Das können nur die Gildenleitungen nachschlagen.", ephemeral=True
        )
        return None
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        snapshot = await _snapshot(cog)
    except Exception as exc:  # Lotus Link nicht erreichbar
        logger.warning("[ForeverCog] Snapshot für /forever fehlgeschlagen: %s", exc)
        snapshot = None
    if snapshot is None:
        await interaction.followup.send(
            "Lotus Link antwortet gerade nicht, bitte gleich nochmal.", ephemeral=True
        )
        return None
    return cog, snapshot


async def _send(interaction: discord.Interaction, text: str) -> None:
    for chunk in _chunks(text):
        await interaction.followup.send(
            chunk, ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )


def _chunks(text: str, limit: int = 1900) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        if current and len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


@forever_group.command(
    name="uebersicht", description="Wie viele Chars je Gilde sind verbunden?"
)
async def uebersicht(interaction: discord.Interaction) -> None:
    prepared = await _prepare(interaction, leaders_only=False)
    if prepared is None:
        return
    cog, snapshot = prepared
    stats = guild_stats(snapshot, await cog.store.departed())
    if not stats:
        await _send(interaction, "Noch keine Gildenliste aus Lotus Link geladen.")
        return
    details = await is_leader(interaction, cog)
    lines = ["🔗 **Mit Lotus Link verbunden**"] + stats_lines(stats, details=details)
    await _send(interaction, "\n".join(lines))


@forever_group.command(
    name="charakter", description="Wem gehört ein Char? (nur Gildenleitungen)"
)
@app_commands.describe(name="Name oder Teil des Namens")
async def charakter(interaction: discord.Interaction, name: str) -> None:
    prepared = await _prepare(interaction, leaders_only=True)
    if prepared is None:
        return
    cog, snapshot = prepared
    hits = find_characters(name, snapshot, _visible(cog))
    await _send(interaction, search_text(name, hits, snapshot, cog.who))


@charakter.autocomplete("name")
async def charakter_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    cog = interaction.client.get_cog("ForeverCog")
    if cog is None or cog._last_snapshot is None or len(current.strip()) < 2:
        return []
    if not await is_leader(interaction, cog):
        return []
    hits = find_characters(current, cog._last_snapshot, _visible(cog))
    names = dict.fromkeys(h.name for h in hits)
    return [app_commands.Choice(name=n, value=n) for n in list(names)[:25]]


@forever_group.command(
    name="spieler", description="Welche Chars hat jemand verbunden? (nur Leitungen)"
)
@app_commands.describe(nutzer="Discord-Nutzer")
async def spieler(interaction: discord.Interaction, nutzer: discord.User) -> None:
    prepared = await _prepare(interaction, leaders_only=True)
    if prepared is None:
        return
    cog, snapshot = prepared
    chars = characters_of(nutzer.id, snapshot)
    await _send(interaction, player_text(cog.who(nutzer.id), chars))


__all__ = ["forever_group", "is_leader"]
