# Architecture Audit: `implementation_guide_v2.md` vs Current Codebase

Audit basis:
- This report is based on a full read of `data/implementation_guide_v2.md` and a full read of the current repository contents that define runtime behavior: root config/docs, `src/app`, `src/shared`, `src/suggestion`, `src/profiling`, `src/conversion`, `scripts`, and runtime-adjacent data scripts. Absence claims mean no corresponding component exists anywhere in the current tree as read on 2026-04-07.
- The central finding is simple: this repository does not implement the service described in the guide. It implements a smaller, synchronous, four-phase normalization workflow with a thin API wrapped around it. The architecture change is not incremental drift. It is a product-level fork. (Guide: `data/implementation_guide_v2.md:1125-1151`, `data/implementation_guide_v2.md:1186-1219`, `data/implementation_guide_v2.md:3018-3063`; Actual: `CLAUDE.md:43-60`, `src/app/bootstrap/orchestrator.py:1-126`)

## §1 — What Was Actually Built

### 1.1 System shape

The current system is a four-step lifecycle: `suggest -> confirm -> profile -> normalize`. `MainOrchestrator` is the single control plane for both the HTTP API and the CLI. It constructs one `PostgresRunRepository`, one `SuggestionService`, one `ProfilingService`, and one `ConversionService`, and then executes a fixed sequence of method calls against an `InstanceModel`. There is no generic stage runner, no worker handoff, no queue, no idempotency claim step, and no async orchestration layer. (Actual: `src/app/bootstrap/orchestrator.py:29-126`)

The package structure is deliberate and documented in-repo: `app/` owns entrypoints and orchestration, `suggestion/` owns config inference, `profiling/` owns full-dataset analysis, `conversion/` owns transformation and artifact writing, and `shared/` owns models and utilities. There is no `src/normalize/` package, no `engine.py`, no `tasks/`, no `observability/`, no `rules/`, no `templates/`, and no `locales/` implementation. (Actual: `CLAUDE.md:45-60`, `FILE_PHILOSOPHY.md:9-31`, `FILE_PHILOSOPHY.md:35-52`)

### 1.2 Entry points

The HTTP surface is synchronous and instance-oriented. It exposes:
- `GET /health`
- `POST /normalize/suggest`
- `GET /normalize/instances/{id}`
- `PUT /normalize/instances/{id}/confirm`
- `POST /normalize/instances/{id}/profile`
- `POST /normalize/instances/{id}/normalize`

Every route returns or mutates the same `InstanceModel`. There is no job submission endpoint, no progress endpoint, no artifact retrieval endpoint, no webhook management endpoint, no baseline endpoint, no auth dependency, no rate limiting dependency, and no backpressure dependency. (Actual: `src/app/api/router.py:21-51`, `src/app/api/server.py:21-29`, `src/app/api/models.py:11-20`)

The CLI is not a thin operator shell over the planned service. It is a first-class execution path that directly calls the same orchestrator from `main.py` and the `app/cli/*` commands. The repo-local command documentation in `CLAUDE.md` also treats this lifecycle as primary. (Actual: `main.py:1-40`, `src/app/cli/suggest.py:36-62`, `src/app/cli/confirm.py:23-43`, `src/app/cli/profile.py:19-36`, `src/app/cli/convert.py:17-33`, `CLAUDE.md:30-47`)

### 1.3 Persistence and state model

Persistence is a single PostgreSQL table, `normalization_runs`, created lazily at runtime by repository code. The table stores one row per instance and persists lifecycle snapshots as JSONB blobs: `suggested_config`, `suggestion_display`, `confirmed_config`, `profiling_output`, and `normalization_output`. There are no separate tables for issues, baselines, templates, locales, webhooks, partitions, orphaned artifacts, or rate limits. There is no migration framework. There is no optimistic locking. There is no fingerprint column. There is no `artifacts_complete` gate. (Actual: `src/app/infra/postgres/repository.py:28-137`, `src/app/persistence/serialization.py:15-90`)

`InstanceModel` carries a broader status enum than the code actually uses: `PENDING`, `AWAITING_CONFIRMATION`, `CONFIRMED`, `PROFILING`, `PROFILED`, `NORMALIZING`, `READY`, `READY_WITH_WARNINGS`, `BLOCKED`, `FAILED`. In practice, the orchestrator only drives the path to `READY`. There is no code that sets `READY_WITH_WARNINGS`, `BLOCKED`, or `FAILED`. (Actual: `src/shared/models/instance.py:16-28`, `src/shared/models/instance.py:71-92`, `src/app/bootstrap/orchestrator.py:44-126`)

Multi-tenancy is nominal only. `tenant_id` exists on the model and table, but `InstanceModel.create()` defaults it to `"default"`, there is no authenticated tenant context, and no row-level security or tenant-scoped query logic exists. (Actual: `src/shared/models/instance.py:48-69`, `src/app/infra/postgres/repository.py:41-61`, `src/app/api/router.py:26-51`)

### 1.4 Configuration and dependencies

The runtime settings surface is small: DuckDB memory/thread/cache settings, PostgreSQL DSN, S3 endpoint/credentials/bucket, and a conversion output directory. There is no RabbitMQ config, no API key salt, no backpressure thresholds, no rate limits, no feature flags, no tier thresholds, no circuit breaker settings, no sweeper intervals, and no incremental settings. (Actual: `src/shared/settings.py:10-33`, `.env.example:1-10`)

The actual dependency stack is also small: `duckdb`, `fastapi`, `openpyxl`, `pyarrow`, `psycopg[binary]`, `pydantic`, `pydantic-settings`, `requests`, `uvicorn`, and `boto3`. The runtime does not include `python-calamine`, `dramatiq`, `sqlalchemy`, `alembic`, `structlog`, `python-dateutil`, `pybreaker`, or `apscheduler`. `docker-compose.yml` provisions only PostgreSQL. (Actual: `pyproject.toml:10-31`, `docker-compose.yml:1-20`)

### 1.5 Suggestion phase

Suggestion is a heuristic config-inference pass, not Stage 8-10 of the guide’s pipeline. It:
- probes the source
- infers format settings
- derives null tokens
- builds a spreadsheet-style position map (`A`, `B`, ...)
- computes exact counts in one track
- infers `ColumnConfig` objects in another track
- returns `SuggestionOutput = suggested_config + display`

This is done in `suggestion/pipeline.py` with a `ThreadPoolExecutor`, not via a stage engine. (Actual: `src/suggestion/pipeline.py:1-122`, `src/shared/models/suggestion.py:10-30`, `src/shared/db/column_index.py:33-44`)

CSV and JSON suggestion operate from the first 4 MiB probe, not the full dataset. Excel suggestion uses `openpyxl`, loads the first visible non-empty worksheet, and fully materializes its rows into Python lists. (Actual: `src/suggestion/constants.py:13-18`, `src/suggestion/source/reader.py:41-120`, `src/suggestion/source/csv.py:174-185`, `src/suggestion/source/json.py:13-85`, `src/suggestion/source/excel.py:40-91`)

Suggestion also seeds the downstream `OperationConfig`. The defaults are:
- `assign_indices = false`
- `drop_empty_rows = true`
- `emit_raw_row = false`
- `emit_parse_issues = false`
- `trace_mode = "sparse"`
- readiness thresholds `ready=95.0`, `warning=85.0`

The threshold values are stored in config but are not used anywhere in execution. (Actual: `src/suggestion/constants.py:117-132`, `src/suggestion/pipeline.py:90-108`, `src/shared/models/operation.py:48-68`)

### 1.6 Ingestion and source handling

The shared ingestion layer supports only three declared formats: `csv`, `excel`, `json`. The Excel path is `.xlsx` only. Validation is strict on extension and magic bytes. JSON must be a top-level array. There is no archive extraction, no `.xls` support, no multi-file ingestion, and no workbook strategy handling. (Actual: `src/app/bootstrap/validation.py:11-63`, `src/shared/models/operation.py:11-45`)

