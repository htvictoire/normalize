# Gap Analysis: Implementation Guide v2 vs Current Implementation

## Reading Basis

Every line of `data/implementation_guide_v2.md` was read (3,347 lines). Every Python source file
in `src/` was read (131 files across 29 directories). This report reflects both in full.

---

## Part 1: What the Original Plan Designed vs What Was Actually Built

### Pipeline Structure

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Stages | 16 named stages (Ingestion → Manifest Finalization) | 3 phases: suggest → profile → convert |
| Stage gating | Explicit PROFILE vs APPLY mode; stages 15-16 skipped in PROFILE | No mode flag; full execution always runs |
| Entry point | `NormalizationEngine.run()` dispatching 16 stage objects | `MainOrchestrator` with three service classes |
| Async execution | Dramatiq workers + RabbitMQ + priority queues | Synchronous only; no task queue |
| State machine | PENDING → RUNNING → READY/BLOCKED/FAILED | PENDING → AWAITING_CONFIRMATION → CONFIRMED → PROFILING → PROFILED → NORMALIZING → READY |
| Inline path | Small datasets (< 10K rows) processed synchronously in API request | All API calls are synchronous inline already |

The current architecture collapsed the original 16 stages into three domain services. The
suggest/profile/convert split maps roughly to stages 1-7, 8-10, and 11-16 respectively, but the
explicit stage boundaries, contracts, and gating were discarded. The current design is simpler and
works well for a single-user CLI/API scenario. The original plan's staged approach was oriented
toward a multi-tenant platform with SLAs, retries, and scheduling.

### Data Contract Design

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Central config object | `NormalizationConfig` (locale, template, rules version, reference_date, workbook strategy) | `InstanceConfig` (source_format, column_config, operation_config) — no locale, template, or rules version concept |
| Type system | Arrow types (`pa.DataType`) assigned per column with semantic metadata in Arrow field metadata | Python discriminated union of `ColumnConfig` subtypes; no Arrow types until Parquet export |
| Determinism contract | SHA256 fingerprint of data + config + rules version + locale + DuckDB version | `source_checksum` field stored per instance; no composite fingerprint |
| Quality score formula | Five weighted components: parse_success (0.25) + pattern_consistency (0.25) + anomaly_ratio (0.20) + schema_stability (0.15) + completeness (0.15) | Two components: parse_success (0.50) + completeness (0.50); no anomaly, schema stability, or pattern consistency |
| Decision thresholds | READY ≥ 95, READY_WITH_WARNINGS ≥ 85, BLOCKED < 85 | `DecisionThresholds(ready, warning)` configured on `OperationConfig`; current code always sets status to `READY` regardless of score |

### Excel Ingestion Path

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Library | `python-calamine` (Rust-based, GIL-releasing, direct Arrow output) | `openpyxl` (pure Python, streaming `read_only=True`, row-by-row `executemany`) |
| Multi-workbook | `ThreadPoolExecutor` parallel reads + temp Parquet + `read_parquet` batch DuckDB registration | Single-file only; no multi-workbook support |
| Arrow integration | Calamine → Arrow table → DuckDB zero-copy `duckdb.register()` | openpyxl rows → Python list → DuckDB `executemany(INSERT ...)` |
| ODS/XLSB support | Yes (Calamine supports all four: XLSX, XLS, ODS, XLSB) | No (openpyxl supports XLSX only; XLS reads silently wrong) |
| Sheet visibility | `CalamineWorkbook.sheet_visibility` filters hidden/very_hidden sheets | `worksheet.sheet_state == "visible"` check via openpyxl (only in suggestion phase, not in ingestion) |

