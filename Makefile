SHELL := /bin/bash
.PHONY: release

VERSION := $(shell python3 -c "import json; print(json.load(open('custom_components/kohler_anthem/manifest.json'))['version'])")

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
