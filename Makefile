PYTHON ?= python
VENV ?= .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
PIP := $(VENV_PYTHON) -m pip
DEPS_STAMP := $(VENV)/.deps-installed

.PHONY: first bootstrap install test type lint format check run-runner clean-venv

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

format: $(DEPS_STAMP)
	$(VENV_BIN)/ruff format .

check: lint type test

run-runner: | $(VENV_PYTHON)
	$(VENV_PYTHON) runner.py

clean-venv:
	rm -rf $(VENV)
