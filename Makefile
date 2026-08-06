.PHONY: venv install dev reinstall test lint format

PKGS = core engines skills adapters agents interfaces storage

# This machine's homebrew python has an unreliable `site` (it intermittently
# fails to process .pth files), so BOTH setuptools editable modes break the
# `origami` command with `ModuleNotFoundError: interfaces`. We therefore install
# NON-editable: packages are copied into site-packages and found by normal import,
# with no .pth dependency. Trade-off: after editing source, run `make reinstall`.

# Durable venv rebuild: --copies also insulates from homebrew python symlink churn
# that breaks a symlinked venv on `brew upgrade`.
venv:
	rm -rf .venv
	python3.11 -m venv --copies .venv
	.venv/bin/pip install -q --upgrade pip
	.venv/bin/pip install ".[dev]"

install:
	pip install .

dev:
	pip install ".[dev]"

# Fast path after editing source (non-editable install needs a refresh to see edits)
reinstall:
	pip install --force-reinstall --no-deps -q .

test:
	pytest

lint:
	pylint $(PKGS)

format:
	black $(PKGS) tests