### Artifact Export

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Standard tier export | `fetch_arrow_table()` (zero-copy, dataset fits in memory) | `COPY (...) TO file.parquet (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)` — DuckDB native COPY |
| Large tier export | `COPY TO` to bypass Arrow intermediary | Not applicable (no tier concept) |
| Trace export (large tier) | `arrow(chunk_size=500000)` chunked streaming for bounded memory | `COPY (...) TO trace.parquet` — same COPY strategy as main artifact |
| PyArrow role | Explicit: CSV→Arrow, JSON→Arrow, parallel workbook writes to temp Parquet | Only at import time: `pyarrow` is a declared dependency but `write_normalized_parquet` and `write_trace_parquet` both use DuckDB `COPY TO`, not PyArrow directly |
| Compression | ZSTD level 9 + dictionary encoding for low-cardinality columns | ZSTD (no level specified, ROW_GROUP_SIZE 100000) — in `PARQUET_COPY_OPTIONS` constant |

The current implementation actually made a better call on Parquet export: it uses DuckDB's native
`COPY TO` for both the normalized Parquet and the trace Parquet. This is exactly what the original
plan prescribed for Large/Massive tier export — bypassing Arrow to avoid memory doubling. The
current implementation applies this optimization universally, not just for large datasets. The
original plan would have introduced an unnecessary `fetch_arrow_table()` step for Standard tier
datasets that the current code correctly avoids.

### Scheduled Maintenance Tasks

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Stuck job sweeper | APScheduler `BackgroundScheduler` + `CronTrigger`, every 5 minutes, transitions RUNNING→FAILED after threshold | **Absent** |
| Orphaned artifact sweeper | APScheduler, every 1 hour, removes R2 artifacts not referenced by any completed run | **Absent** |
| Stuck partition sweeper | APScheduler, every 10 minutes, fails parent run for stuck partition workers | Not applicable (no partitioning) |
| Scheduled via | APScheduler `CronTrigger` initialized on worker startup | Nothing |
| Self-healing | Yes — RUNNING jobs that exceed their tier's expected duration are automatically recovered | No — NORMALIZING status stays permanent on crash |

The current codebase has no APScheduler dependency and no maintenance tasks. A crashed normalize
call leaves the instance permanently in `NORMALIZING` status with no recovery path.

### Async, Queue, Backpressure

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Task queue | Dramatiq + RabbitMQ, priority queues, per-actor concurrency limits, `time_limit` | None |
| Idempotency | Two-phase atomic claim (`UPDATE ... WHERE status='PENDING' RETURNING id`) + stuck-job sweeper for crash recovery | No idempotency; repeated calls create new instances |
| Backpressure | FastAPI dependency checking RabbitMQ queue depth (cached 5s TTL), returns HTTP 429 + Retry-After | None |
| Worker concurrency | `max_concurrent = floor(container_memory / per_task_memory)` enforced by Dramatiq actor options | No concurrency limit |
| Webhook dispatch | Dramatiq actor with HMAC-SHA256 signed payloads, exponential backoff retries | None |
| Circuit breakers | pybreaker on R2 (threshold=5, timeout=30s) and PostgreSQL writes (threshold=3, timeout=15s) | None |
| Progress tracking | `progress_pct` updated to PostgreSQL via atomic `completed_partitions / total_partitions` | No progress tracking |

### Quality Scoring and Decision Evaluation

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Components | 5: parse_success (0.25), pattern_consistency (0.25), anomaly_ratio (0.20), schema_stability (0.15), completeness (0.15) | 2: parse_success (0.50), completeness (0.50) |
| Anomaly detection | IQR outliers, z-score, chronological gaps, exact duplicates, fuzzy duplicates via DuckDB `editdist3`/`jaccard`, cross-column constraints | **Absent** |
| Schema drift detection | Baseline stored in PostgreSQL; structural drift (add/remove/rename/type change) + quality drift (null ratio, parse error spike, pattern consistency drop, anomaly ratio spike); drift policy (strict/additive_only/permissive) | **Absent** |
| Decision logic | READY ≥ 95, READY_WITH_WARNINGS 85–95, BLOCKED < 85 or any ERROR issue | `set_normalization_output` always sets `InstanceStatus.READY` regardless of quality score |
| Decimal arithmetic | `decimal.Decimal` for all threshold comparisons to avoid IEEE 754 drift | `decimal.Decimal` used correctly in `quality_metrics.py` ✓ |
| Pattern consistency in score | Yes — `AVG(dominant_pattern_frequency)` across profiled columns | Not present in quality score; `pattern_consistency_ratio` is computed in `ProfilingOutput` but not used in the conversion quality formula |