CSV ingestion uses DuckDB `read_csv(... all_varchar=true)`. JSON ingestion uses DuckDB `read_json_auto(?)` and then casts all columns to `VARCHAR`. Excel ingestion uses `openpyxl`, builds a Python `rows` list, creates a DuckDB table, and bulk inserts via `executemany()`. (Actual: `src/shared/ingestion/service.py:24-65`, `src/shared/ingestion/csv/loader.py:18-52`, `src/shared/ingestion/json/loader.py:16-55`, `src/shared/ingestion/excel/loader.py:18-81`)

S3 support exists only as direct object read/download/upload helpers. Excel from S3 is downloaded to a temporary local file before ingestion. There is no multipart upload policy, no presigned URL generation, and no artifact visibility protocol. (Actual: `src/shared/ingestion/resolve.py:22-41`, `src/shared/storage/s3.py:31-107`)

### 1.7 Profiling phase

Profiling is a separate full-dataset phase executed after confirmation. It opens a file-backed DuckDB database, ingests the source, canonicalizes headers in-place, resolves column config by canonical name, computes row/null counts, computes per-type column profiles, and stores a `ProfilingOutput`. (Actual: `src/app/bootstrap/profiling.py:16-31`, `src/profiling/pipeline.py:24-69`, `src/shared/ingestion/canonicalization.py:13-76`)

ProfilingOutput contains:
- `source_checksum`
- `row_count`
- `empty_row_count`
- `column_count`
- `pattern_consistency_ratio`
- `completeness_ratio`
- `column_stats`
- `issues`

It does not contain drift results, anomaly summaries, schema stability, decision output, or artifact metadata. (Actual: `src/shared/models/profiling/output.py:12-29`)

The profiling issue system is narrow. Only two codes exist:
- `MIXED_CURRENCY`
- `SEPARATOR_MISMATCH`

Both are emitted as warnings. There is no blocking profiling issue in the current implementation. (Actual: `src/profiling/constants.py:5-14`, `src/profiling/issues.py:27-105`)

`pattern_consistency_ratio` is not a general pattern-consistency metric. The code sets it to `mean_dominant_symbol_ratio`, which is computed only from symbol-distribution profiles. On data with no symbol columns it becomes `1.0`. On mixed-currency data it becomes a currency-dominance score. The field name does not match the implemented metric. (Actual: `src/profiling/profiles.py:45-91`, `src/profiling/pipeline.py:60-69`)

### 1.8 Normalize / conversion phase

Normalization is not a 16-stage engine. It is a second fixed phase that reopens the persisted DuckDB file from profiling, resolves the confirmed config against canonical columns, builds a `RowPlan`, builds a `CellPlan`, composes one `CREATE OR REPLACE TABLE` transform SQL statement, computes quality metrics, and materializes artifacts. (Actual: `src/app/bootstrap/conversion.py:19-56`, `src/conversion/pipeline.py:25-59`, `src/conversion/rows.py:13-57`, `src/conversion/cells/stage.py:21-104`, `src/conversion/transform.py:11-151`)

The transform adds only five audit columns:
- `_row_index`
- `_global_row_index`
- `_raw_row`
- `_parse_issues`
- `_parse_error_count`

No provenance columns, no `_pattern_metadata`, and no `_anomaly_flags` are produced. Row indices are optional and suggestion defaults them off. (Actual: `src/conversion/constants.py:5-21`, `src/suggestion/constants.py:122-124`, `src/conversion/artifacts/export.py:15-18`)

Numeric normalization casts decimal-like values to `DOUBLE`, not deterministic `DECIMAL`. (Actual: `src/conversion/cells/exprs/numeric.py:47-87`)

The quality model is much smaller than the guide’s model:
- `parse_success_ratio`
- `completeness_ratio`
- `quality_score = 0.50 * parse_success_ratio + 0.50 * completeness_ratio`

There is no anomaly ratio, no pattern consistency component, and no schema stability component. (Actual: `src/conversion/quality_metrics.py:17-90`)

### 1.9 Artifact model

The artifact set is three files:
- `normalized.parquet`
- `manifest.json`
- `trace.parquet`

There is no pattern profile artifact. `NormalizationOutput` stores only `quality_output` plus three artifact paths. (Actual: `src/shared/models/normalization.py:8-37`, `src/conversion/artifacts/staging.py:47-90`)

The manifest payload is minimal: checksum, quality summary, issue summary, DuckDB version, and relative artifact paths. It does not include effective config, replay instructions, drift report, pattern analysis, trace mode deviation metadata, or execution tier. (Actual: `src/conversion/artifacts/manifest.py:22-46`)

Trace export is a wide-to-long UNPIVOT over the final DuckDB table. Trace mode is `full` or `sparse`, where `sparse` means rows pre-filtered to `_parse_error_count > 0` and then cells filtered to changed values or issue-bearing values. Each trace row hardcodes `applied_rules = 'type_cast'`. There is no template match, locale applied, detected pattern, pattern confidence, anomaly flag, or anomaly score. (Actual: `src/shared/models/operation.py:11-13`, `src/conversion/artifacts/staging.py:60-73`, `src/conversion/artifacts/trace.py:16-140`)

Artifact publication is coupled to source backend. `ConversionService` passes `source.source_type` into `materialize_artifacts()`. Local input sources publish to a local directory. S3 input sources publish to S3. There is no separate artifact storage contract. The path/key root is `run_id` (`instance_id`), not a deterministic `{source_id}/{dataset_id}/{fingerprint}` convention. (Actual: `src/app/bootstrap/conversion.py:43-52`, `src/conversion/artifacts/stage.py:19-45`, `src/conversion/artifacts/publish.py:18-79`)

## §2 — What The Original Plan Required

### 2.1 Required stack and infrastructure

The guide required this exact service stack:
- Python 3.11+, DuckDB 1.0+, PyArrow 15.0+, `python-calamine`, Dramatiq, Pydantic 2.6+, FastAPI 0.110+, SQLAlchemy 2.0+, `structlog`, `python-dateutil` pinned to 2.8.2 and scoped only to `pattern_discovery.py`, `pybreaker`, and APScheduler. (Guide: `data/implementation_guide_v2.md:15-62`)
- PostgreSQL 15+, RabbitMQ 3.12+, Cloudflare R2, Prometheus, Grafana, and Loki as mandatory infrastructure dependencies. (Guide: `data/implementation_guide_v2.md:66-88`)
- GitHub Actions, Docker, and Alembic as delivery and schema-management infrastructure. (Guide: `data/implementation_guide_v2.md:92-103`)
- Environment variables for runtime config, Git-managed rule/template/locale bundles, and API-key Bearer auth. (Guide: `data/implementation_guide_v2.md:104-118`)

### 2.2 Required repository shape

The guide required a service repository centered on `src/normalize/`, plus:
- `.github/workflows/{ci.yml,build.yml,deploy.yml}`
- `alembic/` and multiple migration files
- `docs/api`, `docs/operations`, `docs/architecture`
- `docker/Dockerfile.api`, `docker/Dockerfile.worker`, service-oriented compose files
- `scripts/` for DB setup, seeding, and rules bundle builds
- `src/normalize/api`, `src/normalize/core`, `src/normalize/stages`, `src/normalize/sql`, `src/normalize/rules`, `src/normalize/templates`, `src/normalize/locales`, `src/normalize/storage`, `src/normalize/tasks`, `src/normalize/observability`, `src/normalize/config`, `src/normalize/utils`
- unit, integration, performance, and golden-dataset tests across those components. (Guide: `data/implementation_guide_v2.md:122-1117`, `data/implementation_guide_v2.md:2695-2804`, `data/implementation_guide_v2.md:2853-2938`)

### 2.3 Required API layer

