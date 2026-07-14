"""Canonical temporal parsing SQL — the single source of truth for date/datetime/time.

Values parse against fixed format chains; ``day_first`` declares whether a
numeric day/month pair reads day-first (01/02/2023 is 1 February) or
month-first (January 2), and only one order is ever in a column's chain.
Excel serials are accepted within a plausibility window so a bare year can
never be read as a serial; two-digit years never parse. Both profiling and
conversion build their temporal SQL here.
"""

from __future__ import annotations

from shared.constants import EXCEL_SERIAL_DATE_EPOCH_SQL
from shared.db.sql import quote_string

# Excel serial plausibility window: 20000 = 1954-10-03, 59999 = 2064-04-07
# (days since the 1899-12-30 epoch). Four-digit years (1000-9999) all fall
# outside it, so year-looking integers are never read as serials.
EXCEL_SERIAL_MIN_SERIAL = 20000
EXCEL_SERIAL_MAX_SERIAL = 59999

# Year-first formats are order-free: a leading 4-digit year forces y-m-d.
_YEAR_FIRST_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d")

_DAY_FIRST_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y")
_MONTH_FIRST_DATE_FORMATS = ("%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y", "%b %d, %Y", "%b %d %Y")

# Datetime-shaped values appearing in a date column truncate to their date.
_DATETIME_IN_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
)

_YEAR_FIRST_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
)

_DAY_FIRST_DATETIME_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
)
_MONTH_FIRST_DATETIME_FORMATS = (
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m-%d-%Y %H:%M:%S",
    "%m-%d-%Y %H:%M",
)

# Date-only values appearing in a datetime column read as midnight.
_DATE_IN_DATETIME_FORMATS = ("%Y-%m-%d", "%Y/%m/%d")

TIME_STRPTIME_FORMATS = ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p")


def date_strptime_formats(day_first: bool) -> tuple[str, ...]:
    """Return the ordered strptime chain for a date column."""
    ordered = _DAY_FIRST_DATE_FORMATS if day_first else _MONTH_FIRST_DATE_FORMATS
    return _YEAR_FIRST_DATE_FORMATS + ordered + _DATETIME_IN_DATE_FORMATS


def datetime_strptime_formats(day_first: bool) -> tuple[str, ...]:
    """Return the ordered strptime chain of time-bearing datetime formats.

    Date-only fallbacks are appended only inside ``datetime_parse_expr``: a
    value without a time component is not evidence that a column is a datetime,
    but in a declared datetime column it reads as midnight.
    """
    ordered = _DAY_FIRST_DATETIME_FORMATS if day_first else _MONTH_FIRST_DATETIME_FORMATS
    return _YEAR_FIRST_DATETIME_FORMATS + ordered


def _format_list_sql(formats: tuple[str, ...]) -> str:
    return "[" + ", ".join(quote_string(fmt) for fmt in formats) + "]"


def _serial_double(value_expr: str) -> str:
    return f"TRY_CAST({value_expr} AS DOUBLE)"


def _serial_window_predicate(value_expr: str) -> str:
    serial = _serial_double(value_expr)
    return f"{serial} >= {EXCEL_SERIAL_MIN_SERIAL} AND {serial} <= {EXCEL_SERIAL_MAX_SERIAL}"


def _require_four_digit_year(parsed_expr: str) -> str:
    """Null out parses below year 1000.

    DuckDB's ``%Y`` accepts 1-3 digit years, so ``01/02/98`` would otherwise
    parse to year 0098.
    """
    return f"CASE WHEN EXTRACT(year FROM {parsed_expr}) >= 1000 THEN {parsed_expr} END"


def date_parse_expr(value_expr: str, day_first: bool) -> str:
    """Return a SQL expression parsing ``value_expr`` to DATE, or NULL."""
    chain = _require_four_digit_year(
        f"TRY_CAST(TRY_STRPTIME({value_expr}, "
        f"{_format_list_sql(date_strptime_formats(day_first))}) AS DATE)"
    )
    serial = (
        f"CASE WHEN {_serial_window_predicate(value_expr)} "
        f"THEN {EXCEL_SERIAL_DATE_EPOCH_SQL} "
        f"+ CAST(FLOOR({_serial_double(value_expr)}) AS INTEGER) END"
    )
    return f"COALESCE({chain}, {serial})"


def datetime_parse_expr(value_expr: str, day_first: bool) -> str:
    """Return a SQL expression parsing ``value_expr`` to TIMESTAMP, or NULL."""
    formats = datetime_strptime_formats(day_first) + _DATE_IN_DATETIME_FORMATS
    chain = _require_four_digit_year(
        f"TRY_CAST(TRY_STRPTIME({value_expr}, {_format_list_sql(formats)}) AS TIMESTAMP)"
    )
    serial = (
        f"CASE WHEN {_serial_window_predicate(value_expr)} "
        f"THEN {EXCEL_SERIAL_DATE_EPOCH_SQL} "
        f"+ ({_serial_double(value_expr)} * INTERVAL 1 DAY) END"
    )
    return f"COALESCE({chain}, {serial})"


def time_parse_expr(value_expr: str) -> str:
    """Return a SQL expression parsing ``value_expr`` to TIME, or NULL."""
    return (
        f"TRY_CAST(TRY_STRPTIME({value_expr}, {_format_list_sql(TIME_STRPTIME_FORMATS)}) AS TIME)"
    )
