#!/usr/bin/env bash
# ca.sh — git commit all (run from PROJECT_ROOT)
set -euo pipefail
cd "$(dirname "$0")/../.."
rm -f .git/index.lock
git add -A
git commit -m "feat: sunnywalker — multi-agent workflow runner (D-022)

vein walk init / run / status / step / reset

Core:
- src/vein/core/workflow.py   WorkflowRunner state machine
                               StepDef (on_pass/on_fail routing)
                               WalkerState persisted to .vein/WALKER.json
- src/vein/commands/walk.py   vein walk subcommand group
- sunnywalker.yaml template   code → validate → report → review → commit

Template scripts (shell/sunnywalker/):
  b_validate.sh  — pytest / cargo check / tsc (edit for your project)
  c_report.py    — auto report from vein entries + log to .vein/
  d_review.py    — ollama reads vein entries → VERDICT: PASS/FAIL
  e_ca.sh        — git commit with cycle info

on_fail routing: stop | skip | retry:N | goto:<step> | ai_decide
Templates: --template default | python | rust | tauri

Docs:
- docs/sunnywalker.md         design + usage guide
- docs/decisions.md D-022     decision record
- .vein/.gitignore            added WALKER.json

Tests: 30 passed (pytest tests/ -q)"
