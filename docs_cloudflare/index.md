# Vein

> **Lode finds the code. Vein remembers the why.**
>
> Local-first decision & debug lore archive for AI-assisted development.

Part of the **[Lode Vein](https://rexcode.app)** suite.

---

## The problem

Your LLM can read every line of code in your repo. It can parse the AST, follow imports, understand types.

But it can't tell you **why** you added that workaround on line 142 last Wednesday. It can't recall the three hours you spent figuring out that the third-party API returns `200` instead of `429` when rate-limited. It can't reconstruct the decision to drop SQLite in favor of Parquet.

**The code is the present. The decisions are the past. LLMs see the present. Vein remembers the past.**

---

## What Vein does

A small CLI that captures and surfaces:

- **Decisions** — architectural choices, why you picked A over B
- **Debug lore** — quirks of external APIs, weird workarounds, "don't refactor this, here's why"
- **Refactor notes** — what you tried, what failed, what stuck

Stored as plain markdown in `.vein/`, indexed locally for retrieval via:

- **CLI**: `vein log "..."` / `vein recall "..."` / `vein review`
- **MCP server** (planned): any MCP client (Claude Desktop, Cursor, Cline) can query your decision history as a tool

---

## Quick example

```bash
# After solving a tricky bug
vein log lore "API rate-limit returns 200 not 429 — see api/client.rs:142 workaround"

# After making an architectural call
vein log decision "drop sqlite for parquet — single-writer constraint failed scale test"

# Next time you (or your LLM) ask
vein recall "sqlite"
# → returns the decision above with file:line links

# Weekly review
vein review --since 7d
```

---

## Why not just `git log`?

`git log` tells you *what* changed. It rarely tells you *why* — and when it does, the why is buried in commit messages that nobody re-reads.

Vein is the difference between:

- "Refactor auth middleware" *(git commit)*
- "Dropped session-token storage from middleware because legal flagged it under the new compliance requirements; see decisions/20260520_auth_compliance.md" *(vein)*

---

## Why not [other AI context tool]?

Most "AI context" tools index your **code** and serve it back as RAG. Useful, but redundant with what LLMs can already do with a big enough context window.

Vein indexes the **invisible knowledge** — the reasoning, the workarounds, the trade-offs — that LLMs cannot reconstruct from code alone.

See [Why Vein](why.md) for a full comparison.

---

## Status

**Phase 0 / Early access.** Spec stable, CLI in development. Dogfood-driven design — built by [@rex4ssd](https://github.com/rex4ssd) for the [Lode](https://rexcode.app/lode) project.

- 📜 [About](about.md)
- 🤔 [Why Vein](why.md)
- 🔧 [Features](features.md)
- ⬇️ [Install](install.md)

---

## Lode Vein

Vein is one product in the **Lode Vein** suite:

- **[Lode](https://rexcode.app/lode)** — desktop GUI for fast file viewing, folder/file/binary compare, git inspection, full-text search
- **[Vein](#)** — decision lore archive *(you are here)*

Together: Lode shows you the code. Vein remembers the why.