The current implementation computes `pattern_consistency_ratio` during profiling (stored in
`ProfilingOutput.pattern_consistency_ratio`) but then ignores it entirely during the conversion
quality score. This is a direct gap from the original plan.

### Pattern Discovery and Type Inference

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Pattern matching engine | DuckDB SQL with `REGEXP_MATCHES` + `COUNT FILTER` aggregations, patterns tested in specificity order | Column-type config is confirmed by the user before profiling; profiling validates parse rates per type, not discovers patterns |
| Stratified sampling | DuckDB `NTILE(10)` with explicit `ORDER BY _global_row_index` for determinism | Suggestion phase uses first N inference rows (not stratified); no NTILE |
| Relative date handling | `RELATIVE_DATE_REQUIRES_REFERENCE` blocker when relative dates detected without `reference_date` config | No relative date detection |
| Scientific notation | Dedicated pattern rule in `rules/patterns/numeric.py` | No scientific notation type or detection |
| Unit suffixes | Dedicated pattern rule in `rules/patterns/units.py` (e.g., "100 kg", "25°C") | Not supported |
| PII suppression | Template flags columns as PII; sample values suppressed in pattern profile and trace artifacts | No PII concept |
| Mixed-type detection | Explicit stage (9) categorizing harmless/ambiguous/incompatible mixing with policy-driven resolution | Not present as a stage; separator mismatch and mixed currency are detected in profiling as issues |

### Multi-Workbook Support

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Workbook manifest | Per-workbook metadata (filename, sheet names, row count, schema fingerprint, checksum) | Not implemented |
| Cross-workbook schema alignment | Column union/intersection/rename detection via Jaccard, provenance columns `_source_workbook` | Not implemented |
| Concatenation strategies | strict, union, intersection, sequential | Not implemented |
| Archive support | ZIP and TAR extraction with path traversal prevention | Not implemented |

### Scalability Architecture

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Tiers | Standard (<1M), Large (1M-10M), Massive (>10M) with partition-merge for Large/Massive | None — single-path pipeline regardless of dataset size |
| Partition-merge | Partition workers execute stages 11-12 on row-range Parquet slices; global statistics precomputed; merge worker runs stages 13-16 | Not implemented |
| Incremental normalization | Append-only fast path: delta extraction, stages 11-12 on delta only, merge with previous artifacts | Not implemented |
| Memory enforcement | Container cgroup validation at startup; 4GB DuckDB limit enforced; `tier_selector.py` validates 6GB minimum container memory | 4GB default memory limit in `DuckDBManager`; no cgroup validation |
| COPY TO for partitions | DuckDB `COPY TO ... WHERE _global_row_index BETWEEN ...` for partition export | Not applicable |

### Observability

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Structured logging | structlog with JSON formatter, context propagation (request_id, tenant_id, job_id) | Standard Python logging or print statements (no structlog) |
| Prometheus metrics | 20+ defined counters/histograms/gauges with codified alert rules | None |
| Distributed tracing | Trace span decorators on stage boundaries, trace ID propagation | None |
| Loki integration | JSON logs shipped to Loki | None |

### Schema Migration

| Dimension | Original Plan | Current Implementation |
|---|---|---|
| Migration tool | Alembic with 6 versioned migrations | None — `_ensure_schema()` in `PostgresRunRepository` runs `CREATE TABLE IF NOT EXISTS` directly |
| Schema baseline table | `schema_baselines` with optimistic locking (version column) | Not present |
| Partition runs table | `partition_runs` for partition lifecycle tracking | Not present |
| Incremental tracking columns | `is_incremental`, `incremental_base_fingerprint`, `delta_row_count`, `previous_row_count` | Not present |
| Row-level security | PostgreSQL RLS policies for multi-tenant isolation | Not present; `tenant_id` column exists but no RLS |

