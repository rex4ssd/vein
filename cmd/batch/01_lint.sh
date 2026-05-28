#!/usr/bin/env bash
# 01_lint.sh — ruff check (run from PROJECT_ROOT)
set -euo pipefail
echo "[01] ruff check src/"
cd "${VEIN_PROJECT_ROOT:-.}"
if [ -d "src" ]; then
    ruff check src/ || exit 1
else
    echo "  src/ not found — skip (Phase 0, no code yet)"
fi
echo "[01] lint OK"
