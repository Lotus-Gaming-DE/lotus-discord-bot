import sqlite3
import tarfile
from collections import namedtuple
from datetime import datetime, timezone

import pytest

import lotus_bot.cogs.backup.cog as backup_cog_mod
import lotus_bot.log_setup as log_setup
from lotus_bot import backup
from lotus_bot.cogs.backup.cog import BackupCog


def _wal_db(path, values):
    """A WAL-mode DB whose rows are still only in the -wal file (conn open)."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.executemany("INSERT INTO t VALUES (?)", [(v,) for v in values])
    conn.commit()
    return conn


def _persistent_dir(tmp_path):
    source = tmp_path / "pers"
    (source / "wow").mkdir(parents=True)
    (source / "quiz").mkdir()
    (source / "quiz" / "stats.json").write_text('{"x": 1}', encoding="utf-8")
    (source / "wcr_cache.json").write_text("{}", encoding="utf-8")
    (source / "wow_import_cache").mkdir()
    (source / "wow_import_cache" / "a.json").write_text("{}", encoding="utf-8")
    (source / "backups").mkdir()
    return source


def test_create_backup_copies_data_and_skips_caches(tmp_path):
    source = _persistent_dir(tmp_path)
    conn = _wal_db(source / "wow" / "wow.db", ["a", "b"])
    try:
        result = backup.create_backup(
            source, source / "backups", datetime(2026, 9, 11, 4, 0)
        )
    finally:
        conn.close()

    assert result.path.name == "lotus-backup-2026-09-11_040000.tar.gz"
    with tarfile.open(result.path) as tar:
        assert sorted(tar.getnames()) == ["quiz/stats.json", "wow/wow.db"]
        tar.extractall(tmp_path / "restore", filter="data")

    restored = sqlite3.connect(tmp_path / "restore" / "wow" / "wow.db")
    try:
        rows = [r[0] for r in restored.execute("SELECT v FROM t ORDER BY v")]
    finally:
        restored.close()
    # The rows only lived in the WAL — a raw file copy would have lost them.
    assert rows == ["a", "b"]
    assert not list((source / "backups").glob("*.part"))


def test_create_backup_refuses_when_volume_is_full(tmp_path, monkeypatch):
    source = _persistent_dir(tmp_path)
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(backup.shutil, "disk_usage", lambda p: usage(1, 1, 0))

    with pytest.raises(backup.InsufficientSpaceError):
        backup.create_backup(source, source / "backups", datetime(2026, 9, 11))

    assert backup.list_backups(source / "backups") == []


def test_rotate_keeps_newest_and_removes_leftovers(tmp_path):
    dest = tmp_path / "backups"
    dest.mkdir()
    names = [f"lotus-backup-2026-09-{day:02d}_040000.tar.gz" for day in range(1, 10)]
    for name in names:
        (dest / name).write_bytes(b"x")
    (dest / "lotus-backup-2026-09-10_040000.tar.gz.part").write_bytes(b"x")
    (dest / "notes.txt").write_text("keep me", encoding="utf-8")

    removed = backup.rotate_backups(dest, keep=7)

    assert [p.name for p in backup.list_backups(dest)] == names[2:]
    assert len(removed) == 3  # two old archives + the .part leftover
    assert (dest / "notes.txt").exists()


def test_next_run_is_four_am_berlin():
    # 01:00 UTC = 03:00 Berlin (CEST) → one hour until 04:00.
    assert BackupCog.seconds_until_next_run(
        datetime(2026, 9, 11, 1, 0, tzinfo=timezone.utc)
    ) == pytest.approx(3600)
    # 03:00 UTC = 05:00 Berlin → tomorrow 04:00, 23 hours later.
    assert BackupCog.seconds_until_next_run(
        datetime(2026, 9, 11, 3, 0, tzinfo=timezone.utc)
    ) == pytest.approx(23 * 3600)


class FakeChannel:
    def __init__(self, filesize_limit=10 * 1024 * 1024):
        self.guild = type("Guild", (), {"filesize_limit": filesize_limit})()
        self.sent = []

    async def send(self, content=None, file=None):
        self.sent.append((content, file.filename if file else None))
        if file is not None:
            file.close()  # release the handle so Windows can clean up tmp_path


class FakeBot:
    def __init__(self, channel):
        self.channel = channel

    def get_cog(self, name):
        return None

    def get_channel(self, channel_id):
        return self.channel


def _cog(tmp_path, patch_logged_task, channel):
    patch_logged_task(backup_cog_mod, log_setup)
    source = _persistent_dir(tmp_path)
    _wal_db(source / "wow" / "wow.db", ["a"]).close()
    return BackupCog(FakeBot(channel), source=source, dest_dir=source / "backups")


@pytest.mark.asyncio
async def test_run_backup_uploads_to_officer_channel(tmp_path, patch_logged_task):
    channel = FakeChannel()
    cog = _cog(tmp_path, patch_logged_task, channel)

    result = await cog.run_backup(upload=True)

    assert result.error is None
    assert result.uploaded
    assert channel.sent[0][1] == result.archive.name


@pytest.mark.asyncio
async def test_run_backup_skips_upload_when_file_too_large(tmp_path, patch_logged_task):
    channel = FakeChannel(filesize_limit=1)
    cog = _cog(tmp_path, patch_logged_task, channel)

    result = await cog.run_backup(upload=True)

    assert not result.uploaded
    assert "zu groß" in result.note
    assert channel.sent == [
        (f"💾 Backup `{result.archive.name}` erstellt. {result.note}", None)
    ]


@pytest.mark.asyncio
async def test_run_backup_reports_failure_in_officer_channel(
    tmp_path, patch_logged_task, monkeypatch
):
    channel = FakeChannel()
    cog = _cog(tmp_path, patch_logged_task, channel)

    def broken(*args):
        raise backup.InsufficientSpaceError("Volume voll")

    monkeypatch.setattr(backup_cog_mod, "create_backup", broken)

    result = await cog.run_backup(upload=True)

    assert result.error == "Volume voll"
    assert channel.sent == [("❌ **Backup fehlgeschlagen:** Volume voll", None)]
