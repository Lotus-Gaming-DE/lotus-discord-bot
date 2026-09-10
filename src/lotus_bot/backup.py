"""Sicherung aller persistenten Bot-Daten (``data/pers``).

Alles, was der Bot dauerhaft speichert — Claims, Champion-Punkte, Duo-Teams,
Marktplatz, Quiz-Stand — liegt auf dem Railway-Volume unter ``data/pers``.
Ein Deploy löscht davon nichts, aber ohne Sicherung wären ein versehentlich
gelöschtes Volume oder eine kaputte Migration nicht rückgängig zu machen.

SQLite-Dateien werden über die Backup-API von SQLite kopiert, nicht per
Dateikopie: Die Datenbanken laufen im WAL-Modus, und eine rohe Kopie der
``.db``-Datei verpasst Änderungen, die noch nur im WAL stehen.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tarfile
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PERSISTENT_DIR = Path("data/pers")
BACKUP_DIR = PERSISTENT_DIR / "backups"
KEEP_BACKUPS = 7
ARCHIVE_PREFIX = "lotus-backup-"
ARCHIVE_SUFFIX = ".tar.gz"

# Nicht mitsichern: die Sicherungen selbst und reine Caches, die der Bot
# jederzeit neu aus externen Quellen aufbaut.
EXCLUDED_DIRS = frozenset({"backups", "wow_import_cache"})
EXCLUDED_FILES = frozenset({"wcr_cache.json"})
# SQLite-Nebendateien — ihr Inhalt steckt bereits in der Backup-Kopie der .db.
SQLITE_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")
SQLITE_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3"})


class InsufficientSpaceError(RuntimeError):
    """Auf dem Volume ist nicht genug Platz für eine weitere Sicherung."""


@dataclass
class BackupArchive:
    path: Path
    files: list[str]
    warnings: list[str] = field(default_factory=list)


def backup_sources(source: Path) -> list[Path]:
    """Alle Dateien unter ``source``, die in eine Sicherung gehören."""
    files = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        if rel.parts[0] in EXCLUDED_DIRS or path.name in EXCLUDED_FILES:
            continue
        if path.name.endswith(SQLITE_SIDECAR_SUFFIXES):
            continue
        files.append(path)
    return files


def _copy_sqlite(src: Path, dst: Path) -> None:
    source = sqlite3.connect(src)
    try:
        target = sqlite3.connect(dst)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def create_backup(source: Path, dest_dir: Path, now: datetime) -> BackupArchive:
    """Schreibt eine ``.tar.gz``-Sicherung von ``source`` nach ``dest_dir``.

    Das Archiv entsteht erst unter einem ``.part``-Namen und wird zum Schluss
    umbenannt, damit ein abgebrochener Lauf nie wie eine fertige Sicherung
    aussieht.
    """
    files = backup_sources(source)
    dest_dir.mkdir(parents=True, exist_ok=True)
    needed = sum(path.stat().st_size for path in files)
    free = shutil.disk_usage(dest_dir).free
    if free < needed:
        raise InsufficientSpaceError(
            f"Nur {free // 1024 // 1024} MB frei, die Sicherung braucht bis zu "
            f"{needed // 1024 // 1024} MB."
        )

    archive = dest_dir / f"{ARCHIVE_PREFIX}{now:%Y-%m-%d_%H%M%S}{ARCHIVE_SUFFIX}"
    partial = archive.with_name(archive.name + ".part")
    included: list[str] = []
    warnings: list[str] = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            for path in files:
                rel = path.relative_to(source)
                target = staging / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if path.suffix in SQLITE_SUFFIXES:
                    try:
                        _copy_sqlite(path, target)
                    except sqlite3.Error as exc:
                        # Lieber die rohen Bytes sichern als gar nichts.
                        target.unlink(missing_ok=True)
                        shutil.copy2(path, target)
                        warnings.append(
                            f"{rel.as_posix()}: SQLite-Kopie fehlgeschlagen ({exc}), "
                            "Datei roh gesichert."
                        )
                else:
                    shutil.copy2(path, target)
                included.append(rel.as_posix())
            with tarfile.open(partial, "w:gz") as tar:
                for name in included:
                    tar.add(staging / name, arcname=name)
        os.replace(partial, archive)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return BackupArchive(path=archive, files=included, warnings=warnings)


def list_backups(dest_dir: Path) -> list[Path]:
    """Fertige Sicherungen in ``dest_dir``, älteste zuerst."""
    if not dest_dir.exists():
        return []
    return sorted(
        path
        for path in dest_dir.iterdir()
        if path.is_file()
        and path.name.startswith(ARCHIVE_PREFIX)
        and path.name.endswith(ARCHIVE_SUFFIX)
    )


def rotate_backups(dest_dir: Path, keep: int = KEEP_BACKUPS) -> list[Path]:
    """Löscht alles über die ``keep`` neuesten Sicherungen hinaus.

    Räumt auch ``.part``-Reste abgebrochener Läufe weg. Gibt die gelöschten
    Pfade zurück.
    """
    backups = list_backups(dest_dir)
    stale = backups[:-keep] if keep > 0 else backups
    if dest_dir.exists():
        stale += sorted(dest_dir.glob(f"{ARCHIVE_PREFIX}*{ARCHIVE_SUFFIX}.part"))
    for path in stale:
        path.unlink(missing_ok=True)
    return stale
