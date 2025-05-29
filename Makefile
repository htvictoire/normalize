PYTHON ?= python

.PHONY: bootstrap install test type lint format check

bootstrap:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && python -m pip install -U pip setuptools wheel
	. .venv/bin/activate && python -m pip install -U -e ".[dev]"

install:
	$(PYTHON) -m pip install -U -e ".[dev]"

test:
	pytest -q

type:
	mypy src/

lint:
	ruff check .

format:
	ruff format .

check: lint type test
