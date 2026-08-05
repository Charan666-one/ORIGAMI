.PHONY: venv install dev test lint format

PKGS = core engines skills adapters agents interfaces storage
# compat editable mode uses a plain .pth (repo root on sys.path) instead of the
# setuptools MAPPING finder, which is unreliable with homebrew python on macOS.
EDITABLE = --config-settings editable_mode=compat

# Durable venv rebuild: --copies insulates from homebrew python symlink churn
# that otherwise breaks the venv on `brew upgrade`. Use this if the `origami`
# command ever raises `ModuleNotFoundError: interfaces`.
venv:
	rm -rf .venv
	python3.11 -m venv --copies .venv
	.venv/bin/pip install -q --upgrade pip
	.venv/bin/pip install -e ".[dev]" $(EDITABLE)

install:
	pip install -e . $(EDITABLE)

dev:
	pip install -e ".[dev]" $(EDITABLE)

test:
	pytest

lint:
	pylint $(PKGS)

format:
	black $(PKGS) tests
