#!/usr/bin/env bash
# 02_test.sh — pytest
set -euo pipefail
echo "[02] pytest -q"
cd "${VEIN_PROJECT_ROOT:-.}"
if [ -d "tests" ] || find . -name "test_*.py" -maxdepth 3 | grep -q .; then
    pytest -q || exit 1
else
    echo "  no tests found — skip (Phase 0)"
fi
echo "[02] tests OK"