The guide required the API layer to:
- authenticate every request with Bearer API keys validated against PostgreSQL
- enforce per-key and per-tenant rate limits
- enforce queue backpressure with RabbitMQ queue-depth checks and `Retry-After`
- run inline only for sub-10K single-workbook jobs under a bounded semaphore and timeout
- enqueue all other work to Dramatiq and return a job ID immediately
- support status polling, artifact URL retrieval, progress polling, webhook management, and baseline management
- generate presigned R2 URLs only when artifacts are finalized
- expose middleware-backed FastAPI app, dependency injection, and OpenAPI docs. (Guide: `data/implementation_guide_v2.md:198-247`, `data/implementation_guide_v2.md:1123-1180`, `data/implementation_guide_v2.md:1966-1994`, `data/implementation_guide_v2.md:2680-2715`)

### 2.4 Required orchestration model

The guide required:
- a `NormalizationEngine` that orchestrates all 16 stages
- both `PROFILE` and `APPLY` execution modes
- a two-phase idempotency claim protocol around fingerprints
- job status persistence before queueing
- webhook dispatch on lifecycle events
- tier selection after Stage 4
- incremental normalization eligibility after Stage 10
- partition fan-out and merge coordination for Large and Massive tiers
- no long-running PostgreSQL transactions during DuckDB execution. (Guide: `data/implementation_guide_v2.md:266-314`, `data/implementation_guide_v2.md:1184-1219`, `data/implementation_guide_v2.md:1223-1271`, `data/implementation_guide_v2.md:3018-3117`)

### 2.5 Required execution modes

The guide required:
- `PROFILE`: run stages 1-14 only, persist evaluation results, skip persistent artifacts
- `APPLY`: run all 16 stages, materialize artifacts only when decision is not `BLOCKED` unless explicitly overridden
- identical evaluation results between modes for the same input
- execution mode stored in run metadata. (Guide: `data/implementation_guide_v2.md:1223-1248`)

### 2.6 Required persistence and storage model

The guide required PostgreSQL to store:
- normalization runs
- issues
- schema baselines
- templates
- locales
- webhooks
- partition runs
- orphaned artifact tracking
- optimistic-lock version columns
- tenant isolation via row-level security
- `artifacts_complete`, partition counters, execution tier, and incremental metadata on runs. (Guide: `data/implementation_guide_v2.md:146-172`, `data/implementation_guide_v2.md:631-642`, `data/implementation_guide_v2.md:1814-1845`, `data/implementation_guide_v2.md:2041-2064`)

The guide required Cloudflare R2 to store:
- normalized Parquet
- manifest JSON
- trace Parquet
- pattern profile JSON
- staged `.pending` uploads
- checksum validation before rename
- presigned URL generation only after `artifacts_complete = true`
- orphan cleanup and retention policies. (Guide: `data/implementation_guide_v2.md:635-638`, `data/implementation_guide_v2.md:1277-1305`, `data/implementation_guide_v2.md:1814-1845`, `data/implementation_guide_v2.md:2754-2778`)

### 2.7 Required configuration system

The guide required configuration for:
- database URL, RabbitMQ, R2, API-key salt, feature flags, worker counts
- tier thresholds, DuckDB memory limits, partition size, chunk sizes
- rate limiting and backpressure thresholds
- circuit breaker thresholds
- worker concurrency
- sweeper intervals
- trace mode (`full` by default, `selective` as explicit deviation)
- inline thresholds/timeouts/semaphore sizing
- incremental normalization toggles and tolerance
- locale/template/rule override precedence. (Guide: `data/implementation_guide_v2.md:708-710`, `data/implementation_guide_v2.md:1777-1810`, `data/implementation_guide_v2.md:2814-2856`)

### 2.8 Required observability and operations

The guide required:
- Prometheus metrics and codified alert rules
- `/metrics` exposure
- structured JSON logging with `structlog`
- Loki-compatible output
- distributed tracing spans
- queue, quality, drift, anomaly, backpressure, partition, and circuit-breaker metrics
- scheduled sweepers for stuck jobs, orphaned artifacts, and stuck partitions. (Guide: `data/implementation_guide_v2.md:647-700`, `data/implementation_guide_v2.md:1875-1927`, `data/implementation_guide_v2.md:2782-2810`)

### 2.9 Required rule/template/locale system

The guide required:
- immutable, versioned rule-pack bundles
- YAML templates and locales with validation
- builtin templates (`financial_transactions`, `inventory_management`, `employee_records`, `multi_period_financial`, `audit_trail`, `generic_tabular`)
- builtin locales (`en_US`, `en_GB`, `de_DE`, `fr_FR`, `zh_CN`, `ja_JP`)
- strict locale resolution with blocker errors for missing locale config
- effective config construction from defaults + locale + template + rules + workspace + dataset + column overrides. (Guide: `data/implementation_guide_v2.md:468-622`, `data/implementation_guide_v2.md:1746-1810`, `data/implementation_guide_v2.md:2132-2179`)

### 2.10 Required stage pipeline

The guide required a fixed 16-stage pipeline, in this order, with no stage added, removed, or reordered:

1. Ingestion: Calamine/PyArrow-based file loading, archive extraction, zero-copy Arrow registration, checksums, UTF-8 normalization. (Guide: `data/implementation_guide_v2.md:2221-2248`)
2. Multi-workbook detection and validation: workbook manifest, Calamine sheet metadata, workbook count checks. (Guide: `data/implementation_guide_v2.md:2252-2277`)
3. Sheet selection: visible-sheet filtering and workbook sheet strategy. (Guide: `data/implementation_guide_v2.md:2281-2300`)
4. Cross-workbook schema alignment: DuckDB concatenation strategies plus provenance columns. (Guide: `data/implementation_guide_v2.md:2304-2330`)
5. Header canonicalization: canonical names plus template mapping. (Guide: `data/implementation_guide_v2.md:2334-2353`)
6. Schema drift detection: baseline compare, quality drift compare, policy evaluation. (Guide: `data/implementation_guide_v2.md:2357-2384`)
7. Row normalization: stable row indices, empty-row removal, lineage columns. (Guide: `data/implementation_guide_v2.md:2388-2407`)
8. Pattern discovery and profiling: DuckDB regex sampling, dominant patterns, relative-date blocking. (Guide: `data/implementation_guide_v2.md:2411-2450`)
9. Mixed-type detection and resolution: entropy-based categories and resolution plans. (Guide: `data/implementation_guide_v2.md:2454-2472`)
10. Type inference: Arrow schema inference with parse-success and pattern-consistency thresholds, DECIMAL not DOUBLE for currency/percentage. (Guide: `data/implementation_guide_v2.md:2476-2496`)
11. Cell normalization: bulk DuckDB normalization with `_raw_row`, `_parse_issues`, `_pattern_metadata`. (Guide: `data/implementation_guide_v2.md:2500-2525`)
12. Anomaly detection: outliers, exact/fuzzy duplicates, constraint violations, `_anomaly_flags`. (Guide: `data/implementation_guide_v2.md:2529-2557`)
13. Quality metrics: five-component deterministic score. (Guide: `data/implementation_guide_v2.md:2561-2593`)
14. Decision evaluation: `READY`, `READY_WITH_WARNINGS`, `BLOCKED`, `FAILED`. (Guide: `data/implementation_guide_v2.md:2597-2616`)
15. Artifact materialization: Parquet + manifest + trace + pattern profile, skipped in PROFILE mode. (Guide: `data/implementation_guide_v2.md:2620-2649`)
16. Manifest and trace finalization: completed manifest metadata and indexed trace. (Guide: `data/implementation_guide_v2.md:2653-2665`)

### 2.11 Required scalability model

The guide required:
- deterministic tier selection after Stage 4
- inline tier for <10K rows and single workbook
- Standard tier single-pass to <1M rows
- Large tier partition-merge for 1M-10M rows
- Massive tier partition-merge for >10M rows
- uniform 4GB DuckDB limit across tiers
- partition exports via `COPY TO`
- chunked Arrow trace export
- deterministic partition boundaries and merge ordering
- progress reporting via partition counters
- incremental normalization after Stage 10 for append-only datasets
- guaranteed output equivalence across inline, single-pass, partitioned, and incremental paths. (Guide: `data/implementation_guide_v2.md:1929-1962`, `data/implementation_guide_v2.md:3018-3342`)

