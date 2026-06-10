# OpenGeneral developer convenience targets (Linux/macOS).
# For installing a release build, end users use the curl installer (./install.sh);
# these targets are for working from a source checkout.

PYTHON ?= python3
INSTALL_DIR ?= $(HOME)/.local/bin

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

install-bin: build ## Build and install the local binary onto your PATH
	mkdir -p $(INSTALL_DIR)
	install -m 0755 dist/opengeneral $(INSTALL_DIR)/opengeneral
	@echo "Installed dist/opengeneral to $(INSTALL_DIR)/opengeneral"

uninstall-bin: ## Unregister the daemon and remove the locally-installed binary
	-$(INSTALL_DIR)/opengeneral daemon uninstall
	rm -f $(INSTALL_DIR)/opengeneral
	@echo "Removed $(INSTALL_DIR)/opengeneral"

clean: ## Remove build artifacts
	rm -rf build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache
