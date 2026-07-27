.DEFAULT_GOAL := help

# ── Colours ───────────────────────────────────────────────────────────────────
CYAN  := \033[36m
RESET := \033[0m

.PHONY: help clean install requirements lint format typecheck check-docs check-config validate-config smoke-test

help: ## Show this help and exit
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-16s$(RESET) %s\n", $$1, $$2}'

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean: ## Remove cache and generated files (runs automatically before each commit)
	find . -type d -name "__pycache__" ! -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
	find . \( -name "*.pyc" -o -name "*.pyo" -o -name "*.pyd" \) ! -path "./.git/*" -delete 2>/dev/null || true
	find . -maxdepth 4 -name "*.nfo" ! -name "example_output.nfo" ! -path "./.git/*" -delete 2>/dev/null || true
	find . -maxdepth 4 \( -name "*-clearlogo.png" -o -name "*.gif" \) ! -path "./.git/*" -delete 2>/dev/null || true
	rm -rf .ruff_cache .pyright 2>/dev/null || true
	@echo "Clean done."

# ── Setup ─────────────────────────────────────────────────────────────────────
install: ## Install all Python dependencies (uv preferred, pip as fallback)
	uv sync || pip install -r requirements.txt

requirements: ## Regenerate requirements.txt from uv.lock (for pip compatibility)
	uv export --no-hashes --no-emit-project -o requirements.txt
	@echo "requirements.txt updated."

# ── Code quality ──────────────────────────────────────────────────────────────
lint: ## Run ruff linter across all Python files
	ruff check .

format: ## Auto-fix and format code with ruff
	ruff check --fix .
	ruff format .

typecheck: ## Run pyright type checker
	pyright

# ── Documentation ─────────────────────────────────────────────────────────────
check-docs: ## Check all Markdown files for broken links and missing file refs
	python scripts/check_md.py

# ── Smoke tests ───────────────────────────────────────────────────────────────
smoke-test: ## Quick functional test of all three tools (no video file required)
	@echo "--- NFO Converter ---"
	python stash_to_nfo.py --help > /dev/null && echo "  stash_to_nfo.py OK"
	@echo "--- Video Gallery ---"
	python video_gallery.py --help > /dev/null && echo "  video_gallery.py OK"
	@echo "--- ClearLogo ---"
	python clearlogo.py "Smoke Test Title" --font bebas -o /tmp/_smoke_clearlogo.png && \
		echo "  clearlogo.py OK" && rm -f /tmp/_smoke_clearlogo.png
	@echo "--- NFO from sample JSON ---"
	python stash_to_nfo.py attached_assets/Chef-At-Home.*.json /tmp/_smoke.nfo --pretty && \
		echo "  NFO conversion OK" && rm -f /tmp/_smoke.nfo
	@echo "All smoke tests passed."

# ── Config checks ─────────────────────────────────────────────────────────────
check-config: ## Verify every CLI option is covered by the config system
	python scripts/check_config_coverage.py

validate-config: ## Validate a filled-in config file (FILE=path, default stash-tools.toml)
	python scripts/validate_config.py $(FILE)
