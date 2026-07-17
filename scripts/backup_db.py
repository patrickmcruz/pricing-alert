"""Safe, timestamped snapshots of the PostgreSQL database.

Shells out to `pg_dump -Fc` (custom format), which produces a consistent
snapshot even while another process is actively writing - pg_dump runs
inside its own transaction with a REPEATABLE READ-equivalent snapshot.
Requires the `pg_dump` client binary (postgresql-client package) to be
present on PATH.

Run manually (`python scripts/backup_db.py`) to snapshot whatever `settings.db_dsn`
resolves to, or import `backup_database()` to call it from code. main.py calls
it once at every orchestrator boot (before any writes) and again on a daily
schedule, so a mistake in a migration/manual script is never more than a day
old and one boot-time snapshot away from a restore point. Restore with:
`pg_restore -d <dsn> --clean --if-exists <backup_path>`.
"""
import os
import shutil
import subprocess
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


def backup_database(dsn: str, backup_dir: str = BACKUP_DIR, keep: int = DEFAULT_KEEP) -> Optional[str]:
    """
    Snapshots the database `dsn` points at into backup_dir with a timestamped
    filename, then prunes old backups beyond `keep`. Returns the backup path,
    or None if pg_dump isn't available (logs a warning instead of failing the
    caller - a missing backup shouldn't block orchestrator boot).
    """
    if shutil.which("pg_dump") is None:
        print("pg_dump not found on PATH - skipping backup.", file=sys.stderr)
        return None

    os.makedirs(backup_dir, exist_ok=True)
    # Microsecond precision avoids filename collisions between backups taken
    # in quick succession (e.g. a boot-time backup followed by a migration
    # script's pre-run backup within the same second).
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = os.path.join(backup_dir, f"pricing_{timestamp}.dump")

    result = subprocess.run(
        ["pg_dump", "-Fc", "-f", backup_path, dsn],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"pg_dump failed: {result.stderr}", file=sys.stderr)
        if os.path.exists(backup_path):
            os.remove(backup_path)
        return None

    _prune_old_backups(backup_dir, keep)
    return backup_path


def _prune_old_backups(backup_dir: str, keep: int) -> None:
    existing = sorted(
        f for f in os.listdir(backup_dir) if f.startswith("pricing_") and f.endswith(".dump")
    )
    for stale in existing[:-keep] if len(existing) > keep else []:
        os.remove(os.path.join(backup_dir, stale))


if __name__ == "__main__":
    from src.core.config import settings

    result = backup_database(settings.db_dsn, keep=settings.backup_retention_count)
    if result:
        print(f"Backup created: {result}")
    else:
        print("Backup skipped or failed - see warnings above.")
