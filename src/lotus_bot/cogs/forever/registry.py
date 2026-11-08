"""Liest die Battle.net-Verbindungen aus Lotus Link (nur lesen).

Lotus Link ist der einzige Dienst, der Blizzard zu WoW Forever abfragt. Er stellt
für diesen Bot die Ansichten ``registry_api.*`` bereit (Lotus Link, design D4
und D29). Der Bot meldet sich mit einem eigenen Login an, der nur diese
Ansichten lesen darf.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class LinkedCharacter:
    """Ein per Battle.net-Login nachgewiesener Char (der „Claim“)."""

    character_id: int
    blizzard_id: int
    discord_user_id: int
    name: str
    level: int
    guild_slug: str | None


@dataclass(frozen=True)
class GuildMember:
    """Ein Eintrag der Gildenliste. Beweist keinen Besitz."""

    guild_slug: str
    blizzard_id: int
    name: str
    level: int
    rank: int


@dataclass(frozen=True)
class RunAttendance:
    """Teilnahme an einem Run, den der Organisator als stattgefunden markiert hat."""

    run_id: int
    discord_user_id: int
    is_organizer: bool
    recorded_at: datetime


@dataclass(frozen=True)
class Snapshot:
    linked: tuple[LinkedCharacter, ...]
    members: tuple[GuildMember, ...]
    runs: tuple[RunAttendance, ...]
    # Gilden, deren Liste Lotus Link schon einmal geladen hat. Ohne Liste gibt
    # es keinen Sync-Report, sonst stünde dort jeder als „ohne Claim“.
    rosters_loaded: frozenset[str]


class Registry(Protocol):
    async def snapshot(
        self, guild_slugs: list[str], host_discord_guild_id: int
    ) -> Snapshot: ...

    async def close(self) -> None: ...


LINKED_SQL = """
SELECT c.id, c.blizzard_character_id, p.discord_user_id, c.name, c.level, g.slug
  FROM registry_api.characters c
  JOIN registry_api.players p ON p.id = c.player_id
  LEFT JOIN registry_api.guilds g ON g.id = c.guild_id
 WHERE c.region = 'eu'
"""

MEMBERS_SQL = """
SELECT g.slug, m.blizzard_character_id, m.name, m.level, m.rank
  FROM registry_api.guild_members m
  JOIN registry_api.guilds g ON g.id = m.guild_id
 WHERE g.region = 'eu' AND g.slug = ANY($1::text[])
"""

ROSTERS_SQL = """
SELECT slug FROM registry_api.guilds
 WHERE region = 'eu' AND slug = ANY($1::text[]) AND roster_synced_at IS NOT NULL
"""

RUNS_SQL = """
SELECT a.run_id, p.discord_user_id, a.is_organizer, a.recorded_at
  FROM registry_api.run_attendance a
  JOIN registry_api.players p ON p.id = a.player_id
 WHERE a.host_discord_guild_id = $1
"""


class PgRegistry:
    """Lesezugriff über asyncpg. Die Verbindung entsteht erst bei Bedarf."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self._dsn, min_size=0, max_size=2, command_timeout=30
            )
        return self._pool

    async def snapshot(
        self, guild_slugs: list[str], host_discord_guild_id: int
    ) -> Snapshot:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True, isolation="repeatable_read"):
                linked = await conn.fetch(LINKED_SQL)
                members = await conn.fetch(MEMBERS_SQL, guild_slugs)
                loaded = await conn.fetch(ROSTERS_SQL, guild_slugs)
                runs = await conn.fetch(RUNS_SQL, host_discord_guild_id)
        return Snapshot(
            linked=tuple(
                LinkedCharacter(r[0], r[1], r[2], r[3], r[4], r[5]) for r in linked
            ),
            members=tuple(GuildMember(r[0], r[1], r[2], r[3], r[4]) for r in members),
            runs=tuple(
                RunAttendance(r[0], r[1], r[2], r[3])
                for r in runs
                if r[1] is not None  # gelöschte Spieler sind anonymisiert
            ),
            rosters_loaded=frozenset(r[0] for r in loaded),
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