---

## Part 2: Salvageable Ideas — Verdict and Integration Path

### 1. python-calamine for Excel Ingestion

**Verdict: Adopt. Clear, unambiguous improvement.**

The current `DirectExcelIngestor` reads Excel via openpyxl into Python lists, then inserts rows via
`executemany`. This is Python-loop ingestion. For a 500K-row Excel file this can take 30-60 seconds.
Calamine reads via Rust, releases the GIL, and outputs an Arrow table directly — DuckDB can then
register it via `duckdb.register()` with zero-copy.

**Measurable benefit**: Excel ingestion 5-10× faster. Zero Python-to-DuckDB copy overhead. GIL
released during file parsing enables true parallel ingestion if multi-workbook support is added.

**Integration**: Replace `DirectExcelIngestor.run()` in
`src/shared/ingestion/excel/loader.py`. Add `python-calamine` to `pyproject.toml`. PyArrow is
already a declared dependency so `pa.Table` is available.

```python
from python_calamine import CalamineWorkbook
import pyarrow as pa

def run(self, conn, source_url, sheet_name, header_mode, header_row_index) -> list[str]:
    wb = CalamineWorkbook.from_path(source_url)
    sheet = wb.get_sheet_by_name(sheet_name) if sheet_name else wb.get_sheet_by_index(0)
    data = sheet.to_python(skip_empty_area=False)
    # extract headers, convert to Arrow, register with DuckDB
    table = pa.table({col: ... for col in columns})
    conn.register(RAW_INPUT_TABLE_NAME, table)
    return columns
```

The suggestion phase in `suggestion/source/excel.py` also uses openpyxl for the same reason and
should be updated at the same time, since it currently reads the full workbook into memory to detect
headers.

### 2. Stuck-Job Sweeper (APScheduler)

**Verdict: Adopt. Addresses a real production gap with low implementation cost.**

The current codebase has a permanent failure mode: if the normalize call crashes between setting
`status = NORMALIZING` and calling `set_normalization_output`, the instance is stuck in
`NORMALIZING` forever. There is no recovery path. Any subsequent call returns
`"instance must be PROFILED before normalize"` because the status is wrong.

**Measurable benefit**: Self-healing. NORMALIZING timeouts are detected and reset to FAILED within
configurable interval. The DuckDB cache file can be cleaned up. The user gets a clear error rather
than a silent stuck state.

**Integration**: Add `APScheduler` to `pyproject.toml`. Add a `maintenance.py` module in
`src/app/` with a `BackgroundScheduler` that runs on API or worker startup. The sweeper query is
trivial:

```python
UPDATE normalization_runs
SET status = 'FAILED', updated_at = NOW()
WHERE status = 'NORMALIZING'
  AND updated_at < NOW() - INTERVAL '30 minutes'
```

The sweeper should also delete the orphaned DuckDB cache file at `settings.duckdb_cache_dir /
{instance_id}.duckdb` for recovered instances, since the profiling DB stays on disk when the
normalize step fails. Start interval at 5 minutes.

### 3. DuckDB COPY TO for Parquet — Already Correct

**Verdict: No action needed. The current implementation already beat the plan here.**

The original plan prescribed `fetch_arrow_table()` for Standard tier and `COPY TO` only for
Large/Massive tier. The current implementation uses `COPY TO` everywhere (both
`write_normalized_parquet` and `write_trace_parquet` in `conversion/artifacts/`). This eliminates
the Arrow intermediary memory doubling that the plan only applied to large datasets. The current
code is more memory-efficient than the plan.

The one improvement worth making: add `COMPRESSION_LEVEL 9` to `PARQUET_COPY_OPTIONS` in
`conversion/constants.py`. Currently the constant is
`(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)` with no level specified; DuckDB
defaults to level 3 for ZSTD. Level 9 reduces artifact size by 15-25% at a CPU cost that is
typically acceptable for normalization workloads.

