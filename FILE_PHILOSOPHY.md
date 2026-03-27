# File Philosophy

This document is the single source of truth for file structure, naming, and module
organisation across this codebase. Every structural decision must be justified against
the principles here.

---

## Core principle: location expresses responsibility, not data ancestry

A file belongs where its **responsibility** lives, not where its **input data** came from.

> Just because a module works on source data does not mean it belongs in `source/`.
> Just because a module produces column configs does not mean it belongs in `column_config/`.

Ask: **what does this module do, not what does it consume.**

### Example that settled this

`stats.py` computes row counts from a `SourceReading` object. A naive reading says
"it touches source data → put it in `source/`." The right reading is: it runs as
Track A of the suggestion pipeline in a `ThreadPoolExecutor` — it is a **pipeline-level
computation** that happens to consume source data. It belongs at `suggestion/` root,
not inside `source/`.

Same for `display.py`: it extracts display values from `inference_rows`. The data comes
from source reading, but the operation is a pipeline-level concern called from
`pipeline.py`. Root is right. `source/` would be wrong.

**Rule:** if it is called directly from `pipeline.py` and its role is a phase or track
of the pipeline, it lives at the package root alongside `pipeline.py`.

---

## Folder responsibility must be stated in one sentence

Before creating or keeping a folder, write one sentence that captures its sole
responsibility. If you cannot write one sentence without using "and", split the folder
or reconsider.

| Folder | Responsibility |
|---|---|
| `source/` | Detect file format, parse rows, return a `SourceReading`. |
| `column_config/` | Infer a `ColumnConfig` from sampled string values. |
| `column_config/numeric/` | Score and decide numeric type fits from raw tokens. |
| `shared/models/column/` | Define column configuration types and their hierarchy. |
| `shared/models/profiling/` | Define profiling output types and their hierarchy. |
| `shared/column_parsing/` | Build config-driven SQL preprocessing expressions. |
| `shared/ingestion/` | Resolve ingestion source and run DuckDB ingestion. |
| `profiling/column_stats/` | Compute per-type column profiles from a live DuckDB table. |

If files inside a folder stop fitting that sentence, they are in the wrong place.

---

## Files at the pipeline root

Files that sit alongside `pipeline.py` at the package root are **pipeline-level
concerns**: they are either called directly from `pipeline.py` or they define the
contracts that `pipeline.py` produces. They do not belong in sub-packages even if
their inputs originate from a sub-package.

Examples at `suggestion/`:
- `pipeline.py` — orchestrator
- `null_tokens.py` — infers null tokens (Phase 2 of suggestion pipeline)
- `stats.py` — computes row/null counts (Track A, called from pipeline)
- `display.py` — extracts display values (Track B, called from pipeline)
- `constants.py` — all pipeline-level constants

---

## Naming conventions

### Naming pattern: nouns, not verbs

Module names are nouns. A module named after an action (`read.py`) is harder to reason
about than one named after the thing it provides (`reader.py`). All sibling modules
within a package must follow the same pattern.

- `read.py` → `reader.py`
- `utils.py` → name it after what it actually contains (`heuristics.py`)

### No redundant prefixes

A prefix that repeats the folder name adds noise and signals the file was put in the
wrong place — or was named before the folder existed.

- `source_stats.py` inside `suggestion/` → prefix `source_` was a location smell;
  rename to `stats.py`
- `column_display.py` → `column_` was wrong context; rename to `display.py`

**Rule:** if removing the prefix still leaves a clear, unambiguous name, remove it.

### Specific beats generic

Generic names (`utils.py`, `models.py`, `helpers.py`) force a reader to open the file
to know what's inside. Name the file after what it actually contains.

- `utils.py` with one function `looks_numeric` → `heuristics.py`
- `models.py` containing exclusively numeric inference dataclasses → move to
  `numeric/models.py`

### Plural vs singular

Use singular when the module defines or produces one thing; use plural only when the
module is genuinely a collection of independent items.

---

## Single file vs sub-package

A module becomes a sub-package when it has **distinct internal sections that each have
their own imports, logic, and clear identity**. The test is whether you would write a
section-divider comment like:

```python
# ---------------------------------------------------------------------------
# Section name
# ---------------------------------------------------------------------------
```

If yes, each section is a module waiting to be born.

