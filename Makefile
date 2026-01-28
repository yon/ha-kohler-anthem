SHELL := /bin/bash
.PHONY: help venv lint format check clean release bump-patch bump-minor bump-major

COMPONENT_DIR := custom_components/kohler_anthem
MANIFEST := $(COMPONENT_DIR)/manifest.json
VERSION := $(shell python3 -c "import json; print(json.load(open('$(MANIFEST)'))['version'])")
VENV := .venv
RUFF := $(VENV)/bin/ruff

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Development:"
	@echo "  venv        Create venv and install dev tools"
	@echo "  lint        Run ruff linter"
	@echo "  format      Format code with ruff"
	@echo "  check       Run all checks (lint)"
	@echo "  clean       Remove cache files"
	@echo ""
	@echo "Versioning:"
	@echo "  bump-patch  Bump patch version (0.0.X)"
	@echo "  bump-minor  Bump minor version (0.X.0)"
	@echo "  bump-major  Bump major version (X.0.0)"
	@echo ""
	@echo "Release:"
	@echo "  release     Create GitHub release (requires COMMIT=<hash>)"
	@echo ""
	@echo "Current version: $(VERSION)"

$(VENV)/bin/ruff:
	@python3 -m venv $(VENV)
	@$(VENV)/bin/pip install --quiet ruff
	@echo "venv created with ruff installed"

venv: $(VENV)/bin/ruff

lint: $(VENV)/bin/ruff
	@$(RUFF) check $(COMPONENT_DIR)

format: $(VENV)/bin/ruff
	@$(RUFF) format $(COMPONENT_DIR)
	@$(RUFF) check --fix $(COMPONENT_DIR)

check: lint

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

bump-patch:
	@python3 -c "import json; \
		m = json.load(open('$(MANIFEST)')); \
		v = m['version'].split('.'); \
		v[2] = str(int(v[2]) + 1); \
		m['version'] = '.'.join(v); \
		json.dump(m, open('$(MANIFEST)', 'w'), indent=2); \
		print(f\"Version bumped to {m['version']}\")"

bump-minor:
	@python3 -c "import json; \
		m = json.load(open('$(MANIFEST)')); \
		v = m['version'].split('.'); \
		v[1] = str(int(v[1]) + 1); \
		v[2] = '0'; \
		m['version'] = '.'.join(v); \
		json.dump(m, open('$(MANIFEST)', 'w'), indent=2); \
		print(f\"Version bumped to {m['version']}\")"

bump-major:
	@python3 -c "import json; \
		m = json.load(open('$(MANIFEST)')); \
		v = m['version'].split('.'); \
		v[0] = str(int(v[0]) + 1); \
		v[1] = '0'; \
		v[2] = '0'; \
		m['version'] = '.'.join(v); \
		json.dump(m, open('$(MANIFEST)', 'w'), indent=2); \
		print(f\"Version bumped to {m['version']}\")"

release:
ifndef COMMIT
	$(error Usage: make release COMMIT=<git-hash>)
endif
	@git cat-file -e $(COMMIT) 2>/dev/null || (echo "ERROR: commit $(COMMIT) not found" && exit 1)
	@if git rev-parse "v$(VERSION)" >/dev/null 2>&1; then \
		echo "ERROR: tag v$(VERSION) already exists"; \
		exit 1; \
	fi
	@echo "Creating GitHub release v$(VERSION) at $(COMMIT)..."
	@git tag -a "v$(VERSION)" $(COMMIT) -m "Release v$(VERSION)"
	@git push origin "v$(VERSION)"
	@gh release create "v$(VERSION)" \
		--title "v$(VERSION)" \
		--notes "Kohler Anthem HACS Integration v$(VERSION)" \
		--latest
	@echo "Release: https://github.com/yon/ha-kohler-anthem/releases/tag/v$(VERSION)"