### 2.12 Required testing and delivery

The guide required:
- unit tests for stages and core components
- integration tests for end-to-end, API, drift, storage, partitioning, backpressure, and incremental flows
- performance tests for partition throughput
- golden datasets covering ambiguity, locales, anomalies, drift, sparse data, malformed records, and scalability tiers
- CI workflows to run linting, typing, unit/integration tests, builds, and deploys. (Guide: `data/implementation_guide_v2.md:859-989`, `data/implementation_guide_v2.md:2708-2804`, `data/implementation_guide_v2.md:2901-2938`)

## §3 — The Divergence Map (Global + Unit Level)

### 3.1 Global architectural divergences

#### G1. Service architecture vs local workflow

Specified:
- a service split into API layer, async worker layer, engine, queue, storage, observability, and background maintenance. (Guide: `data/implementation_guide_v2.md:1125-1151`, `data/implementation_guide_v2.md:1186-1219`, `data/implementation_guide_v2.md:2719-2810`)

Built instead:
- a synchronous four-phase workflow driven by `MainOrchestrator`, callable from both API and CLI, with no queue or worker tier. (Actual: `src/app/bootstrap/orchestrator.py:29-126`, `main.py:1-40`, `CLAUDE.md:45-60`)

Why it likely changed:
- the repo’s own architecture notes codify the four-phase workflow and a responsibility-based package split. This was a conscious re-scope, not an accidental omission. (Actual: `CLAUDE.md:45-60`, `FILE_PHILOSOPHY.md:9-31`)

#### G2. `src/normalize` stage engine vs top-level phase packages

Specified:
- a `src/normalize/` package with `api/`, `core/`, `stages/`, `storage/`, `tasks/`, `observability/`, `rules/`, `templates/`, and `locales/`. (Guide: `data/implementation_guide_v2.md:192-710`)

Built instead:
- `src/app`, `src/shared`, `src/suggestion`, `src/profiling`, and `src/conversion`; no `src/normalize` exists. (Actual: `CLAUDE.md:49-57`, `FILE_PHILOSOPHY.md:41-50`)

Why it likely changed:
- the current code optimizes for package-local clarity around the four fixed phases, not for a reusable stage engine. (Actual: `FILE_PHILOSOPHY.md:56-69`, `FILE_PHILOSOPHY.md:216-220`)

#### G3. 16-stage pipeline vs two analysis phases plus one transform phase

Specified:
- a fixed 16-stage pipeline with explicit stage boundaries, outputs, and invariants. (Guide: `data/implementation_guide_v2.md:2031-2665`, `data/implementation_guide_v2.md:3016-3018`)

Built instead:
- suggestion phase for config inference, profiling phase for counts/profiles/issues, conversion phase for transform/quality/artifacts. There is no stage 6 drift detection, no stage 8 pattern engine, no stage 9 mixed-type resolution stage, no stage 12 anomaly detection, no stage 14 decision stage, and no stage 16 finalization stage. (Actual: `src/suggestion/pipeline.py:1-122`, `src/profiling/pipeline.py:1-69`, `src/conversion/pipeline.py:1-59`, `src/conversion/artifacts/stage.py:19-45`)

Why it likely changed:
- complexity was cut by collapsing the guide’s analysis and governance stages into heuristic config inference plus one transform. The code never introduces the missing stage outputs those later stages would have needed. (Actual: `src/shared/models/profiling/output.py:21-29`, `src/shared/models/normalization.py:20-37`)

#### G4. Async jobs and queueing vs synchronous request/command execution

Specified:
- inline execution for small jobs, RabbitMQ + Dramatiq for the rest, backpressure on submission, progress polling, worker retries, and sweepers. (Guide: `data/implementation_guide_v2.md:1138-1143`, `data/implementation_guide_v2.md:1966-1994`, `data/implementation_guide_v2.md:2719-2750`, `data/implementation_guide_v2.md:3187-3208`)

Built instead:
- every API call and every CLI command executes work directly in-process. There is no async fallback path. (Actual: `src/app/api/router.py:26-51`, `src/app/bootstrap/orchestrator.py:44-126`, `src/app/cli/suggest.py:36-62`, `src/app/cli/profile.py:19-36`, `src/app/cli/convert.py:17-33`)

Why it likely changed:
- the current product is optimized for direct operator-driven execution, and the repo contains no queue-related config or code. (Actual: `src/shared/settings.py:10-33`, `pyproject.toml:11-22`)

#### G5. PROFILE/APPLY split vs always-materialize normalize path

Specified:
- `PROFILE` and `APPLY` as first-class modes with stage skipping and artifact suppression in PROFILE. (Guide: `data/implementation_guide_v2.md:1223-1248`)

Built instead:
- `profile` is a separate prerequisite phase, and `normalize` always runs conversion plus artifact materialization. The only trace of `MODE=APPLY` is CLI/Makefile argument plumbing that is never consumed by runtime code. (Actual: `Makefile:9-12`, `Makefile:69-103`, `main.py:4-12`, `src/app/cli/convert.py:14-27`, `src/app/bootstrap/conversion.py:22-56`)

Why it likely changed:
- the architecture replaced execution modes with a manual review checkpoint (`confirm` and `profile`) followed by unconditional apply. The old mode vocabulary survived only in CLI docs. (Actual: `CLAUDE.md:30-39`, `src/app/bootstrap/orchestrator.py:61-126`)

#### G6. Rich relational persistence vs one JSONB snapshot table

Specified:
- a normalized PostgreSQL schema with run metadata, issues, baselines, templates, locales, webhooks, partition runs, optimistic locking, and tenant isolation. (Guide: `data/implementation_guide_v2.md:146-172`, `data/implementation_guide_v2.md:631-642`, `data/implementation_guide_v2.md:1814-1845`)

Built instead:
- one `normalization_runs` table with JSONB snapshots and runtime DDL. (Actual: `src/app/infra/postgres/repository.py:36-137`)

Why it likely changed:
- the implementation favors minimal persistence friction over queryability and service semantics. Every lifecycle output is serialized wholesale back into the same row. (Actual: `src/app/persistence/serialization.py:15-90`)

#### G7. Deterministic artifact service vs source-coupled output publishing

Specified:
- all artifacts stored in Cloudflare R2 with staged upload protocol, deterministic final paths, presigned retrieval, and `artifacts_complete` visibility gate. (Guide: `data/implementation_guide_v2.md:1277-1305`, `data/implementation_guide_v2.md:1814-1845`)

Built instead:
- local-source runs write to filesystem and return server paths; S3-source runs upload directly and return raw keys. No staged upload, no finalization gate, no presigned retrieval, and no deterministic fingerprint-based pathing exists. (Actual: `src/app/bootstrap/conversion.py:43-52`, `src/conversion/artifacts/publish.py:18-79`, `src/shared/models/normalization.py:8-18`)

Why it likely changed:
- artifact storage was reduced to “write near the execution backend,” which is simpler locally but destroys the guide’s retrieval and consistency model. (Actual: `src/conversion/artifacts/stage.py:19-45`)

#### G8. Rule/template/locale/baseline-driven normalization vs per-run direct config

Specified:
- immutable rule bundles, YAML templates/locales, strict locale resolution, baseline-driven drift detection, and override precedence across multiple scopes. (Guide: `data/implementation_guide_v2.md:1746-1810`, `data/implementation_guide_v2.md:2132-2179`)

Built instead:
- each run carries a direct `InstanceConfig` plus `OperationConfig` with separators/date formats/tokens already baked in. There is no rules engine, no template loader, no locale loader, and no baseline lookup. (Actual: `src/shared/models/instance_config.py:10-15`, `src/shared/models/operation.py:17-68`, `src/app/bootstrap/orchestrator.py:61-126`)

