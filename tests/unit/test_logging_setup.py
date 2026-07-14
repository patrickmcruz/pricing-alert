import logging
from datetime import datetime, timezone

from src.core.logging_setup import (
    ColorFormatter,
    SaoPauloTimeFormatter,
    _RESET,
    _THIRD_PARTY_LOGGERS,
    configure_logging,
)


def test_configure_logging_silences_third_party_loggers_regardless_of_app_level():
    configure_logging("DEBUG")

    for name in _THIRD_PARTY_LOGGERS:
        assert logging.getLogger(name).level == logging.WARNING


def test_color_formatter_wraps_line_in_ansi_code_matching_level():
    formatter = ColorFormatter("%(levelname)s: %(message)s")
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname=__file__, lineno=1,
        msg="boom", args=(), exc_info=None,
    )

    formatted = formatter.format(record)

    assert formatted.startswith("\033[31m")  # red for ERROR
    assert formatted.endswith(_RESET)
    assert "ERROR: boom" in formatted


def test_color_formatter_leaves_unmapped_levels_uncolored():
    formatter = ColorFormatter("%(message)s")
    record = logging.LogRecord(
        name="test", level=25, pathname=__file__, lineno=1,
        msg="custom level", args=(), exc_info=None,
    )

    formatted = formatter.format(record)

    assert formatted == "custom level"


def test_sao_paulo_time_formatter_converts_utc_to_utc_minus_3_regardless_of_system_tz():
    # 18:00 UTC is always 15:00 in America/Sao_Paulo (Brazil has had no DST
    # since 2019) - independent of whatever tz the host/container is in,
    # which is exactly the bug this formatter fixes (container tz is UTC).
    utc_instant = datetime(2026, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
    formatter = SaoPauloTimeFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="x", args=(), exc_info=None,
    )
    record.created = utc_instant.timestamp()

    formatted_time = formatter.formatTime(record)

    assert formatted_time == "2026-01-15 15:00:00 -0300"
