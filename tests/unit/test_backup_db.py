import os
import shutil

import pytest

from scripts.backup_db import backup_database

pytestmark = pytest.mark.skipif(shutil.which("pg_dump") is None, reason="pg_dump not on PATH")


@pytest.mark.asyncio
async def test_backup_database_creates_a_dump_file(tmp_path, db_dsn):
    backup_dir = str(tmp_path / "backups")

    backup_path = backup_database(db_dsn, backup_dir=backup_dir)

    assert backup_path is not None
    assert os.path.exists(backup_path)
    assert os.path.getsize(backup_path) > 0


def test_backup_database_returns_none_for_bad_dsn(tmp_path):
    backup_dir = str(tmp_path / "backups")

    assert backup_database("postgresql://nobody:nowhere@localhost:1/does-not-exist", backup_dir=backup_dir) is None


@pytest.mark.asyncio
async def test_backup_database_prunes_old_backups_beyond_keep_limit(tmp_path, db_dsn):
    backup_dir = str(tmp_path / "backups")

    paths = [backup_database(db_dsn, backup_dir=backup_dir, keep=3) for _ in range(5)]

    remaining = sorted(f for f in os.listdir(backup_dir) if f.endswith(".dump"))
    assert len(remaining) == 3
    # The most recent backup created must survive pruning.
    assert os.path.basename(paths[-1]) in remaining
