"""Generate production-like CSV datasets for manual testing.

Outputs (under data/ by default):
- prod_like_10k.csv
- prod_like_100k.csv
- prod_like_1m.csv
- prod_like_10m.csv

Design goals:
- deterministic data (same content every run)
- realistic values and mixed formatting patterns
- 15 columns, including 3 date columns with different formats:
  - Order Date: %Y-%m-%d
  - Invoice Date: %d/%m/%Y
  - Posting Date Serial: EXCEL_SERIAL-compatible integer days
- streaming writes to avoid high memory usage on large files
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

HEADERS = [
    "Order ID",
    "Customer ID",
    "Order Date",
    "Invoice Date",
    "Posting Date Serial",
    "Region",
    "Country Code",
    "Currency",
    "Sales Channel",
    "Payment Method",
    "Units",
    "Gross Amount",
    "Discount Rate",
    "Priority Order",
    "Order Status",
]

MARKETS = [
    ("North America", "US", "USD", "$", ".", ","),
    ("Europe", "DE", "EUR", "€", ",", "."),
    ("Asia Pacific", "JP", "JPY", "¥", ".", ","),
    ("Europe", "GB", "GBP", "£", ".", ","),
    ("Asia Pacific", "CN", "CNY", "CN¥", ".", ","),
    ("Europe", "CH", "CHF", "CHF", ".", ","),
    ("North America", "CA", "CAD", "C$", ".", ","),
    ("Oceania", "AU", "AUD", "A$", ".", ","),
    ("Asia Pacific", "HK", "HKD", "HK$", ".", ","),
    ("Asia Pacific", "SG", "SGD", "S$", ".", ","),
    ("Europe", "SE", "SEK", "SEK", ",", "."),
    ("Europe", "NO", "NOK", "NOK", ",", "."),
    ("Oceania", "NZ", "NZD", "NZ$", ".", ","),
    ("Latin America", "MX", "MXN", "MX$", ".", ","),
    ("Asia Pacific", "IN", "INR", "₹", ".", ","),
    ("Asia Pacific", "KR", "KRW", "₩", ".", ","),
    ("Latin America", "BR", "BRL", "R$", ",", "."),
    ("Africa", "ZA", "ZAR", "ZAR", ".", ","),
    ("Middle East", "TR", "TRY", "₺", ",", "."),
    ("Middle East", "AE", "AED", "AED", ".", ","),
]
CHANNELS = ["Web", "Mobile App", "Marketplace", "Partner", "Retail POS", "Inside Sales"]
PAYMENTS = ["card", "wallet", "bank_transfer", "invoice", "cash_on_delivery"]
STATUSES = ["processing", "shipped", "completed", "on_hold", "refunded", "cancelled", "delayed"]
PRIORITY_TOKENS = ["true", "false", "yes", "no", "1", "0", "TRUE", "FALSE"]

BASE_DATE = date(2023, 1, 1)
DATE_CYCLE_DAYS = 1461  # 4 years including a leap year.
DATE_CACHE_ISO = [
    (BASE_DATE + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(DATE_CYCLE_DAYS)
]
DATE_CACHE_DMY = [
    (BASE_DATE + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(DATE_CYCLE_DAYS)
]


@dataclass(frozen=True)
class DatasetSpec:
    rows: int
    suffix: str


DATASETS = [
    DatasetSpec(rows=10_000, suffix="10k"),
    DatasetSpec(rows=100_000, suffix="100k"),
    DatasetSpec(rows=1_000_000, suffix="1m"),
    DatasetSpec(rows=10_000_000, suffix="10m"),
]


def _format_grouped(integer_part: int, thousand_sep: str) -> str:
    grouped = f"{integer_part:,}"
    if thousand_sep != ",":
        grouped = grouped.replace(",", thousand_sep)
    return grouped


def _format_local_number(cents: int, decimal_sep: str, thousand_sep: str, index: int) -> str:
    sign = ""
    if index % 137 == 0:
        sign = "-"
    elif index % 97 == 0:
        sign = "+"

    base_cents = abs(cents)
    int_part = base_cents // 100
    frac = base_cents % 100
    grouped = _format_grouped(int_part, thousand_sep)

    if index % 503 == 0:
        core = f"{grouped}{decimal_sep}"
    elif index % 389 == 0:
        core = f"{decimal_sep}{frac:02d}"
        sign = "-"
    elif index % 257 == 0:
        core = f"{decimal_sep}{frac:02d}"
    else:
        core = f"{grouped}{decimal_sep}{frac:02d}"
    return f"{sign}{core}"


def _format_gross_amount(currency_code: str, symbol: str, number_text: str, index: int) -> str:
    style_index = index % 10
    unsigned_text = number_text.lstrip("+-")
    styles = (
        f"{symbol}{number_text}",
        f"{currency_code} {number_text}",
        f"{number_text} {currency_code}",
        f"{symbol} {number_text}",
        f"({symbol}{unsigned_text})",
        f"{unsigned_text}-",
        f"{unsigned_text} CR",
        f"{unsigned_text} DR",
        unsigned_text,
        f"{currency_code} {unsigned_text}",
    )
    return styles[style_index]


def _format_discount_rate(decimal_sep: str, index: int) -> str:
    if index % 499 == 0:
        return "n/a"
    if index % 997 == 0:
        return ""
    rate = ((index * 7) % 3500) / 10_000
    text = f"{rate:.4f}"
    if decimal_sep == ",":
        return text.replace(".", ",")
    return text


def _format_units(thousand_sep: str, index: int) -> str:
    if index % 311 == 0:
        return ""
    units = ((index * 11) % 5000) + 1
    if index % 77 == 0:
        return _format_grouped(units, thousand_sep)
    return str(units)


def _date_value_from_offset(offset: int) -> date:
    return BASE_DATE + timedelta(days=offset)


def _excel_serial_from_date(day_value: date) -> int:
    excel_epoch = date(1899, 12, 30)
    return (day_value - excel_epoch).days


def _format_order_date(offset: int, index: int) -> str:
    if index % 997 == 0:
        return ""
    if index % 1543 == 0:
        return "n/a"
    return DATE_CACHE_ISO[offset]


def _format_invoice_date(offset: int, index: int) -> str:
    if index % 991 == 0:
        return ""
    if index % 1871 == 0:
        return "n/a"
    return DATE_CACHE_DMY[offset]


def _format_posting_serial(offset: int, index: int) -> str:
    if index % 983 == 0:
        return ""
    if index % 1999 == 0:
        return "n/a"
    day_value = _date_value_from_offset(offset)
    return str(_excel_serial_from_date(day_value))


def format_row(index: int) -> list[str]:
    row_number = index + 1
    offset = row_number % DATE_CYCLE_DAYS
    region, country, currency_code, symbol, decimal_sep, thousand_sep = MARKETS[
        row_number % len(MARKETS)
    ]
    cents = ((row_number * 173) % 9_500_000) + 50
    number_text = _format_local_number(cents, decimal_sep, thousand_sep, row_number)

    return [
        f"ORD-{row_number:011d}",
        str(100_000 + ((row_number * 17) % 900_000)),
        _format_order_date(offset, row_number),
        _format_invoice_date(offset, row_number),
        _format_posting_serial(offset, row_number),
        region,
        country,
        currency_code,
        CHANNELS[row_number % len(CHANNELS)],
        PAYMENTS[row_number % len(PAYMENTS)],
        _format_units(thousand_sep, row_number),
        _format_gross_amount(currency_code, symbol, number_text, row_number),
        _format_discount_rate(decimal_sep, row_number),
        PRIORITY_TOKENS[row_number % len(PRIORITY_TOKENS)],
        STATUSES[row_number % len(STATUSES)],
    ]


def write_dataset(path: Path, rows: int, *, progress_every: int) -> None:
    started = time.perf_counter()
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="", buffering=1024 * 1024) as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for i in range(rows):
            row = format_row(i)
            writer.writerow(row)
            if progress_every > 0 and (i + 1) % progress_every == 0:
                elapsed = time.perf_counter() - started
                print(f"  wrote {i + 1:,}/{rows:,} rows in {elapsed:.1f}s", flush=True)

    hasher = hashlib.sha256()
    with path.open("rb") as binary_file:
        while True:
            chunk = binary_file.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    checksum = hasher.hexdigest()
    sidecar_path = path.with_suffix(path.suffix + ".sha256")
    sidecar_path.write_text(f"{checksum}\n", encoding="utf-8")
    elapsed = time.perf_counter() - started
    size_mb = path.stat().st_size / (1024 * 1024)
    print(
        f"done: {path} rows={rows:,} size={size_mb:.1f}MB elapsed={elapsed:.1f}s "
        f"checksum_file={sidecar_path}",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate production-like Phase 1 datasets")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data"),
        help="Output directory (default: data)",
    )
    parser.add_argument(
        "--only",
        choices=["10k", "100k", "1m", "10m", "all"],
        default="all",
        help="Generate only one dataset size (default: all)",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=500_000,
        help="Progress log interval in rows (default: 500000)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    selected = DATASETS
    if args.only != "all":
        selected = [spec for spec in DATASETS if spec.suffix == args.only]

    print(f"output directory: {args.out_dir}")
    for spec in selected:
        output_file = args.out_dir / f"prod_like_{spec.suffix}.csv"
        print(f"generating: {output_file} ({spec.rows:,} rows)")
        write_dataset(output_file, spec.rows, progress_every=args.progress_every)


if __name__ == "__main__":
    main()
