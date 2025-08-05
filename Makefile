PYTHON ?= python
VENV ?= .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
PIP := $(VENV_PYTHON) -m pip
DEPS_STAMP := $(VENV)/.deps-installed
CSV ?= data/prod_like_100k.csv
SUGGESTION_JSON ?= suggestion.json
NORMALIZE_MODE ?= APPLY
NORMALIZATION_JSON ?= normalization.json

.PHONY: first bootstrap install test type lint format check db-up db-down api upload normalize clean-venv

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

type: $(DEPS_STAMP)
	$(VENV_BIN)/mypy src/

lint: $(DEPS_STAMP)
	$(VENV_BIN)/ruff check .
	$(VENV_BIN)/mypy src/

format: $(DEPS_STAMP)
	$(VENV_BIN)/ruff format .

check: lint type test

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

api: | $(VENV_PYTHON)
	$(VENV_BIN)/uvicorn app.api.app:app --host 0.0.0.0 --port 8000

upload: | $(VENV_PYTHON)
	$(VENV_PYTHON) upload.py $(CSV) $(SUGGESTION_JSON)

normalize: | $(VENV_PYTHON)
	$(VENV_PYTHON) scripts/normalize.py $(SUGGESTION_JSON) $(NORMALIZE_MODE) $(NORMALIZATION_JSON)

clean-venv:
	rm -rf $(VENV)
