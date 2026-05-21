from __future__ import annotations

import discord
from discord import app_commands

from lotus_bot.permissions import owner_only

dev_group = app_commands.Group(
    name="dev",
    description="Entwickler-Hilfsbefehle (nur Server-Owner)",
)

_SEP = "─" * 30


def _chunk(text: str, limit: int = 1900) -> list[str]:
    """Split text into chunks that fit within Discord's message limit."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split = text.rfind("\n", 0, limit)
        if split == -1:
            split = limit
        chunks.append(text[:split])
        text = text[split:].lstrip("\n")
    return chunks


@dev_group.command(name="roles", description="Alle Rollen mit IDs anzeigen")
@owner_only()
async def dev_roles(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Nur im Server verfügbar.", ephemeral=True
        )
        return

    roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)
    lines = [f"**Rollen ({len(roles)})**\n{_SEP}"]
    for role in roles:
        indicator = "🔴" if role.color.value else "⚪"
        display = role.display_icon
        icon = (
            f" {display}"
            if display is not None and not isinstance(display, discord.Asset)
            else ""
        )
        lines.append(f"{indicator} `{role.id}`  @{role.name}{icon}")

    body = "\n".join(lines)
    chunks = _chunk(body)
    await interaction.response.send_message(chunks[0], ephemeral=True)
    for chunk in chunks[1:]:
        await interaction.followup.send(chunk, ephemeral=True)


@dev_group.command(name="channels", description="Alle Channels mit IDs anzeigen")
@owner_only()
async def dev_channels(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Nur im Server verfügbar.", ephemeral=True
        )
        return

    lines = [f"**Channels ({len(guild.channels)})**\n{_SEP}"]

    # Channels ohne Kategorie zuerst
    no_cat = [
        c
        for c in guild.channels
        if c.category is None and not isinstance(c, discord.CategoryChannel)
    ]
    if no_cat:
        lines.append("📌 *(keine Kategorie)*")
        for ch in sorted(no_cat, key=lambda c: c.position):
            prefix = "🔊" if isinstance(ch, discord.VoiceChannel) else "#"
            lines.append(f"   {prefix} `{ch.id}`  {ch.name}")

    # Channels nach Kategorie gruppiert
    for cat in sorted(guild.categories, key=lambda c: c.position):
        lines.append(f"\n📁 **{cat.name}** `({cat.id})`")
        for ch in sorted(cat.channels, key=lambda c: c.position):
            prefix = "🔊" if isinstance(ch, discord.VoiceChannel) else "#"
            lines.append(f"   {prefix} `{ch.id}`  {ch.name}")

    body = "\n".join(lines)
    chunks = _chunk(body)
    await interaction.response.send_message(chunks[0], ephemeral=True)
    for chunk in chunks[1:]:
        await interaction.followup.send(chunk, ephemeral=True)


@dev_group.command(
    name="emojis", description="Alle Server-Emojis mit IDs und Syntax anzeigen"
)
@owner_only()
async def dev_emojis(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Nur im Server verfügbar.", ephemeral=True
        )
        return

    emojis = sorted(guild.emojis, key=lambda e: e.name)
    lines = [f"**Server-Emojis ({len(emojis)})**\n{_SEP}"]
    for emoji in emojis:
        prefix = "a" if emoji.animated else ""
        syntax = f"<{prefix}:{emoji.name}:{emoji.id}>"
        lines.append(f"`{emoji.name:<24}` `{emoji.id}`  `{syntax}`")

    body = "\n".join(lines)
    chunks = _chunk(body)
    await interaction.response.send_message(chunks[0], ephemeral=True)
    for chunk in chunks[1:]:
        await interaction.followup.send(chunk, ephemeral=True)
