#!/usr/bin/env bash
# clean_test_entries.sh — 刪除 smoke test 產生的測試 entries
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Removing smoke test entries..."
rm -fv .vein/decisions/20260528-*.md
rm -fv .vein/decisions/20260527-165106-*.md
rm -fv .vein/lore/20260527-165114-*.md
rm -fv .vein/pitfalls/20260527-165113-*.md
rm -fv .vein/BRIEF.md

echo "Done. Current state:"
vein status