### 4. Pattern Consistency in Quality Score

**Verdict: Adopt. The data is already computed; it just isn't used.**

`ProfilingOutput.pattern_consistency_ratio` is computed during profiling (it's the mean dominant
symbol ratio across currency/accounting columns). The conversion quality score ignores it, using
only `parse_success_ratio * 0.50 + completeness_ratio * 0.50`. The original plan weighted pattern
consistency at 0.25 in the five-component formula.

The current formula is reasonable for a two-phase system where profiling gates conversion. But
`pattern_consistency_ratio` is free data that already exists — not using it means the quality score
misses a signal. A high parse_success_ratio with low pattern_consistency means some columns contain
mixed formats that happened to parse, but shouldn't be trusted.

**Integration**: Thread `profiling_issues` and `profiling_output` through to `ConversionService`.
The `profiling_output.pattern_consistency_ratio` is already stored on `InstanceModel`. Incorporate
it into `_compute_quality_score` in `conversion/quality_metrics.py` with a weight like
`0.30 * parse_success + 0.30 * completeness + 0.40 * pattern_consistency`.

### 5. Decision Evaluation — BLOCKED Status Is Not Implemented

**Verdict: Adopt immediately. The current code never blocks on low quality scores.**

`InstanceModel.set_normalization_output` always sets `status = InstanceStatus.READY` regardless of
the quality score. The `OperationConfig` carries `DecisionThresholds(ready, warning)` but these
are never evaluated — nothing in the current code reads these thresholds. This means a dataset with
5% parse success rate produces a `READY` status. The original plan had three decision states with
clear thresholds.

**Integration**: In `MainOrchestrator.normalize()`, after calling
`self._conversion_service.convert()`, evaluate `result.quality_output.quality_score` against
`confirmed.operation_config.decision_thresholds`:

```python
score = Decimal(result.quality_output.quality_score)
thresholds = confirmed.operation_config.decision_thresholds
if score < Decimal(str(thresholds.warning)):
    instance.status = InstanceStatus.BLOCKED
elif score < Decimal(str(thresholds.ready)):
    instance.status = InstanceStatus.READY_WITH_WARNINGS
else:
    instance.status = InstanceStatus.READY
```

Also check `profiling_output.issues` for `IssueSeverity.ERROR` to set `BLOCKED` independent of
score (this check exists for profiling already at line 100 of `orchestrator.py` but the equivalent
post-conversion check is missing).

### 6. Scientific Notation Support

**Verdict: Adopt. Common in exported financial data; currently silently wrong.**

The original plan had a dedicated `rules/patterns/numeric.py` for scientific notation (`1.5E+10`,
`-2.3E-4`, `1E3`). The current implementation has no `ScientificColumnConfig` type. A value like
`1.23E+06` in a numeric column will be treated as a string parse error because no column type maps
to it. Financial exports (Bloomberg, Reuters) regularly produce this format.

**Integration**: Add `ScientificColumnConfig` to `shared/models/column/configs.py` with a
`decimal_separator` field. Add detection in `suggestion/column_config/numeric/` (regex match on
`[+-]?\d+\.?\d*[Ee][+-]?\d+`). Add a profiling stat and conversion expression
(`CAST(REGEXP_REPLACE(val, 'E', 'e', 'g') AS DOUBLE)::DECIMAL`). This is a self-contained
addition that doesn't break any existing type.

### 7. Alembic Migrations

**Verdict: Adopt for production readiness. Not urgent for development.**

The current `_ensure_schema()` in `PostgresRunRepository` uses `CREATE TABLE IF NOT EXISTS`.
This is adequate for development but creates a permanent gap for schema evolution: there is no
way to add columns, change constraints, or roll back schema changes safely in production. The
original plan had 6 Alembic migrations with explicit rollback DDL.

