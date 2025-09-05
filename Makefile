PYTHON ?= python
VENV ?= .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
PIP := $(VENV_PYTHON) -m pip
DEPS_STAMP := $(VENV)/.deps-installed

# ── lifecycle args ────────────────────────────────────────────────────────────
FILE      ?= prod_like_10k.csv
INSTANCE  ?=
CONFIRMED ?=
MODE      ?= APPLY
NAME      ?= $(shell date +%Y-%m-%dT%H-%M-%S)

.PHONY: first bootstrap install test lint format check db-up db-down api \
        suggest confirm profile convert clean-venv

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
#   make suggest FILE=prod_like_10k.csv NAME=my_run
#   make confirm INSTANCE=<uuid> CONFIRMED=my_confirmed.json NAME=my_run
#   make profile INSTANCE=<uuid> NAME=my_run
#   make convert INSTANCE=<uuid> NAME=my_run MODE=APPLY

suggest: | $(VENV_PYTHON)
	$(VENV_PYTHON) main.py suggest $(FILE) $(NAME)

confirm: | $(VENV_PYTHON)
	$(VENV_PYTHON) main.py confirm $(INSTANCE) $(CONFIRMED) $(NAME)

profile: | $(VENV_PYTHON)
	$(VENV_PYTHON) main.py profile $(INSTANCE) $(NAME)

convert: | $(VENV_PYTHON)
	$(VENV_PYTHON) main.py convert $(INSTANCE) $(NAME) $(MODE)

clean-venv:
	rm -rf $(VENV)
