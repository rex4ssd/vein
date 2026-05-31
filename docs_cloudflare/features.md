# Features

## Core CLI

```bash
vein init                          # Initialize .vein/ in current repo
vein log decision "why X not Y"    # Capture an architectural decision
vein log lore "API quirk..."       # Capture debug lore / workaround
vein log pitfall "don't do X..."   # Capture a pitfall

vein recall "<query>"              # Semantic + full-text search
vein brief                         # Session primer — paste into any AI

vein debrief                       # Auto-extract decisions from last git diff
vein hooks install                 # Install post-commit hook (runs debrief silently)

vein status                        # Show .vein/ stats
vein import docs/decisions.md      # Bulk-import existing docs
```

## MCP Server

```json
{
  "mcpServers": {
    "vein-myproject": {
      "command": "vein",
      "args": ["mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

Four tools available to any MCP client (Claude Desktop, Claude Code, Cursor, Cline):

- `vein_brief()` — session orientation primer
- `vein_recall(query)` — semantic search over lore
- `vein_log(type, message)` — capture a decision in the moment
- `vein_status()` — project name + entry counts

## Lode integration *(planned, Phase 0.2)*

When [Lode](https://rexcode.app/lode) is installed:

- **Right-click in diff view** → "Send to Vein" — captures the diff + your annotation as a lore entry
- **Decision timeline** — Lode visualizes your `.vein/` chronologically
- **Surface in context** — Lode shows "this file has 3 related decisions" inline

## Storage

```
.vein/
├── decisions/
│   ├── 20260520_drop_sqlite_for_parquet.md
│   └── 20260522_auth_middleware_refactor.md
├── debug_lore/
│   ├── third_party_api_quirks.md
│   └── webkit_overlay_gotchas.md
├── links/                    # autogen — connects entries to file:line
└── config.yaml
```

All markdown. All git-friendly. All hand-editable.

## What Vein does NOT do

- ❌ Index your source code (LLMs do that; `git` versions it)
- ❌ Replace `git log` (it complements it)
- ❌ Replace Slack / docs / ADRs (it can absorb them, but doesn't force migration)
- ❌ Send anything to the cloud (local-first; you push `.vein/` to your own git remote if you want sharing)
- ❌ Lock you into a vendor (MIT, markdown-based, you can `cat` everything)
