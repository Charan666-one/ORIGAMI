.PHONY: install dev test lint format

PKGS = core engines skills adapters agents interfaces storage

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest

lint:
	pylint $(PKGS)

format:
	black $(PKGS) tests
