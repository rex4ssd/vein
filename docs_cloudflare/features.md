# Features

> *Placeholder — Phase 0 階段，core commands 在 spec/v0.1.md 還沒改寫為 Path D 形態。等 code 開始才能 polish。*

## Core CLI

```bash
vein init                          # Initialize .vein/ in current repo
vein log decision "..."            # Capture an architectural decision
vein log lore "..."                # Capture debug lore / API quirk / workaround
vein log refactor "..."            # Capture what you tried and learned

vein recall "<query>"              # Retrieval: find related decisions
vein review --since 7d             # Weekly summary of what was captured

vein link --to-file <path:line>    # Attach a file:line anchor to last entry

vein status                        # Show .vein/ state
```

## MCP integration *(planned, Phase 0.3)*

```json
{
  "mcpServers": {
    "vein": {
      "command": "vein",
      "args": ["serve"]
    }
  }
}
```

Exposes tools:

- `recall` — semantic search over decisions + lore
- `surface` — given a file:line, return related decisions
- `digest` — get a brief summary of the project's lore

Works with Claude Desktop, Claude Code, Cursor, any MCP-compatible client.

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