A module stays a single file when its internals are tightly coupled implementation
details of one public function — moving them out would create private modules that
have no independent value.

### Settled examples

| Was | Became | Why |
|---|---|---|
| `shared/models/column.py` | `shared/models/column/` package | Base classes and concrete types are distinct sections with independent imports |
| `shared/models/profiling.py` | `shared/models/profiling/` package | Base classes, profiles, and output models are three independent concerns |
| `shared/column_parsing/normalizer.py` | + `_currency.py`, `_markers.py` siblings | Currency stripping and marker helpers are independent SQL utility groups |
| `suggestion/column_config/inference.py` | + `boolean.py`, `date.py`, `numeric/decision.py` | Per-type inference logic has no shared state — each type is its own module |

### The `__init__.py` contract

`__init__.py` is an optional package API, not an automatic re-export bucket.

Use `__init__.py` re-exports only when the package has a **small, intentional, stable
surface** and the package root is meant to be the canonical access point for those
names.

Once a name is exported from `__init__.py`, the package root becomes the **only
acceptable import path** for that name across the codebase. Do not mix:
- `from pkg import Name`
- `from pkg.module import Name`
for the same symbol. That is a red flag. It means the boundary is undefined in
practice even if it exists on paper.

If callers should import a name from the concrete owning module, do **not** re-export
it from `__init__.py`. A package must choose one canonical path per exported symbol.

Concrete-module imports remain correct for names that are **not** exported from
`__init__.py`. Path length is a tiebreaker, not the governing rule. Prefer the shorter
path only when it preserves a clear ownership boundary.

Do **not** add re-exports when they:
- create import cycles
- force unrelated modules to load together
- make it harder to see where a name is actually defined
- expose unstable implementation details as package API

When a single file becomes a package, preserving old import paths is optional, not
mandatory. Keep the old path only if it is a deliberate public API worth preserving.
If that API is preserved through `__init__.py`, callers must use it consistently.
Otherwise, update imports to the new concrete modules.

---

## Type hierarchy over local union types

Repeating a union of types in multiple files is a signal that the union should be a
base class in `shared/models/`.

```python
# Smell — same union copy-pasted in 4 files:
isinstance(config, DecimalColumnConfig | PercentageColumnConfig | SignedColumnConfig | ...)

# Fix — one base class in shared/models/column/base.py:
isinstance(config, DecimalFamilyColumnConfig)
```

**Rule:** if the same set of types appears in an `isinstance` check in more than one
file, it must become a base class. Local type aliases (`_SomeName = A | B | C`) are
always wrong — they are private copies of a shared concept.

### Settled hierarchy

**Config base classes** (`shared/models/column/base.py`):
- `NumericColumnConfig` — `thousand_separator`, `grouping_style`
  - `DecimalFamilyColumnConfig` — adds `decimal_separator`, `allow_leading_decimal_point`
    - `SignedFamilyColumnConfig` — adds sign marker fields

**Profile base classes** (`shared/models/profiling/base.py`):
- `ParseMatchProfile` — `parse_match_count`, `parse_match_ratio`
  - `SeparatorMismatchProfile` — adds swap detection fields
- `SymbolDistributionProfile` — `symbol_distribution`, `dominant_symbol`, etc.

---

## Nesting depth

Three levels is the default ceiling. Four levels is acceptable when the inner package
has a clear, single responsibility that is legitimately separate from its parent.

`suggestion/column_config/numeric/` is four levels deep and correct:
numeric inference is a self-contained domain with its own models, parsing, scoring, and
decision logic.

Creating a fifth level requires explicit justification.

---

## Pipeline files are orchestrators, not logic containers

`pipeline.py` files call other modules. They do not contain:
- Business logic (conditions, calculations)
- Private helpers
- Inline dataclasses

If logic appears in `pipeline.py`, it belongs in a dedicated module. The pipeline
reads like a phase list; each phase delegates entirely to a named function from a
named module.

---

## Config-driven code

`ColumnConfig` is the single source of truth. Neither profiling nor conversion may
contain hardcoded assumptions about type behaviour that are not derived from the config.

The canonical preprocessing function is `build_value_candidate_expr(value_expr, config)`
in `shared/column_parsing/normalizer.py`. Both profiling and conversion call this
function — they do not reimplement it.
