#!/usr/bin/env bash
# ca.sh — git commit all (run from PROJECT_ROOT)
set -euo pipefail
cd "$(dirname "$0")/../.."
rm -f .git/index.lock
git add -A
git commit -m "docs: usage guide, test docs, tests/README — Phase 0.5 complete

New docs:
- docs/usage.md            — complete CLI usage guide with flowcharts
- tests/README.md          — test suite overview + rules for new feature tests
- tests/test_models.md     — Entry model doc + Mermaid flowcharts
- tests/test_store.md      — VeinStore I/O doc + Mermaid flowcharts

Tests: 30 passed (pytest tests/ -q)"