Why it likely changed:
- current code chose explicit per-run config over platform-managed configuration assets. Suggestion is now the config authoring mechanism. (Actual: `src/suggestion/pipeline.py:71-122`)

#### G9. Observability platform vs almost no operational instrumentation

Specified:
- Prometheus, alert rules, `/metrics`, structured logs, tracing, Dramatiq middleware metrics, and sweepers. (Guide: `data/implementation_guide_v2.md:647-700`, `data/implementation_guide_v2.md:2782-2810`)

Built instead:
- no observability package, no metrics endpoint, no structured logging layer, no trace propagation, and no maintenance jobs. The app wiring is only exception handlers plus router registration, the dependency list contains none of the required observability libraries, and the compose file provisions no monitoring services. (Actual: `src/app/api/server.py:21-29`, `pyproject.toml:11-22`, `docker-compose.yml:1-20`)

Why it likely changed:
- the runtime was collapsed to a direct workflow and the operational scaffolding was never ported into the smaller architecture.

#### G10. Scalability architecture vs single-node execution

Specified:
- inline/standard/large/massive tiers, partition-merge execution, deterministic boundaries, global-stat precompute, and incremental normalization. (Guide: `data/implementation_guide_v2.md:1929-1962`, `data/implementation_guide_v2.md:3018-3342`)

Built instead:
- one-process execution with a single DuckDB database file passed from profile to normalize. No tier selector, no partition coordinator, no partition artifacts, no merge worker, no incremental fast path. (Actual: `src/app/bootstrap/profiling.py:26-29`, `src/app/bootstrap/conversion.py:33-42`, `src/shared/db/duckdb.py:22-68`)

Why it likely changed:
- the current implementation targets local or moderate workloads and never builds the coordination state the guide’s scalability design required.

#### G11. Security and tenancy model vs trusted local workflow

Specified:
- Bearer auth, hashed API keys, tenant propagation, per-tenant rate limits, row-level security, and secret-safe operations. (Guide: `data/implementation_guide_v2.md:1155-1180`, `data/implementation_guide_v2.md:1814-1845`)

Built instead:
- no auth, no tenant propagation, no rate limiting, and a checked-in `.env` containing live-looking R2 credentials. (Actual: `src/app/api/router.py:21-51`, `src/shared/models/instance.py:48-69`, `.env:1-9`)

Why it likely changed:
- the system is being used like an internal tool, not like a multi-tenant service. The danger is that the API still looks service-like while lacking service controls.

#### G12. Test-backed delivery vs unprotected runtime code

Specified:
- unit, integration, performance, and golden-dataset coverage plus CI/CD workflows. (Guide: `data/implementation_guide_v2.md:92-103`, `data/implementation_guide_v2.md:859-989`, `data/implementation_guide_v2.md:2901-2938`)

Built instead:
- `pyproject.toml` still points pytest at `tests/`, but the runtime code and repo-local docs now stand without a live, referenced test implementation surface in the current tree. (Actual: `pyproject.toml:40-43`, `CLAUDE.md:12-16`, `CLAUDE.md:25-28`)

Why it likely changed:
- the architecture was shifted faster than the verification story was maintained. The result is a runtime-heavy codebase with little visible protection.

### 3.2 Unit/component-level divergences

#### U1. `src/app/bootstrap/orchestrator.py`

Specified:
- a `NormalizationEngine` that owns the full 16-stage pipeline, idempotency, modes, tier selection, and incremental coordination. (Guide: `data/implementation_guide_v2.md:266-314`, `data/implementation_guide_v2.md:1184-1219`)

Built instead:
- `MainOrchestrator` only sequences `suggest`, `confirm`, `profile`, and `normalize`. It has no fingerprint logic, no mode logic, no tier selection, no incremental flow, and no retry/recovery policy. (Actual: `src/app/bootstrap/orchestrator.py:29-126`)

Likely change driver:
- the engine abstraction was replaced by a lifecycle coordinator around persisted `InstanceModel` snapshots.

#### U2. `src/app/api/*`

Specified:
- auth, dependency injection, backpressure, rate limiting, dual-path normalize route, status/artifact/webhook/baseline routes, and OpenAPI-backed schemas. (Guide: `data/implementation_guide_v2.md:198-247`, `data/implementation_guide_v2.md:2680-2715`)

Built instead:
- one router with instance-centric CRUD-like endpoints and no service controls. `GET /health` is static and does not check dependencies. (Actual: `src/app/api/router.py:21-51`, `src/app/api/server.py:21-29`)

Likely change driver:
- the API was reduced to a remote wrapper over the same workflow the CLI already runs.

#### U3. `src/app/infra/postgres/repository.py`

Specified:
- SQLAlchemy ORM models, migrations, query builders, issue persistence, baseline operations, partition coordination, optimistic locking. (Guide: `data/implementation_guide_v2.md:631-642`, `data/implementation_guide_v2.md:1814-1845`)

Built instead:
- one psycopg repository that upserts a single row shape into a single table, with runtime `CREATE TABLE IF NOT EXISTS`. (Actual: `src/app/infra/postgres/repository.py:28-137`)

Likely change driver:
- minimizing persistence work while retaining just enough durability for manual lifecycle handoff.

#### U4. `src/shared/settings.py` and `.env.example`

Specified:
- broad service and scaling config surface, including queueing, auth, backpressure, circuit breaker, sweeper, and incremental knobs. (Guide: `data/implementation_guide_v2.md:2818-2856`)

Built instead:
- only DuckDB/Postgres/S3/output settings. (Actual: `src/shared/settings.py:10-33`, `.env.example:1-10`)

Likely change driver:
- service-wide operations config was dropped because the runtime no longer contains those components.

#### U5. `src/shared/ingestion/*`

Specified:
- Calamine + Arrow ingestion, `.xls` support, archives, multi-file ordering, workbook metadata, zero-copy registration, sheet visibility handling. (Guide: `data/implementation_guide_v2.md:2221-2300`)

Built instead:
- direct CSV/JSON DuckDB loaders and `openpyxl`-based Excel ingestion. Validation rejects anything outside `.csv`, `.xlsx`, and `.json`. (Actual: `src/app/bootstrap/validation.py:11-63`, `src/shared/ingestion/service.py:24-65`, `src/shared/ingestion/excel/loader.py:18-81`)

Likely change driver:
- ingestion was simplified to the minimum set needed for the current lifecycle, and guide-level workbook orchestration was never ported.

#### U6. `src/suggestion/*`

Specified:
- stages 8-10 driven by rules, templates, locales, DuckDB regex sampling, mixed-type resolution, and Arrow type inference thresholds. (Guide: `data/implementation_guide_v2.md:2411-2496`)

Built instead:
- a pre-pipeline config suggestion system using sampled values, Python heuristics, and position-keyed `ColumnConfig` inference. (Actual: `src/suggestion/pipeline.py:71-122`, `src/suggestion/source/reader.py:41-120`, `src/suggestion/column_config/date.py:11-32`)

Likely change driver:
- the current product needed a user-facing config bootstrapper more than a declarative rules-and-template stage stack.

#### U7. `src/profiling/*`

Specified:
- separate drift detection, pattern discovery, anomaly detection, quality metrics, and decision stages with rich artifacts and blocking logic. (Guide: `data/implementation_guide_v2.md:2357-2616`)

Built instead:
- one profiling phase that computes counts, per-type profiles, and two warning families. (Actual: `src/profiling/pipeline.py:24-69`, `src/profiling/counts.py:23-68`, `src/profiling/column_stats/dispatch.py:38-97`, `src/profiling/issues.py:18-105`)

Likely change driver:
- profiling became a lighter safety check ahead of transform, not a full governance/evaluation pipeline.

#### U8. `src/conversion/*`

