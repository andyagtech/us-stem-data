# One entrypoint. If CI and this file diverge, CI is fiction -- the workflow
# calls these same targets rather than repeating their commands.
#
# Why this exists: there were six suites with six different invocations, and
# nobody ran all of them. scripts/check_consistency.py and
# scripts/test_query_page.py were not in CI at all, and the site checks were
# wired with `|| true`, so 120 assertions ran and could never fail a build.

PY := .venv/bin/python

.PHONY: check check-offline check-live site query consistency units chat docs \
        lint-deps verify-deploy help sidebar anchors nav

help:
	@echo "  make check          everything that needs no network or credentials"
	@echo "  make check-live     adds the live-site and live-assistant suites"
	@echo "  make site           site structure, accessibility, published figures"
	@echo "  make query          /query.html and the Parquet exports"
	@echo "  make nav            sidebar links and anchor ids (both below)"
	@echo "  make sidebar        every sidebar link, anchor and university"
	@echo "  make anchors        every section addressable from the URL bar"
	@echo "  make consistency    docs, catalog, atomic writes, dependency pins"
	@echo "  make units          pytest tests/ (chat integration is opt-in)"
	@echo "  make chat           chat handler, offline, stubs boto3"
	@echo "  make docs           refill the generated numbers in prose"
	@echo "  make verify-deploy  assert the LIVE site matches what was built"

# The default gate. No network, no AWS, no large data files.
check: consistency site query units chat
	@echo ""
	@echo "  all offline checks passed"

check-offline: check

# Adds the suites that call the live site and the deployed assistant.
check-live: check
	$(PY) scripts/test_site.py
	$(PY) scripts/test_query_page.py
	$(PY) scripts/test_chat_answers.py
	@echo ""
	@echo "  live checks passed"

site:
	$(PY) scripts/test_site.py --offline

# Navigation checks. Kept out of the `check` chain for now: `sidebar` reports
# six pages that render no sidebar at all, which is a design question rather
# than a regression, and a target that is expected to fail teaches people to
# ignore it.
sidebar:
	$(PY) scripts/check_sidebar_links.py

anchors:
	$(PY) scripts/check_anchor_ids.py

nav: sidebar anchors

query:
	$(PY) scripts/test_query_page.py --local

consistency:
	$(PY) scripts/check_consistency.py

units:
	$(PY) -m pytest tests/ -q

chat:
	cd cloud/chat && ../../$(PY) test_local.py

docs:
	$(PY) scripts/sync_docs.py --write

lint-deps:
	$(PY) scripts/check_consistency.py --quiet | grep -iE "pin|version|lockfile" || true

# Post-deploy assertion. A deploy exiting 0 is not evidence it shipped: on
# 2026-08-21 one exited 0 having uploaded no JSON at all.
verify-deploy:
	$(PY) scripts/verify_deploy.py
