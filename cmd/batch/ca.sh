#!/usr/bin/env bash
# ca.sh — git commit all (run from PROJECT_ROOT)
set -euo pipefail
cd "$(dirname "$0")/.."
rm -f .git/index.lock
git add -A
git commit -m "feat: Phase 0 CLI skeleton — init/log/status/brief/ask/recall working

- pyproject.toml (setuptools, Python 3.10+, lode-vein entry point)
- src/vein/core/models.py — Entry dataclass, YAML frontmatter I/O
- src/vein/core/store.py — .vein/ path resolution, read/write, grep search
- src/vein/core/config.py — ai_providers.yaml + .env loader
- src/vein/core/polish.py — ollama polish pipeline + interactive confirm
- src/vein/core/brief.py — rule-based brief generation (no LLM required)
- src/vein/commands/ — init, log, status, brief, ask, recall
- config/ai_providers.yaml — Claude/Gemini/OpenAI/local routing
- .env.example, .gitignore
- cmd/ — cmd_vein_entry.csv/py, run_batch.py, batch scripts
- docs/data_format.md, docs_cloudflare/why.md
- docs/decisions.md D-001~D-020"
