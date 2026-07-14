import os
import sqlite3

from scripts.backup_db import backup_database


def _make_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO t (value) VALUES ('hello')")
    conn.commit()
    conn.close()


def test_backup_database_creates_a_full_copy(tmp_path):
    db_path = str(tmp_path / "source.db")
    _make_db(db_path)
    backup_dir = str(tmp_path / "backups")

    backup_path = backup_database(db_path, backup_dir=backup_dir)

    assert backup_path is not None
    assert os.path.exists(backup_path)
    conn = sqlite3.connect(backup_path)
    rows = conn.execute("SELECT value FROM t").fetchall()
    assert rows == [("hello",)]


def test_backup_database_returns_none_for_missing_db(tmp_path):
    db_path = str(tmp_path / "does_not_exist.db")

    assert backup_database(db_path, backup_dir=str(tmp_path / "backups")) is None


def test_backup_database_returns_none_for_in_memory_db(tmp_path):
    assert backup_database(":memory:", backup_dir=str(tmp_path / "backups")) is None


def test_backup_database_prunes_old_backups_beyond_keep_limit(tmp_path):
    db_path = str(tmp_path / "source.db")
    _make_db(db_path)
    backup_dir = str(tmp_path / "backups")

    paths = [backup_database(db_path, backup_dir=backup_dir, keep=3) for _ in range(5)]

    remaining = sorted(f for f in os.listdir(backup_dir) if f.endswith(".db"))
    assert len(remaining) == 3
    # The most recent backup created must survive pruning.
    assert os.path.basename(paths[-1]) in remaining