Specified:
- stage 11 normalization + stage 12 anomaly detection + stage 13 quality + stage 14 decision + stage 15 artifact materialization + stage 16 finalization, with DECIMAL precision and rich metadata columns. (Guide: `data/implementation_guide_v2.md:2500-2665`)

Built instead:
- one transform plus quality calculation plus artifact writing. No anomaly stage, no decision stage, no finalization stage, and decimal-like values are cast to `DOUBLE`. (Actual: `src/conversion/pipeline.py:25-59`, `src/conversion/cells/exprs/numeric.py:47-87`, `src/conversion/quality_metrics.py:17-90`)

Likely change driver:
- the code optimizes for one bulk SQL rewrite over the table rather than staged metadata enrichment.

#### U9. `src/conversion/artifacts/*`

Specified:
- Parquet + manifest + trace + pattern profile, plus staged upload, replay instructions, trace schema richness, and execution-tier-aware export strategies. (Guide: `data/implementation_guide_v2.md:1701-1742`, `data/implementation_guide_v2.md:2620-2665`)

Built instead:
- three artifacts only, minimal manifest, sparse/full trace with fixed `type_cast` rule marker, direct local or S3 publishing. (Actual: `src/conversion/artifacts/staging.py:36-90`, `src/conversion/artifacts/manifest.py:22-46`, `src/conversion/artifacts/trace.py:16-140`, `src/conversion/artifacts/publish.py:18-79`)

Likely change driver:
- artifact handling was reduced to what the current conversion output can actually produce.

#### U10. `src/shared/storage/s3.py`

Specified:
- R2 artifact storage with staged uploads, checksums, presigned URLs, cleanup coordination, and circuit breakers. (Guide: `data/implementation_guide_v2.md:635-638`, `data/implementation_guide_v2.md:1814-1845`)

Built instead:
- simple boto3 helper functions for `get_object`, temp download, and direct upload. (Actual: `src/shared/storage/s3.py:31-107`)

Likely change driver:
- storage became a generic utility layer rather than a service-level artifact manager.

#### U11. `src/shared/models/instance.py` and `src/shared/models/operation.py`

Specified:
- domain models centered on dataset inputs, normalization runs, issues, schema drift, anomaly policy, execution mode, and tier-aware orchestration. (Guide: `data/implementation_guide_v2.md:256-264`, `data/implementation_guide_v2.md:2083-2095`)

Built instead:
- models centered on `InstanceModel`, `InstanceConfig`, and `OperationConfig` flags for the current four-phase workflow. `decision_thresholds`, `READY_WITH_WARNINGS`, `BLOCKED`, and `FAILED` exist in the types but are not wired into execution. (Actual: `src/shared/models/instance.py:16-92`, `src/shared/models/operation.py:48-68`, `src/conversion/quality_metrics.py:17-90`, `src/app/bootstrap/orchestrator.py:92-126`)

Likely change driver:
- the model layer was preserved as a strict contract surface, but the execution logic that should consume those richer states was never built.

#### U12. `data/full_data_suggestion_compare.py`

Specified:
- not part of the guide; any internal tooling should track the current architecture. (Guide: no corresponding component)

Built instead:
- a stale diagnostic script that still imports removed modules such as `shared.utils.column`, `shared.utils.currency`, `shared.utils.sign_markers`, and `shared.utils.values`. (Actual: `data/full_data_suggestion_compare.py:37-43`)

Likely change driver:
- the architecture changed but supporting tools were not cleaned up.

## §4 — End-to-End Flow Comparison

### 4.1 Original plan flow

1. Client submits a normalization job to the API with Bearer auth, rate limits, and RabbitMQ backpressure checks. Inline-eligible jobs may run synchronously; everything else is queued. (Guide: `data/implementation_guide_v2.md:1125-1151`, `data/implementation_guide_v2.md:2680-2693`)
2. Job metadata is persisted to PostgreSQL before execution. Fingerprint-based idempotency claim prevents duplicate concurrent work. (Guide: `data/implementation_guide_v2.md:1200-1208`, `data/implementation_guide_v2.md:1252-1271`)
3. `NormalizationEngine` runs stages 1-4 to ingest, detect workbooks, select sheets, and align schemas; tier selection happens after Stage 4. (Guide: `data/implementation_guide_v2.md:2221-2330`, `data/implementation_guide_v2.md:1929-1962`)
4. The engine runs stages 5-10 for canonicalization, drift detection, row normalization, pattern discovery, mixed-type resolution, and type inference. Incremental eligibility is evaluated after Stage 10. (Guide: `data/implementation_guide_v2.md:2334-2496`, `data/implementation_guide_v2.md:1207-1210`, `data/implementation_guide_v2.md:3265-3318`)
5. Standard tier runs stages 11-16 in one worker. Large/Massive tiers partition stages 11-12 across workers, then merge and run stages 13-16. (Guide: `data/implementation_guide_v2.md:2721-2750`, `data/implementation_guide_v2.md:3067-3117`)
6. Stage 14 produces a terminal decision. In PROFILE mode the flow stops here with persisted evaluation output. In APPLY mode, stages 15-16 write artifacts if policy allows. (Guide: `data/implementation_guide_v2.md:1223-1248`, `data/implementation_guide_v2.md:2597-2665`)
7. Artifacts upload to R2 via staged `.pending` keys, checksums are validated, `artifacts_complete` is set only after all final keys exist, and presigned URLs are exposed to callers only after that gate is true. (Guide: `data/implementation_guide_v2.md:1277-1305`, `data/implementation_guide_v2.md:1814-1845`)
8. Status, progress, artifacts, webhooks, baselines, and observability all flow through PostgreSQL, RabbitMQ, and the monitoring stack. (Guide: `data/implementation_guide_v2.md:1184-1219`, `data/implementation_guide_v2.md:2680-2810`)

### 4.2 Actual flow

1. Caller already knows a server-local path or S3 key and submits it to either the CLI or `POST /normalize/suggest`, along with a checksum. The API does not authenticate or queue. (Actual: `src/shared/models/source.py:9-15`, `src/app/api/models.py:11-20`, `src/app/api/router.py:26-28`, `src/app/cli/suggest.py:45-56`)
2. `MainOrchestrator.suggest()` validates file format, runs the suggestion heuristic pass, creates an `InstanceModel`, stores `suggested_config` plus display data, and persists the row. (Actual: `src/app/bootstrap/orchestrator.py:44-59`)
3. Caller confirms by sending or loading a full `InstanceConfig`. The system stores it and moves the instance to `CONFIRMED`. (Actual: `src/app/bootstrap/orchestrator.py:61-65`, `src/app/cli/confirm.py:32-37`)
4. `profile()` sets status to `PROFILING`, ingests the full source into a file-backed DuckDB database, canonicalizes headers, computes counts/profiles/issues, stores `ProfilingOutput`, and moves the instance to `PROFILED`. (Actual: `src/app/bootstrap/orchestrator.py:67-90`, `src/app/bootstrap/profiling.py:19-31`, `src/profiling/pipeline.py:24-69`)
5. `normalize()` reopens the same DuckDB file, checks only for `ERROR`-severity profiling issues, runs the conversion transform, computes a two-factor quality score, writes artifacts, deletes the DuckDB cache file on success, stores `NormalizationOutput`, and moves the instance to `READY`. (Actual: `src/app/bootstrap/orchestrator.py:92-126`, `src/app/bootstrap/conversion.py:22-56`, `src/conversion/pipeline.py:25-59`, `src/conversion/quality_metrics.py:42-90`)
6. The API returns the full `InstanceModel`, which includes raw artifact paths or S3 keys. There is no later retrieval flow. (Actual: `src/app/api/router.py:26-51`, `src/shared/models/normalization.py:8-37`)

### 4.3 Where the paths split

