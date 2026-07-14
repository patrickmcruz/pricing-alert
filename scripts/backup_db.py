"""Safe, timestamped snapshots of the SQLite database.

Uses SQLite's native online backup API (sqlite3.Connection.backup), which is
safe to run even while another process is actively writing to the database -
unlike a plain file copy, which can capture a half-written page mid-transaction.

Run manually (`python scripts/backup_db.py`) to snapshot whatever `settings.db_path`
resolves to, or import `backup_database()` to call it from code. main.py calls
it once at every orchestrator boot (before any writes) and again on a daily
schedule, so a mistake in a migration/manual script is never more than a day
old and one boot-time snapshot away from a restore point.
"""
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BACKUP_DIR = os.path.join(PROJECT_ROOT, "data", "backups")
# ~1/day retention is the intent; boot-time backups mean busy days accumulate
# a few extra, which is fine - this just bounds unbounded growth.
DEFAULT_KEEP = 30


def backup_database(db_path: str, backup_dir: str = BACKUP_DIR, keep: int = DEFAULT_KEEP) -> Optional[str]:
    """
    Snapshots db_path into backup_dir with a timestamped filename, then prunes
    old backups beyond `keep`. Returns the backup path, or None if there's
    nothing to back up (db_path doesn't exist yet, or is the in-memory test DB).
    """
    if db_path == ":memory:" or not os.path.exists(db_path):
        return None

    os.makedirs(backup_dir, exist_ok=True)
    db_name = os.path.splitext(os.path.basename(db_path))[0]
    # Microsecond precision avoids filename collisions between backups taken
    # in quick succession (e.g. a boot-time backup followed by a migration
    # script's pre-run backup within the same second).
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = os.path.join(backup_dir, f"{db_name}_{timestamp}.db")

    source = sqlite3.connect(db_path)
    try:
        dest = sqlite3.connect(backup_path)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()

    _prune_old_backups(backup_dir, db_name, keep)
    return backup_path


def _prune_old_backups(backup_dir: str, db_name: str, keep: int) -> None:
    prefix = f"{db_name}_"
    existing = sorted(
        f for f in os.listdir(backup_dir) if f.startswith(prefix) and f.endswith(".db")
    )
    for stale in existing[:-keep] if len(existing) > keep else []:
        os.remove(os.path.join(backup_dir, stale))


if __name__ == "__main__":
    from src.core.config import settings

    result = backup_database(settings.db_path, keep=settings.backup_retention_count)
    if result:
        print(f"Backup created: {result}")
    else:
        print(f"Nothing to back up ({settings.db_path!r} doesn't exist yet).")
