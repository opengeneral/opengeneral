# OpenGeneral developer convenience targets (Linux/macOS).
# These wrap the same commands the packaging scripts and CI use, so there is one
# source of truth. On Windows, use the packaging\*.ps1 scripts directly.

PYTHON ?= python3

.DEFAULT_GOAL := help

.PHONY: help install dev test build install-bin uninstall-bin clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*## "} {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install the package with runtime deps (editable)
	$(PYTHON) -m pip install -e .

dev: ## Install with dev + build extras (editable)
	$(PYTHON) -m pip install -e '.[dev,build]'

test: ## Run the test suite
	$(PYTHON) -m pytest -q

build: ## Build the standalone binary into dist/ (PyInstaller)
	PYTHON=$(PYTHON) ./packaging/build.sh

install-bin: ## Build (if needed) and install the binary onto your PATH
	./packaging/install.sh

uninstall-bin: ## Remove the installed binary and unregister the daemon
	./packaging/uninstall.sh

clean: ## Remove build artifacts
	rm -rf build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache
