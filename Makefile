PYTHON ?= python
VENV ?= .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
PIP := $(VENV_PYTHON) -m pip
DEPS_STAMP := $(VENV)/.deps-installed

# ── lifecycle args ────────────────────────────────────────────────────────────
INSTANCE  ?=
CONFIRMED ?=
MODE      ?= APPLY
NAME      ?= $(shell date +%Y-%m-%dT%H-%M-%S)

SUGGEST_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))

.PHONY: first bootstrap install test lint format check db-up db-down api \
        suggest confirm profile convert clean-venv

ifeq ($(firstword $(MAKECMDGOALS)),suggest)
ifneq ($(strip $(SUGGEST_ARGS)),)
.PHONY: $(SUGGEST_ARGS)
$(SUGGEST_ARGS):
	@:
endif
endif

$(VENV_PYTHON):
	$(PYTHON) -m venv $(VENV)

$(DEPS_STAMP): pyproject.toml Makefile | $(VENV_PYTHON)
	$(PIP) install -U pip setuptools wheel
	$(PIP) install -U -e ".[dev]"
	touch $(DEPS_STAMP)

first: $(DEPS_STAMP)
	@echo "Environment ready at $(VENV)."
	@echo "Activate with: source $(VENV_BIN)/activate"

bootstrap: first

install: $(DEPS_STAMP)

test: $(DEPS_STAMP)
	$(VENV_BIN)/pytest -q

lint: $(DEPS_STAMP)
	$(VENV_BIN)/ruff check .
	$(VENV_BIN)/mypy src/

format: $(DEPS_STAMP)
	$(VENV_BIN)/ruff format .

check: lint test

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

api: | $(VENV_PYTHON)
	$(VENV_BIN)/uvicorn app.api.server:app --host 0.0.0.0 --port 8000

# ── lifecycle commands ────────────────────────────────────────────────────────
# Usage:
#   make suggest csv prod_like_10k NAME=my_run
#   make suggest json prod_like_10k NAME=my_run
#   make suggest excel workbook NAME=my_run
#   make confirm INSTANCE=<uuid> CONFIRMED=my_confirmed.json NAME=my_run
#   make profile INSTANCE=<uuid> NAME=my_run
#   make convert INSTANCE=<uuid> NAME=my_run MODE=APPLY

suggest: | $(VENV_PYTHON)
	@set -- $(SUGGEST_ARGS); \
	if [ "$$#" -ne 2 ]; then \
		echo "Error: use: make suggest <csv|json|excel> <file_stem_or_filename> NAME=..." >&2; \
		exit 1; \
	fi; \
	format="$$1"; \
	filename="$$2"; \
	case "$$format" in \
		csv) expected_ext=".csv" ;; \
		json) expected_ext=".json" ;; \
		excel) expected_ext=".xlsx" ;; \
		*) echo "Error: suggest format must be one of: csv, json, excel" >&2; exit 1 ;; \
	esac; \
	case "$$filename" in \
		*.*) case "$$filename" in \
			*$$expected_ext) ;; \
			*) echo "Error: file $$filename does not match format $$format" >&2; exit 1 ;; \
		esac ;; \
		*) filename="$$filename$$expected_ext" ;; \
	esac; \
	$(VENV_PYTHON) main.py suggest "$$filename" "$(NAME)"

confirm: | $(VENV_PYTHON)
	$(VENV_PYTHON) main.py confirm $(INSTANCE) $(CONFIRMED) $(NAME)

profile: | $(VENV_PYTHON)
	$(VENV_PYTHON) main.py profile $(INSTANCE) $(NAME)

convert: | $(VENV_PYTHON)
	$(VENV_PYTHON) main.py convert $(INSTANCE) $(NAME) $(MODE)

clean-venv:
	rm -rf $(VENV)
