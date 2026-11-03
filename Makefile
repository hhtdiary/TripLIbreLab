# One-command workflows. Run `make help`.
# Needs: python3 (3.10+), node 22 + npm for the docs linters, ruff (pipx run ruff / pip install ruff).
# The iOS app does not exist yet; its targets will be added here when it does (see docs/docs/developer.html).

.PHONY: help fixtures fixtures-check test contract-check lint a11y ci clean

help:            ## list targets
	@grep -E '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-16s %s\n", $$1, $$2}'

fixtures:        ## regenerate fixtures/*.sqlite from tools/triplibre_schema.sql (deterministic; commit the result)
	python3 tools/make_fixtures.py

fixtures-check:  ## fail if fixtures/ differs from what make_fixtures.py produces
	rm -rf .build/fixtures && python3 tools/make_fixtures.py .build/fixtures > /dev/null
	@for f in fixtures/*.sqlite; do cmp -s "$$f" ".build/fixtures/$$(basename $$f)" || { echo "::error::$$f is out of date. Run 'make fixtures' and commit it."; exit 1; }; done
	@echo "fixtures are up to date"

test:            ## Python contract tests (fixtures reproducible, inspector verdicts, sample day shape)
	python3 -m unittest discover -s tools/tests -v

contract-check:  ## run the export inspector on every fixture and print its verdicts
	@for f in fixtures/*.sqlite; do echo "== $$f"; python3 tools/inspect_export.py "$$f" --days; echo "exit=$$?"; done

# npm writes node_modules/.package-lock.json on install, so this reinstalls whenever the lockfile changes.
node_modules/.package-lock.json: package-lock.json
	npm ci

lint: node_modules/.package-lock.json   ## docs JS/CSS/HTML (incl. accessibility rules), Markdown, Python (needs node + ruff)
	npm run lint
	ruff check

a11y: node_modules/.package-lock.json   ## axe-core WCAG 2.1 AA check of every docs page, light + dark (needs node + Chromium)
	npx playwright install chromium
	npm run a11y

ci: lint a11y fixtures-check test contract-check   ## everything GitHub Actions runs

clean:
	rm -rf .build