**Integration**: Add `alembic` to `pyproject.toml`. Run `alembic init alembic`. Create
`001_initial.py` from the current `CREATE TABLE` DDL in `_ensure_schema()`. This is a one-time
migration that doesn't change runtime behavior but enables safe future schema changes. The
`_ensure_schema()` call can be replaced by a startup migration check.

### 8. PyArrow for CSV/JSON Ingestion (Staged Parallel Ingestion)

**Verdict: Low priority for single-file use; high value if multi-workbook is added.**

The original plan used PyArrow's CSV reader for CSV ingestion (with charset-normalizer for encoding
detection) and PyArrow's JSON reader for JSON ingestion — both producing Arrow tables for zero-copy
DuckDB registration. The current implementation uses DuckDB's `read_csv` directly for CSV (fast
and correct) and DuckDB's `read_json_auto` for JSON. Both are good choices.

The place where PyArrow ingestion becomes valuable is the parallel multi-workbook path: each
Calamine worker writes to a temp Parquet via `pyarrow.parquet.write_table()`, then DuckDB reads
all at once via `read_parquet(glob)`. This is the ThreadPoolExecutor pattern in Section 5.5 of the
guide. PyArrow is already a declared dependency; this use case activates it meaningfully.

For single-file ingestion today, the current DuckDB-direct approach is preferable — simpler and
already fast. No change needed until multi-workbook is implemented.

### 9. Composite Fingerprint for Idempotency

**Verdict: Adopt if the API is called by external systems. Skip for CLI-only use.**

The original plan computed a SHA256 fingerprint from: raw data checksum + effective config +
rules version + locale + DuckDB version + optional reference_date + workbook strategy. This
fingerprint served as the idempotency key: identical inputs always return the same result without
re-running the pipeline.

The current implementation stores `source_checksum` per instance but has no composite fingerprint.
Two calls with identical inputs but different `operation_config` flags produce separate instances
that run the full pipeline twice.

**Integration**: Add a `fingerprint` column to `normalization_runs` (migration). Compute it in
`MainOrchestrator.suggest()` from `source_checksum + canonical_json(confirmed_config)` (SHA256).
In `normalize()`, check for an existing `READY` run with the same fingerprint before executing.
This is a 30-line addition with meaningful cost savings for repeated normalizations.

---

## Part 3: What the New Architecture Got Right (Don't Revert)

### The four-phase CLI lifecycle is better than 16 stages

The original plan's 16 stages are appropriate for a fully automated, headless pipeline. The current
suggest → confirm → profile → convert lifecycle correctly inserts a human confirmation step between
inference and execution. For a tool where users review and adjust column types, this is strictly
better. The 16-stage design would have automated through that confirmation, losing the primary
correction interface.

### DuckDB COPY TO everywhere is better than the plan's tiered export

The plan prescribed `fetch_arrow_table()` for Standard tier (< 1M rows) and `COPY TO` only for
Large/Massive tier. The current code uses `COPY TO` universally. This is the right call: `COPY TO`
eliminates the Arrow intermediary for all sizes, not just large ones. There is no downside for
small datasets and it eliminates an entire code path.

### The parse CTE optimization in `transform.py` is not in the plan

`compose_transform_sql` emits a `parsed` CTE that materializes `CAST(col AS VARCHAR)`,
`LOWER(TRIM(...))`, and the nullish boolean once per row before the base CTE applies them. This
is not mentioned in the implementation guide at all — it was invented during implementation. It
prevents DuckDB from recomputing `LOWER(TRIM(...))` multiple times per row (once for the nullish
check, once for the normalized value, once for the issue expression). On 10M-row datasets this
saves several seconds. Keep it.

### The conditional JSON optimization is not in the plan

`compose_transform_sql` computes `__error_cnt` as a lateral alias in the base CTE, then uses it
to conditionally serialize `TO_JSON(STRUCT_PACK(...))` only for error rows when `full_raw_row=False`.
The plan describes the conditional raw row feature (`full_raw_row` flag) but not this specific
optimization. The implementation guide comment says "saves ~10s on 10M rows when most rows have
no parse errors." This is correct and not in the plan — keep it.

