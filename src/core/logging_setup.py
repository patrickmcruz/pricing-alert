"""
Centralized logging setup: color-coded console output, a plain-text file
copy, and third-party loggers quieted regardless of the app's own level.

Call configure_logging() once, near the top of an entrypoint (main.py,
scripts/run_all_scrapers.py) - not from src/core/config.py, which used to
call a bare logging.basicConfig(level=...) at import time. That silently
"won" over any later basicConfig() call without force=True (plain
basicConfig() is a no-op once handlers already exist), which is why
scripts/run_all_scrapers.py's own formatting never actually applied.
"""

import logging
import sys
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from src.core.config import settings

_DISPLAY_TZ = ZoneInfo(settings.display_timezone)

_LEVEL_COLORS = {
    logging.DEBUG: "\033[2;37m",  # dim gray
    logging.INFO: "\033[36m",  # cyan
    logging.WARNING: "\033[33m",  # yellow
    logging.ERROR: "\033[31m",  # red
    logging.CRITICAL: "\033[1;41;37m",  # bold white on red
}
_RESET = "\033[0m"

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Noisy at DEBUG regardless of this app's own log_level - aiosqlite dumps the
# full SQL text + params on every query, httpcore/hpack (the Mercado Livre
# scraper's HTTP/2 transport) dump every request/response header and raw
# HPACK frame byte-by-byte, and asyncio/apscheduler have their own internal
# chatter. None of it is useful for this app's own storytelling. httpx itself
# is left alone - its one-line-per-request "HTTP Request: GET ... 200 OK" at
# INFO is exactly the kind of clean, useful line this cleanup is for.
_THIRD_PARTY_LOGGERS = ("aiosqlite", "asyncio", "apscheduler", "httpcore", "hpack")


class SaoPauloTimeFormatter(logging.Formatter):
    """Renders %(asctime)s in settings.display_timezone (América/São Paulo by
    default, UTC-3) instead of the system/container timezone - the
    orchestrator container's system tz is UTC (same root cause as
    configure_logging's AsyncIOScheduler note), so without this every log
    line reads 3h ahead of local time."""

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=_DISPLAY_TZ)
        return dt.strftime(datefmt) if datefmt else dt.strftime("%Y-%m-%d %H:%M:%S %z")


class ColorFormatter(SaoPauloTimeFormatter):
    """Wraps the whole formatted line in an ANSI color code keyed by level.

    Always emits color codes (no isatty() gating) - the intended viewer is
    `docker logs`/a terminal, which renders ANSI fine regardless of whether
    the writing process's own stdout was a tty.
    """

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = _LEVEL_COLORS.get(record.levelno, "")
        return f"{color}{message}{_RESET}" if color else message


def configure_logging(level_name: str, log_file: str = settings.log_file_path) -> None:
    """Configures the root logger with a colored console handler and a plain
    file handler, and quiets known-noisy third-party loggers."""
    numeric_level = getattr(logging, level_name.upper(), logging.INFO)

    # Windows' default console encoding (cp1252) can't encode the ✓/⚠/○/✗
    # symbols used in the storytelling summary lines - logging then silently
    # drops those lines (swallows a UnicodeEncodeError per record) instead of
    # printing them. Linux containers are already UTF-8 and unaffected.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorFormatter(_LOG_FORMAT))

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(SaoPauloTimeFormatter(_LOG_FORMAT))

    logging.basicConfig(
        level=numeric_level,
        handlers=[console_handler, file_handler],
        force=True,
    )

    for name in _THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
