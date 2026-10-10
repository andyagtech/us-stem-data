# One entrypoint. If CI and this file diverge, CI is fiction -- the workflow
# calls these same targets rather than repeating their commands.
#
# Why this exists: there were six suites with six different invocations, and
# nobody ran all of them. scripts/check_consistency.py and
# scripts/test_query_page.py were not in CI at all, and the site checks were
# wired with `|| true`, so 120 assertions ran and could never fail a build.

PY := .venv/bin/python

.PHONY: check check-offline check-live site query consistency units chat docs \
        lint-deps verify-deploy help sidebar anchors nav lca anomalies links \
        drill

help:
	@echo "  make check          everything that needs no network or credentials"
	@echo "  make check-live     adds the live-site and live-assistant suites"
	@echo "  make site           site structure, accessibility, published figures"
	@echo "  make query          /query.html and the Parquet exports"
	@echo "  make lca            LCA year coverage, swings, reconciliation"
	@echo "  make links          every catalogued source URL still resolves"
	@echo "  make anomalies      new data anomalies vs the baseline"
	@echo "  make nav            sidebar links and anchor ids (both below)"
	@echo "  make sidebar        every sidebar link, anchor and university"
	@echo "  make anchors        every section addressable from the URL bar"
	@echo "  make drill          the public-sector state drill-down, in a browser"
	@echo "  make consistency    docs, catalog, atomic writes, dependency pins"
	@echo "  make units          pytest tests/ (chat integration is opt-in)"
	@echo "  make chat           chat handler, offline, stubs boto3"
	@echo "  make docs           refill the generated numbers in prose"
	@echo "  make verify-deploy  assert the LIVE site matches what was built"

# The default gate. No network, no AWS, no large data files.
check: consistency site query units chat lca anomalies
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

# The published LCA aggregate, checked from the output side. The guards in
# step3 only run when the parse runs; this runs on every check.
lca:
	$(PY) scripts/check_lca_sanity.py

# Source links, reported but not gating: two federal sites refuse automated
# requests while serving people normally, so a dead-link failure here would
# be wrong more often than right. Run with --strict to gate.
links:
	$(PY) scripts/check_source_links.py

# Fails on anomalies that are NEW since data/anomaly_baseline.json, not on
# the 42 already known -- a check that is red on arrival gets ignored.
anomalies:
	$(PY) scripts/data_anomaly_check.py --check

anchors:
	$(PY) scripts/check_anchor_ids.py

# The one part of the public-sector page that Python cannot test: a reader
# opening an employer row. Kept out of the `check` chain alongside `anchors`,
# because both drive a real browser and `check` is meant to stay fast and
# dependency-free. Run it when the page, states.js or the drill-down JS moves.
drill:
	$(PY) scripts/check_public_sector_drill.py

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

# The pre-share checklist. Runs against the LIVE site, so it goes AFTER a
# deploy, not before: `make units` and check_consistency compare the repo
# with itself, this asks whether what a reader opens actually works.
preflight:
	.venv/bin/python scripts/preflight.py