### Psycopg3 (not SQLAlchemy) is the right choice at this scale

The original plan specified SQLAlchemy 2.0 + Alembic. The current implementation uses psycopg3
directly. For a single-table repository with five operations, SQLAlchemy adds 200+ KB of ORM
machinery for no benefit. The raw psycopg3 approach is correct at this scale. The only missing
piece is Alembic, which can be used standalone without the ORM.

### The PROFILE mode / APPLY mode distinction exists implicitly

The original plan made PROFILE vs APPLY a first-class request parameter, skipping stages 15-16 in
PROFILE mode. The current implementation achieves the same thing through the suggest → profile
lifecycle: `profile` runs the full dataset analysis without producing Parquet artifacts. Running
`profile` without subsequently running `convert` is identical to PROFILE mode. The naming and
user model differ but the behavior is equivalent.

---

## Part 4: What the Original Plan Got Right That Was Discarded

### Anomaly detection is a genuine gap

DuckDB has `editdist3` (Levenshtein distance), `jaccard`, `PERCENTILE_CONT`, and window functions
for z-score. The original plan's anomaly detection stage was entirely SQL-based — no Python loops,
no NumPy. The current implementation has no equivalent. A 1M-row financial dataset with duplicate
transactions or outlier amounts produces no warnings.

This is the highest-value missing feature. It can be added as a post-conversion SQL pass before
quality scoring without touching any existing code.

### Schema drift detection would enable safe re-normalization

The `schema_baselines` table + drift detection stage would have detected when a re-submitted file
has different column types than the previous run. Currently, if a monthly file arrives with a new
column or a renamed column, the user must discover this manually. The original plan emitted
`SCHEMA_DRIFT_DETECTED` warnings automatically. This is particularly valuable for recurring
normalization workflows.

### `python-dateutil` scoping was well-designed

The plan pinned `python-dateutil==2.8.2`, restricted imports to one file (`pattern_discovery.py`),
enforced this via CI linter, and used it only for format disambiguation on ≤200 sampled rows. The
rationale — determinism of bulk parsing delegated to DuckDB, dateutil only for inference — is
correct. The current `suggestion/column_config/date.py` uses `dateutil` for date format inference.
The risk is that an accidental `dateutil` import in a bulk path would silently break determinism.
The CI import linter boundary the plan described would prevent this.

### Locale system prevents ambiguous separator interpretation

The original plan required an explicit locale (en_US, de_DE, etc.) or blocker error; no implicit
`en_US` fallback. The current implementation has no locale concept — decimal and thousand separators
are inferred column-by-column during suggestion. For a German file where `1.234,56` is a decimal,
the inference must see enough samples to distinguish `,` as decimal separator. An explicit locale
config would make this unambiguous and user-auditable.

---

## Summary: Prioritized Action List

| Priority | Action | Effort | Impact |
|---|---|---|---|
| **1** | Decision evaluation: use `DecisionThresholds`, set BLOCKED/READY_WITH_WARNINGS | 1 hour | Correctness — currently always returns READY |
| **2** | python-calamine for Excel ingestion | 2 hours | 5-10× faster Excel; supports XLS/ODS/XLSB |
| **3** | Stuck-job sweeper (APScheduler, 5-min interval) | 3 hours | Recovery from crashes; permanent-NORMALIZING fix |
| **4** | Pattern consistency in quality score | 1 hour | Better signal from already-computed data |
| **5** | ZSTD compression level 9 in `PARQUET_COPY_OPTIONS` | 15 min | 15-25% smaller artifacts |
| **6** | Scientific notation column type | 4 hours | Handles financial export format |
| **7** | Alembic migrations | 4 hours | Safe schema evolution in production |
| **8** | Anomaly detection (IQR outliers + exact duplicates) | 8 hours | New quality signal via DuckDB SQL |
| **9** | Composite fingerprint for idempotency | 3 hours | Skip repeat work; cacheable results |
| **10** | Schema drift detection | 16 hours | Recurring workflow safety net |