- The original flow splits at the API boundary into inline vs queued execution. The current flow never leaves the request/command process. (Guide: `data/implementation_guide_v2.md:1138-1143`; Actual: `src/app/api/router.py:26-51`)
- The original flow merges governance stages into the engine before decision. The current flow front-loads config suggestion and separates profiling from normalization. (Guide: `data/implementation_guide_v2.md:2411-2616`; Actual: `src/suggestion/pipeline.py:71-122`, `src/profiling/pipeline.py:24-69`)
- The original flow introduces tier selection after Stage 4 and possibly incremental mode after Stage 10. The current flow never branches by dataset size or previous runs. (Guide: `data/implementation_guide_v2.md:1207-1210`, `data/implementation_guide_v2.md:3018-3342`; Actual: `src/app/bootstrap/orchestrator.py:29-126`)
- The original flow can terminate at Stage 14 in PROFILE mode. The current flow treats `profile` as a prerequisite and `normalize` as unconditional artifact production. (Guide: `data/implementation_guide_v2.md:1223-1248`; Actual: `src/app/bootstrap/orchestrator.py:67-126`)
- The original flow ends with R2 finalization and visibility gating. The current flow ends as soon as files are written and, for S3, uploaded directly. (Guide: `data/implementation_guide_v2.md:1277-1305`; Actual: `src/conversion/artifacts/publish.py:51-65`)

## §5 — Honest Quality Verdict

This codebase is cleaner than the guide in exactly one dimension: local conceptual load. The current packages are readable, the four-phase lifecycle is straightforward, and the separation between `suggestion`, `profiling`, and `conversion` is internally coherent. That is real engineering value. (Actual: `CLAUDE.md:45-60`, `FILE_PHILOSOPHY.md:9-31`)

It is not a better implementation of the guide. It is a smaller product built by deleting the hardest parts of the guide.

Performance:
- For small, operator-driven runs, the synchronous workflow is faster to understand and avoids RabbitMQ/Dramatiq overhead. (Actual: `src/app/bootstrap/orchestrator.py:29-126`)
- For Excel and larger datasets, the current code is materially worse than the guide’s target architecture. Suggestion fully materializes worksheet rows, and ingestion buffers all rows in Python before bulk insert. The guide explicitly chose Calamine + Arrow + DuckDB zero-copy paths to avoid this. (Guide: `data/implementation_guide_v2.md:23-30`, `data/implementation_guide_v2.md:2221-2248`; Actual: `src/suggestion/source/excel.py:40-91`, `src/shared/ingestion/excel/loader.py:18-81`)

Scalability:
- The current architecture does not scale to the guide’s workload model. There is no tier selector, no partitioning, no queue, no progress reporting, no backpressure, and no incremental path. (Guide: `data/implementation_guide_v2.md:1929-1962`, `data/implementation_guide_v2.md:3018-3342`; Actual: `src/app/api/router.py:21-51`, `src/app/bootstrap/orchestrator.py:29-126`, `src/shared/settings.py:10-33`)

Maintainability:
- Package layout is maintainable.
- System truth is not maintainable. The repo contains a guide for a distributed normalization service, but the code implements a different tool. That mismatch will keep producing wrong decisions until one side is deleted or rewritten. (Guide: `data/implementation_guide_v2.md:122-1117`; Actual: `CLAUDE.md:43-60`)
- The single-table JSONB persistence model lowers initial coding cost but makes run history, issue analytics, schema evolution, and artifact consistency harder than they need to be. (Actual: `src/app/infra/postgres/repository.py:36-137`)

Coupling:
- Internal package coupling is acceptable.
- Architectural coupling is poor in two places:
  - source backend determines artifact backend
  - API/CLI/persistence all share one monolithic `InstanceModel` snapshot contract

  These are convenience couplings, not durable platform boundaries. (Actual: `src/app/bootstrap/conversion.py:43-52`, `src/conversion/artifacts/publish.py:71-79`, `src/app/api/router.py:26-51`, `src/app/persistence/serialization.py:15-90`)

Testability:
- Current testability is poor. The runtime has no active test tree in the current worktree, and at least one diagnostic script already references removed modules. (Actual: `pyproject.toml:40-43`, `data/full_data_suggestion_compare.py:37-43`)

Complexity cost:
- The guide paid complexity to get distributed execution, operational safety, and governance features.
- The current code removed that complexity, but it also removed the guarantees that justified the product. The simplification was mostly convenience and scope reduction, not a strictly better architecture for the specified system.

Bottom line:
- If the intended product is a local or operator-assisted normalization tool, the current architecture is directionally reasonable but unfinished.
- If the intended product is the service described in the guide, the current architecture is the wrong system.

## §6 — Gap Analysis With Hard Recommendations

### 6.1 Implement as planned

| Gap | Recommendation | Why |
|---|---|---|
| Terminal decision logic (`READY`, `READY_WITH_WARNINGS`, `BLOCKED`, `FAILED`) | Implement as planned. | The type system already exposes these states, but execution never produces them. Without a real decision stage, the system publishes outputs it has no authority to mark as ready. (Guide: `data/implementation_guide_v2.md:2597-2616`; Actual: `src/shared/models/instance.py:16-28`, `src/app/bootstrap/orchestrator.py:92-126`) |
| `PROFILE` vs `APPLY` semantics | Implement as planned. | The current `profile` phase is not an execution mode. You need a mode boundary that can return evaluation results without forcing artifact publication. (Guide: `data/implementation_guide_v2.md:1223-1248`; Actual: `src/app/bootstrap/orchestrator.py:67-126`, `src/app/cli/convert.py:17-27`) |
| Failure-state persistence and recovery | Implement as planned. | Unhandled exceptions currently strand runs in `PROFILING` or `NORMALIZING`. Even if you keep the synchronous architecture, failed-state persistence is mandatory. (Guide: `data/implementation_guide_v2.md:1277-1305`; Actual: `src/app/bootstrap/orchestrator.py:72-89`, `src/app/bootstrap/orchestrator.py:102-126`) |
| Migration-managed schema | Implement as planned. | Runtime DDL is not acceptable for a persistent system. You need explicit migrations before the schema grows any further. (Guide: `data/implementation_guide_v2.md:100-103`, `data/implementation_guide_v2.md:2037-2069`; Actual: `src/app/infra/postgres/repository.py:115-137`) |
| Automated test suite | Implement as planned. | This repo is now architecture-defining code. Shipping it without tests is negligent. (Guide: `data/implementation_guide_v2.md:2901-2938`; Actual: `pyproject.toml:40-43`) |

### 6.2 Re-implement differently for the new architecture

| Gap | Recommendation | How |
|---|---|---|
| Engine shape | Re-implement differently for the new architecture. | Keep the synchronous architecture, but replace `MainOrchestrator + profile cache handoff + normalize` with one explicit synchronous engine that has named internal stages and a single run contract. Suggestion can remain separate. Profiling and conversion should become engine stages, not two independent app services. (Actual: `src/app/bootstrap/orchestrator.py:29-126`) |
| Persistence model | Re-implement differently for the new architecture. | Replace the single JSONB snapshot row with at least three tables: `runs`, `issues`, and `artifacts`. Keep JSONB only for flexible evidence payloads. Do not keep serializing the full object graph into one row. (Actual: `src/app/infra/postgres/repository.py:36-137`, `src/app/persistence/serialization.py:15-90`) |
| Artifact storage contract | Re-implement differently for the new architecture. | Make artifact backend explicit and independent from source backend. The caller should never receive server filesystem paths for API-triggered runs. Add a small artifact service layer even if you stay synchronous. (Actual: `src/app/bootstrap/conversion.py:43-52`, `src/conversion/artifacts/publish.py:71-79`) |
| Quality/profiling semantics | Re-implement differently for the new architecture. | Either implement the guide’s metrics or rename the current ones to what they actually mean. `pattern_consistency_ratio` must stop meaning “mean dominant currency-symbol ratio.” Decision thresholds must either be consumed or removed. (Actual: `src/profiling/pipeline.py:60-69`, `src/profiling/profiles.py:81-90`, `src/shared/models/operation.py:48-68`) |
| Excel path | Re-implement differently for the new architecture. | Keep the synchronous workflow but swap `openpyxl` row materialization for a reader that can stream tabular data into DuckDB without duplicating it in Python lists. The guide’s Calamine choice was correct here even if the rest of the guide is not. (Guide: `data/implementation_guide_v2.md:27-29`; Actual: `src/suggestion/source/excel.py:40-91`, `src/shared/ingestion/excel/loader.py:18-81`) |
| Trace/audit model | Re-implement differently for the new architecture. | Decide what auditability this product really promises. If trace is only about parse failures, model it that way explicitly. If you claim per-cell explainability, add rule identifiers, pattern metadata, and anomaly flags. (Guide: `data/implementation_guide_v2.md:1723-1724`; Actual: `src/conversion/artifacts/trace.py:71-112`) |

