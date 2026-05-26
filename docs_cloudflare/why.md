# Why Vein

> *Placeholder — full content待 Phase 0 dogfood 後再 polish。先放骨架。*

## The thesis

There are two kinds of knowledge in every codebase:

1. **What the code does** — derivable from the code itself. LLMs handle this with enough context window.
2. **Why the code is this way** — *not* derivable from code. Lives in commit messages (terse), Slack (lost), heads (mortal), ADRs (rarely updated).

Most "AI context" tools index #1. They re-do work the LLM can already do.

Vein indexes #2.

## vs other tools

(placeholder — fill in after dogfood + after re-verifying competitor positioning)

| Tool | Indexes... | Vein indexes... |
|---|---|---|
| Cursor `.cursor/rules` | Coding conventions | Decisions + lore |
| ContextFS | Codebase + semantic memory | Decisions + lore only |
| ctx-sys | Code via tree-sitter + graph | Decisions + lore only |
| adr-tools | ADRs (manually written) | ADRs + AI-assisted capture + retrieval |
| `git log` | Commit history (terse) | Reasoning history (polished) |

## When to use Vein

✅ You have an LLM coding assistant (Claude, Cursor, etc.)
✅ You re-read commit messages and find them useless
✅ You've explained the same architectural decision more than twice
✅ You work on the project for ≥ 3 months and forget things
✅ You want new teammates to onboard in 1 day, not 1 month

## When **not** to use Vein

❌ Solo throwaway scripts (overkill)
❌ You already maintain ADRs manually and they work
❌ Your project has < 30 days of history and no decisions yet
❌ You don't run a local LLM (Vein assumes Ollama for capture-time polish)
