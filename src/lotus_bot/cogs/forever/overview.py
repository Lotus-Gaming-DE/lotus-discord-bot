"""Wer ist in Lotus Link verbunden? Suche und Übersicht, ohne Discord.

Gerrit 16.11.2026: Wie im alten Black-Lotus-Panel soll man nach einem Char
suchen (wem gehört er, welche Chars hat dieser Spieler noch) oder nach einem
Discord-Nutzer (welche Chars hat er verbunden). Dazu je Gilde die Zahl der
Chars und wie viele davon verbunden sind.

Quelle ist der Snapshot, den ``ForeverCog`` alle zehn Minuten aus Lotus Link
liest. Die Gildenliste ist stündlich frisch, das Charakterprofil täglich: Wo
beide etwas sagen, gewinnt die Gildenliste.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .logic import GUILDS, GUILDS_BY_SLUG, ForeverGuild, class_name, is_main_rank
from .registry import Snapshot

# Mehr Treffer passen nicht sinnvoll in eine Antwort.
MAX_HITS = 15


@dataclass(frozen=True)
class CharInfo:
    blizzard_id: int
    name: str
    level: int
    class_key: str | None
    guild_slug: str | None
    rank: int | None
    owner: int | None

    @property
    def lotus_guild(self) -> ForeverGuild | None:
        return GUILDS_BY_SLUG.get(self.guild_slug) if self.guild_slug else None


@dataclass(frozen=True)
class GuildStats:
    guild: ForeverGuild
    chars: int
    linked: int
    players: int
    mains: int
    mains_linked: int

    @property
    def percent(self) -> int:
        return round(100 * self.linked / self.chars) if self.chars else 0


def characters(snapshot: Snapshot) -> dict[int, CharInfo]:
    """Alle bekannten Chars: Gildenlisten der Lotus-Gilden plus alle Verbindungen."""
    chars: dict[int, CharInfo] = {}
    for m in snapshot.members:
        chars[m.blizzard_id] = CharInfo(
            m.blizzard_id, m.name, m.level, m.class_key, m.guild_slug, m.rank, None
        )
    for c in snapshot.linked:
        known = chars.get(c.blizzard_id)
        if known is None:
            # Gilde laut Profil. Steht die Gildenliste schon, ist der Char dort
            # nicht (mehr) Mitglied, auch wenn das ältere Profil es noch sagt.
            slug = c.guild_slug
            if slug in snapshot.rosters_loaded:
                slug = None
            chars[c.blizzard_id] = CharInfo(
                c.blizzard_id, c.name, c.level, None, slug, None, c.discord_user_id
            )
            continue
        chars[c.blizzard_id] = CharInfo(
            known.blizzard_id,
            known.name,
            max(known.level, c.level),
            known.class_key,
            known.guild_slug,
            known.rank,
            c.discord_user_id,
        )
    return chars


def _sort_key(info: CharInfo) -> tuple:
    guild_order = {g.slug: i for i, g in enumerate(GUILDS)}
    return (
        guild_order.get(info.guild_slug or "", len(GUILDS)),
        -info.level,
        info.name.casefold(),
    )


def find_characters(
    query: str,
    snapshot: Snapshot,
    visible: Callable[[CharInfo], bool] = lambda _: True,
) -> list[CharInfo]:
    """Chars, deren Name ``query`` enthält; exakte Treffer zuerst.

    ``visible`` filtert, was der Fragende sehen darf (Lotus Link verbindet auch
    Spieler anderer Server, die gehen uns nichts an).
    """
    needle = query.strip().casefold()
    if not needle:
        return []
    hits = [
        info
        for info in characters(snapshot).values()
        if needle in info.name.casefold() and visible(info)
    ]
    hits.sort(key=lambda i: (i.name.casefold() != needle, _sort_key(i)))
    return hits[:MAX_HITS]


def characters_of(user_id: int, snapshot: Snapshot) -> list[CharInfo]:
    chars = [i for i in characters(snapshot).values() if i.owner == user_id]
    return sorted(chars, key=_sort_key)


def guild_stats(
    snapshot: Snapshot, absent: Iterable[int] = frozenset()
) -> list[GuildStats]:
    """Je Lotus-Gilde mit geladener Liste: Chars, verbunden, Spieler, Mains.

    Wer den Discord verlassen hat, zählt wie unverbunden (wie im Sync-Report).
    """
    gone = set(absent)
    owner_of = {
        c.blizzard_id: c.discord_user_id
        for c in snapshot.linked
        if c.discord_user_id not in gone
    }
    stats = []
    for guild in GUILDS:
        if guild.slug not in snapshot.rosters_loaded:
            continue
        members = [m for m in snapshot.members if m.guild_slug == guild.slug]
        owners = [owner_of.get(m.blizzard_id) for m in members]
        mains = [
            m
            for m in members
            if guild.layout is not None and is_main_rank(m.rank, guild.layout)
        ]
        stats.append(
            GuildStats(
                guild,
                chars=len(members),
                linked=sum(o is not None for o in owners),
                players=len({o for o in owners if o is not None}),
                mains=len(mains),
                mains_linked=sum(m.blizzard_id in owner_of for m in mains),
            )
        )
    return stats


# ---------------------------------------------------------------- texte


def guild_label(info: CharInfo) -> str:
    guild = info.lotus_guild
    if guild is not None:
        rank = f", {guild.rank_name(info.rank)}" if info.rank is not None else ""
        return f"{guild.icon} {guild.name}{rank}"
    if info.guild_slug:
        return info.guild_slug.replace("-", " ").title()
    return "ohne Gilde"


def char_line(info: CharInfo) -> str:
    """``**Voidok** · Level 42 Krieger · ❤️ Crimson Lotus, Member``"""
    level = f"Level {info.level}"
    if class_name(info.class_key):
        level += f" {class_name(info.class_key)}"
    return f"**{info.name}** · {level} · {guild_label(info)}"


def stats_lines(stats: list[GuildStats], *, details: bool) -> list[str]:
    """Eine Zeile je Gilde. ``details`` ergänzt Spieler und Mains (Leitungen)."""
    lines = []
    for s in stats:
        line = (
            f"{s.guild.tag}: **{s.linked}** von {s.chars} Chars verbunden "
            f"({s.percent} %)"
        )
        if details:
            line += f" · {s.players} Spieler"
            if s.mains:
                line += f" · Mains {s.mains_linked}/{s.mains}"
        lines.append(line)
    return lines


def player_text(name: str, chars: list[CharInfo]) -> str:
    if not chars:
        return f"{name} hat keinen Charakter mit Lotus Link verbunden."
    lines = [f"{name} · {len(chars)} verbunden"]
    lines += [f"• {char_line(c)}" for c in chars]
    return "\n".join(lines)


def search_text(
    query: str,
    hits: list[CharInfo],
    snapshot: Snapshot,
    name_of: Callable[[int], str],
) -> str:
    if not hits:
        return f"Kein Charakter zu **{query}** gefunden."
    if len(hits) == 1:
        hit = hits[0]
        if hit.owner is None:
            return f"{char_line(hit)}\n❌ nicht mit Lotus Link verbunden"
        return f"🔎 {char_line(hit)}\n\n" + player_text(
            name_of(hit.owner), characters_of(hit.owner, snapshot)
        )
    lines = [f"🔎 {len(hits)} Treffer zu **{query}**:"]
    for hit in hits:
        owner = name_of(hit.owner) if hit.owner is not None else "nicht verbunden"
        lines.append(f"• {char_line(hit)} → {owner}")
    if len(hits) == MAX_HITS:
        lines.append("_Es gibt mehr Treffer, genauer suchen._")
    return "\n".join(lines)
