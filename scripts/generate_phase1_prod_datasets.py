"""Generate production-like CSV datasets for Phase 1 manual testing.

Outputs (under data/ by default):
- prod_like_10k.csv
- prod_like_100k.csv
- prod_like_1m.csv
- prod_like_10m.csv

Design goals:
- deterministic data (same content every run)
- production-like business fields (clean, valid values)
- 15 columns to exercise steps 1-6 with realistic typed data
- streaming writes to avoid high memory usage on large files
"""

from __future__ import annotations

import argparse
import hashlib
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

HEADERS = [
    "Order ID",
    "Customer ID",
    "Order Date",
    "Region",
    "Country Code",
    "Currency",
    "Sales Channel",
    "Account Tier",
    "Payment Method",
    "Units",
    "Gross Amount",
    "Discount Rate",
    "Priority Order",
    "Fulfillment Days",
    "Order Status",
]

REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America", "Middle East"]
COUNTRIES_BY_REGION = {
    "North America": ["US", "CA", "MX"],
    "Europe": ["DE", "FR", "GB", "IT", "ES"],
    "Asia Pacific": ["JP", "SG", "AU", "IN"],
    "Latin America": ["BR", "CL", "CO"],
    "Middle East": ["AE", "SA", "QA"],
}
CURRENCY_BY_COUNTRY = {
    "US": "USD",
    "CA": "CAD",
    "MX": "MXN",
    "DE": "EUR",
    "FR": "EUR",
    "GB": "GBP",
    "IT": "EUR",
    "ES": "EUR",
    "JP": "JPY",
    "SG": "SGD",
    "AU": "AUD",
    "IN": "INR",
    "BR": "BRL",
    "CL": "CLP",
    "CO": "COP",
    "AE": "AED",
    "SA": "SAR",
    "QA": "QAR",
}
CHANNELS = ["Web", "Mobile App", "Marketplace", "Partner"]
TIERS = ["basic", "silver", "gold", "enterprise"]
PAYMENTS = ["card", "bank_transfer", "wallet", "invoice"]
STATUSES = ["processing", "shipped", "delivered", "completed"]

# Precompute a realistic two-year date cycle to avoid per-row datetime overhead.
DATE_CYCLE = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(730)]


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


def format_row(i: int) -> str:
    region = REGIONS[i % len(REGIONS)]
    countries = COUNTRIES_BY_REGION[region]
    country = countries[(i // len(REGIONS)) % len(countries)]
    currency = CURRENCY_BY_COUNTRY[country]

    order_id = f"ORD-{i + 1:011d}"
    customer_id = str(100_000 + ((i * 17) % 900_000))
    order_date = DATE_CYCLE[i % len(DATE_CYCLE)]
    sales_channel = CHANNELS[(i * 3 + 1) % len(CHANNELS)]
    account_tier = TIERS[(i * 5 + 2) % len(TIERS)]
    payment_method = PAYMENTS[(i * 7 + 3) % len(PAYMENTS)]

    units = 1 + (i % 12)
    gross_cents = 2_500 + ((i * 37) % 250_000)  # 25.00 .. 2525.00
    discount_bps = (i * 13) % 2_000  # 0.00% .. 19.99%
    gross_amount = gross_cents / 100.0
    discount_rate = discount_bps / 10_000.0

    priority_order = "true" if (i % 5 == 0) else "false"
    fulfillment_days = 1 + ((i * 11) % 10)
    order_status = STATUSES[(i * 2 + 1) % len(STATUSES)]

    values = [
        order_id,
        customer_id,
        order_date,
        region,
        country,
        currency,
        sales_channel,
        account_tier,
        payment_method,
        str(units),
        f"{gross_amount:.2f}",
        f"{discount_rate:.4f}",
        priority_order,
        str(fulfillment_days),
        order_status,
    ]
    return ",".join(values)


def write_dataset(path: Path, rows: int, *, progress_every: int) -> None:
    started = time.perf_counter()
    path.parent.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()

    with path.open("w", encoding="utf-8", newline="", buffering=1024 * 1024) as f:
        header_line = ",".join(HEADERS) + "\n"
        f.write(header_line)
        hasher.update(header_line.encode("utf-8"))
        for i in range(rows):
            line = format_row(i) + "\n"
            f.write(line)
            hasher.update(line.encode("utf-8"))
            if progress_every > 0 and (i + 1) % progress_every == 0:
                elapsed = time.perf_counter() - started
                print(f"  wrote {i + 1:,}/{rows:,} rows in {elapsed:.1f}s", flush=True)

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
