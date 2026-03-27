# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
make first              # Create venv and install all dependencies (first time)
make install            # Ensure dependencies are up to date

# Development
make test               # Run pytest suite
make lint               # ruff check + mypy src/
make format             # ruff format .
make check              # lint + test

# Database
make db-up              # Start PostgreSQL (docker compose, port 5438)
make db-down            # Stop PostgreSQL

# API server
make api                # Start FastAPI on port 8000

# Run a single test
.venv/bin/pytest tests/unit/test_fingerprint.py -q
.venv/bin/pytest tests/unit/stages/test_cell_normalization.py::TestName -q
```

## Normalization lifecycle (CLI)

```bash
make suggest csv my_file NAME=my_run        # Infer config from CSV
make suggest json my_file NAME=my_run
make suggest excel my_file NAME=my_run
make confirm INSTANCE=<uuid> CONFIRMED=config.json NAME=my_run
make profile INSTANCE=<uuid> NAME=my_run
make convert INSTANCE=<uuid> NAME=my_run MODE=APPLY
```

Files are resolved under `data/`. The stem alone is accepted — extension is inferred from the format arg.

## Architecture

The pipeline has four sequential phases: **suggest → confirm → profile → convert**.

`MainOrchestrator` (`app/bootstrap/orchestrator.py`) owns the lifecycle. It enforces state transitions via `InstanceStatus`, persists every step to PostgreSQL via `PostgresRunRepository`, and delegates to three domain services: `SuggestionService`, `ProfilingService`, `ConversionService`.

Each domain pipeline lives in its own top-level package under `src/`:

| Package | Role |
|---|---|
| `suggestion/` | Infer source format + per-column `ColumnConfig` from sampled rows |
| `profiling/` | Full-dataset analysis using DuckDB; produces `ProfilingOutput` |
| `conversion/` | Apply normalization rules via DuckDB SQL; produces `NormalizationOutput` |
| `shared/` | Models, DuckDB utilities, ingestion, column parsing — no pipeline logic |

**`ConfirmedConfig`** is the central data contract. It carries `source_format`, `column_config` (dict of column name → `ColumnConfig`), and `operation_config`. Every downstream phase is driven entirely by this config — no hardcoded type assumptions elsewhere.

**`build_value_candidate_expr(value_expr, config)`** in `shared/column_parsing/normalizer.py` is the single canonical preprocessing function. Both profiling and conversion call it; neither reimplements it.

### Model hierarchy (`shared/models/`)

`ColumnConfig` is a discriminated union of concrete types organised under a base class hierarchy in `shared/models/column/base.py`:
- `NumericColumnConfig` → `DecimalFamilyColumnConfig` → `SignedFamilyColumnConfig`

Profile types follow the same pattern in `shared/models/profiling/base.py`.

Repeated `isinstance` unions across files are always promoted to base classes here — local type aliases are not used.

## File structure rules

**Location expresses responsibility, not data ancestry.** A module belongs where its *role* is, not where its input data came from. If a module is called directly from `pipeline.py`, it lives at the pipeline package root alongside `pipeline.py`.

- `pipeline.py` files are orchestrators only — no business logic, no inline helpers.
- A single file becomes a package when it has distinct internal sections with independent imports and clear identity.
- Three nesting levels is the default; four is acceptable with justification. Five requires explicit sign-off.
- Module names are nouns. Generic names (`utils.py`, `models.py`) are not used — name the file after what it contains.
- No redundant prefixes: `source_stats.py` inside `suggestion/` → `stats.py`.
- `__init__.py` re-exports only a small, intentional, stable surface. A name exported from `__init__.py` must be imported *only* from the package root, never mixed with direct-module imports for the same symbol.

## Environment

Copy `.env.example` to `.env`. PostgreSQL DSN defaults to `postgresql://normalize:normalize@localhost:5438/normalize`. DuckDB runs in-process. S3 credentials are optional (Cloudflare R2).