### 6.3 Kill entirely in this codebase

| Missing/replaced capability | Recommendation | Why |
|---|---|---|
| RabbitMQ + Dramatiq worker layer | Kill it entirely in this codebase. | Bolting queue semantics onto the current instance-oriented workflow will recreate the guide badly. If the platform still needs an async service, build that as a separate service package or repo, not as a retrofit here. (Guide: `data/implementation_guide_v2.md:31-33`, `data/implementation_guide_v2.md:2719-2750`; Actual: `pyproject.toml:11-22`) |
| Partition/merge scalability system | Kill it entirely in this codebase. | The current code has no abstractions for partition state, merge state, or equivalent-output guarantees. Retrofitting them will fight every major design choice in the repo. (Guide: `data/implementation_guide_v2.md:1929-1962`, `data/implementation_guide_v2.md:3067-3117`; Actual: `src/app/bootstrap/orchestrator.py:29-126`) |
| Incremental normalization fast path | Kill it entirely in this codebase. | The current persistence, artifact, and fingerprint model is nowhere close to supporting deterministic incremental replay. Do not fake it. (Guide: `data/implementation_guide_v2.md:3063-3342`; Actual: `src/app/infra/postgres/repository.py:36-137`, `src/shared/models/normalization.py:33-37`) |
| Baselines and drift subsystem | Kill it entirely in this codebase. | The current tool does not have the relational backbone, query model, or API semantics for baseline lifecycle management. The API exposes no baseline routes, the repository has no baseline tables, and the runtime config has no baseline settings. Reintroducing baselines here without the rest of the planned service would create dead weight. (Guide: `data/implementation_guide_v2.md:229-231`, `data/implementation_guide_v2.md:2357-2384`; Actual: `src/app/api/router.py:21-51`, `src/app/infra/postgres/repository.py:115-137`, `src/shared/settings.py:10-33`) |
| Webhook subsystem | Kill it entirely in this codebase. | Webhooks make sense in the queued service. They do not belong in a synchronous manual workflow unless you first rebuild job orchestration and delivery guarantees. The current API exposes no webhook routes and the repository has no webhook persistence model. (Guide: `data/implementation_guide_v2.md:224-226`, `data/implementation_guide_v2.md:1895-1923`; Actual: `src/app/api/router.py:21-51`, `src/app/infra/postgres/repository.py:115-137`) |
| Template/locale/rule-pack platform | Kill it entirely in this codebase. | The current architecture is centered on direct per-run config. Keep that model and make it good, or move platform-managed configuration into a separate service implementation. Half-implementing both will be worse than either. (Guide: `data/implementation_guide_v2.md:1746-1810`; Actual: `src/shared/models/instance_config.py:10-15`, `src/suggestion/pipeline.py:90-108`) |
| Full Prometheus/Grafana/Loki observability stack | Kill it entirely in this codebase. | This repo needs correctness and recoverability first. The planned observability stack is operationally meaningful only once there is an actual service to operate, and the current runtime wiring shows no sign of that stack. (Guide: `data/implementation_guide_v2.md:2782-2810`; Actual: `src/app/api/server.py:21-29`, `pyproject.toml:11-22`, `docker-compose.yml:1-20`) |

## §7 — Risk Register

| Severity | Risk | Failure condition | What fails first | Evidence |
|---|---|---|---|---|
| High | Runs get stranded in intermediate states | Any exception during `profile()` after status is set to `PROFILING`, or during `normalize()` after status is set to `NORMALIZING` | The instance row stays in a non-terminal state forever because there is no exception handling that writes `FAILED`, and there is no sweeper | `src/app/bootstrap/orchestrator.py:72-89`, `src/app/bootstrap/orchestrator.py:102-126` |
| High | Bad outputs are published as `READY` | Any dataset with serious quality problems that do not raise Python exceptions | The system still writes artifacts and marks the run `READY` because profiling only emits warnings and there is no decision stage | `src/profiling/issues.py:27-105`, `src/app/bootstrap/orchestrator.py:100-125`, `src/shared/models/instance.py:89-92` |
| High | Excel workloads blow up memory and latency | Large `.xlsx` inputs or many wide sheets | Suggestion loads entire visible sheet into `all_rows`; ingestion buffers every row again before `executemany()` | `src/suggestion/source/excel.py:40-91`, `src/shared/ingestion/excel/loader.py:43-79` |
| High | API clients receive unusable artifact references | Any API-triggered run over a local source | The API returns server-local filesystem paths embedded in `InstanceModel`, which are meaningless to remote clients | `src/app/api/router.py:26-51`, `src/shared/models/normalization.py:8-18`, `src/conversion/artifacts/publish.py:18-36` |
| High | The API has no load-shedding story for real traffic | Concurrent large `profile` or `normalize` requests | API worker threads/processes block on synchronous DuckDB work; there is no auth, rate limiting, queueing, backpressure, or progress fallback | `src/app/api/router.py:26-51`, `src/app/bootstrap/orchestrator.py:67-126`, `src/shared/settings.py:10-33` |
| High | Storage credentials are exposed in-repo | Anyone with repo access or accidental commit propagation | The checked-in `.env` contains live-looking R2 endpoint and credential material | `.env:6-9` |
| Medium | Quality metrics mislead operators | Any consumer trusts `pattern_consistency_ratio` or `decision_thresholds` | `pattern_consistency_ratio` is semantically wrong, and decision thresholds are dead config | `src/profiling/pipeline.py:60-69`, `src/profiling/profiles.py:81-90`, `src/shared/models/operation.py:48-68` |
| Medium | Persistence will become unqueryable and hard to evolve | The moment product asks for run history, issue analytics, or artifact lifecycle reporting | All lifecycle outputs are hidden in JSONB snapshots inside one table with runtime DDL and no migrations | `src/app/infra/postgres/repository.py:36-137`, `src/app/persistence/serialization.py:15-90` |
| Medium | The codebase has no reliable regression net | Any non-trivial refactor or dependency upgrade | Breakage will surface in production/manual use because the current tree has no active tests and at least one helper script is already stale | `pyproject.toml:40-43`, `data/full_data_suggestion_compare.py:37-43` |
| Medium | Source/output backend coupling blocks deployment choices | Local sources that should publish to object storage, or S3 sources that should write locally | Artifact backend is chosen from `source.source_type`, not from an independent output policy | `src/app/bootstrap/conversion.py:43-52`, `src/conversion/artifacts/publish.py:71-79` |

## §8 — Executive Verdict

This codebase is not in a good state relative to the guide. The code is coherent as a small synchronous normalization tool, but it is materially dishonest as an implementation of the specified service: no worker architecture, no 16-stage engine, no decision layer, no failure recovery, no baseline/drift system, no operational controls, and no active test suite. The single most critical thing to address immediately is architectural truthfulness: stop treating this repository as the guide’s service. Either formalize the current smaller architecture and delete the dead service scope from the spec, or build the actual service separately. Continuing with both stories at once will keep producing wrong engineering decisions and unsafe runtime behavior.
