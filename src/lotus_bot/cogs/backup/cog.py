"""Tägliche Sicherung der Bot-Daten, einmal pro Woche auch nach Discord."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from discord.ext import commands

from lotus_bot.backup import (
    BACKUP_DIR,
    KEEP_BACKUPS,
    PERSISTENT_DIR,
    create_backup,
    rotate_backups,
)
from lotus_bot.cogs.wow.cog import DEFAULT_CLAIM_REVIEW_CHANNEL_ID
from lotus_bot.log_setup import get_logger
from lotus_bot.utils.managed_cog import ManagedTaskCog

logger = get_logger(__name__)

# 04:00 Berlin: nachts, weit weg vom 09:00-Digest und vom Spielbetrieb.
BACKUP_HOUR = 4
# Montags geht zusätzlich eine Kopie in den Offi-Channel — die einzige Kopie,
# die ein gelöschtes oder kaputtes Railway-Volume überlebt.
UPLOAD_WEEKDAY = 0
DEFAULT_UPLOAD_LIMIT = 10 * 1024 * 1024

try:
    BACKUP_TIMEZONE = ZoneInfo("Europe/Berlin")
except ZoneInfoNotFoundError:  # pragma: no cover - tzdata is a dependency
    BACKUP_TIMEZONE = timezone.utc


def _mb(size: int) -> str:
    return f"{size / (1024 * 1024):.1f} MB"


@dataclass
class BackupResult:
    archive: Path | None = None
    size: int = 0
    rotated: int = 0
    uploaded: bool = False
    note: str | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


class BackupCog(ManagedTaskCog):
    def __init__(
        self,
        bot: commands.Bot,
        source: Path = PERSISTENT_DIR,
        dest_dir: Path = BACKUP_DIR,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.source = source
        self.dest_dir = dest_dir
        self._lock = asyncio.Lock()
        self.create_task(self._backup_loop())

    @staticmethod
    def seconds_until_next_run(now: datetime) -> float:
        local = now.astimezone(BACKUP_TIMEZONE)
        target = local.replace(hour=BACKUP_HOUR, minute=0, second=0, microsecond=0)
        if target <= local:
            target += timedelta(days=1)
        return (target - local).total_seconds()

    async def _backup_loop(self) -> None:
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(self.seconds_until_next_run(datetime.now(timezone.utc)))
            try:
                today = datetime.now(BACKUP_TIMEZONE)
                await self.run_backup(upload=today.weekday() == UPLOAD_WEEKDAY)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error(
                    "[BackupCog] Backup-Lauf fehlgeschlagen: %s", exc, exc_info=True
                )

    async def run_backup(self, *, upload: bool) -> BackupResult:
        """Legt eine Sicherung an, räumt alte weg und lädt sie optional hoch.

        Fehler landen nicht nur im Log, sondern auch im Offi-Channel — eine
        still gescheiterte Sicherung merkt man sonst erst, wenn man sie braucht.
        """
        async with self._lock:
            try:
                archive = await asyncio.to_thread(
                    create_backup,
                    self.source,
                    self.dest_dir,
                    datetime.now(BACKUP_TIMEZONE),
                )
            except Exception as exc:
                logger.error(
                    "[BackupCog] Sicherung fehlgeschlagen: %s", exc, exc_info=True
                )
                await self._post(f"❌ **Backup fehlgeschlagen:** {exc}")
                return BackupResult(error=str(exc))

            rotated = await asyncio.to_thread(
                rotate_backups, self.dest_dir, KEEP_BACKUPS
            )
            result = BackupResult(
                archive=archive.path,
                size=archive.path.stat().st_size,
                rotated=len(rotated),
                warnings=list(archive.warnings),
            )
            logger.info(
                "[BackupCog] Backup %s erstellt (%s, %d Dateien, %d alte entfernt).",
                archive.path.name,
                _mb(result.size),
                len(archive.files),
                result.rotated,
            )
            if result.warnings:
                await self._post(
                    "⚠️ **Backup mit Warnungen:**\n"
                    + "\n".join(f"- {warning}" for warning in result.warnings)
                )
            if upload:
                await self._upload(result)
            return result

    async def _officer_channel(self):
        wow = self.bot.get_cog("WoWCog")
        channel_id = (
            await wow.get_claim_review_channel_id()
            if wow is not None
            else DEFAULT_CLAIM_REVIEW_CHANNEL_ID
        )
        return self.bot.get_channel(channel_id)

    async def _post(self, content: str) -> None:
        channel = await self._officer_channel()
        if channel is None:
            logger.warning(
                "[BackupCog] Offi-Channel nicht gefunden — nur im Log: %s", content
            )
            return
        try:
            await channel.send(content)
        except discord.HTTPException as exc:
            logger.warning("[BackupCog] Meldung nicht gepostet: %s", exc)

    async def _upload(self, result: BackupResult) -> None:
        channel = await self._officer_channel()
        if channel is None:
            result.note = (
                "Offi-Channel nicht gefunden — Backup liegt nur auf dem Volume."
            )
            logger.warning("[BackupCog] %s", result.note)
            return
        limit = (
            getattr(getattr(channel, "guild", None), "filesize_limit", None)
            or DEFAULT_UPLOAD_LIMIT
        )
        if result.size > limit:
            result.note = (
                f"Datei zu groß für Discord ({_mb(result.size)}, Limit {_mb(limit)}) "
                "— liegt nur auf dem Volume."
            )
            await self._post(
                f"💾 Backup `{result.archive.name}` erstellt. {result.note}"
            )
            return
        try:
            await channel.send(
                content=(
                    f"💾 **Wöchentliches Backup** — `{result.archive.name}` "
                    f"({_mb(result.size)})\n"
                    "Enthält Claims, Champion-Punkte, Duo-Teams, Marktplatz und "
                    "Quiz-Stand. Bitte nicht löschen — das ist die Kopie, die auch "
                    "einen Totalausfall des Servers übersteht."
                ),
                file=discord.File(result.archive),
            )
            result.uploaded = True
        except discord.HTTPException as exc:
            result.note = f"Upload fehlgeschlagen: {exc}"
            logger.warning("[BackupCog] %s", result.note)
