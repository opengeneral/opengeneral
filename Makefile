# OpenGeneral developer convenience targets (Linux/macOS).
# For installing a release build, end users use the curl installer (./install.sh);
# these targets are for working from a source checkout.

PYTHON ?= python3
INSTALL_DIR ?= $(HOME)/.local/bin

.DEFAULT_GOAL := help

.PHONY: help install dev test build build-tui install-bin uninstall-bin clean

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

build-tui: ## Build the connection-visualization TUI (Rust) into tui/target/release
	cargo build --release --manifest-path tui/Cargo.toml

install-bin: build build-tui ## Build and install the local binaries onto your PATH
	mkdir -p $(INSTALL_DIR)
	install -m 0755 dist/opengeneral $(INSTALL_DIR)/opengeneral
	install -m 0755 tui/target/release/opengeneral-tui $(INSTALL_DIR)/opengeneral-tui
	@echo "Installed opengeneral and opengeneral-tui to $(INSTALL_DIR)"

uninstall-bin: ## Unregister the daemon and remove the locally-installed binaries
	-$(INSTALL_DIR)/opengeneral daemon uninstall
	rm -f $(INSTALL_DIR)/opengeneral $(INSTALL_DIR)/opengeneral-tui
	@echo "Removed opengeneral and opengeneral-tui from $(INSTALL_DIR)"

clean: ## Remove build artifacts
	rm -rf build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache
	cargo clean --manifest-path tui/Cargo.toml 2>/dev/null || true
