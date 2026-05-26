# About Vein

## What is Vein

Vein is a local-first CLI tool that captures and surfaces **decision and debug lore** for AI-assisted software development.

Think of it as `git`, but instead of versioning your code, it versions your **reasoning**.

## What problem it solves

Every project accumulates invisible knowledge:

- Why a function uses `Mutex` instead of `RwLock`
- Which API call has an undocumented rate-limit quirk
- The architectural decision to choose `parquet` over `sqlite` 6 months ago
- The 3-hour debugging session that ended with one obscure config flag

This knowledge lives in:

- Slack messages nobody can find
- Commit messages too terse to be useful
- The lead engineer's head
- ADR documents in `docs/adr/` that nobody updates

**LLMs cannot reconstruct this from code alone.** Even with a 1M-token context window, an LLM looking at the current state of your repo cannot tell you what you tried and rejected, what almost broke production, or why a "weird" pattern is actually load-bearing.

Vein makes this lore:

- **Capturable** in seconds (`vein log decision "..."`)
- **Searchable** by any AI assistant (via local RAG or MCP)
- **Versionable** alongside your code (`.vein/` is a git-friendly folder)
- **Portable** across teammates (Dev B clones repo → instant access to Dev A's lore)

## How it works

```
You                       Vein                      Your AI Assistant
───                       ────                      ─────────────────

  │
  │ vein log decision "..."
  ├─────────────────────►  Stores as markdown
  │                        in .vein/decisions/
  │                        AI polishes wording
  │                        Links to file:line
  │
  │
  │                                                   "Why did we drop sqlite?"
  │                                                   ◄────── via MCP tool call
  │                        ┌───────────────────────►  vein recall("sqlite")
  │                        │                          ◄────── returns decision
  │                        │
  │                        Embeddings (Ollama)
  │                        Hybrid retrieval
  │                        Returns relevant ADR
  │                        + file:line links
  │
```

Everything runs locally. Embeddings via Ollama. Storage in `.vein/` (plain markdown + small SQLite index). Optional MCP server for any Claude-compatible AI client.

## Design principles

- **Local-first.** Nothing leaves your machine unless you push the `.vein/` folder yourself.
- **Markdown-based.** No proprietary format. `.vein/decisions/*.md` are normal files you can `cat`, `grep`, or hand-edit.
- **Git-friendly.** Commit `.vein/` to your repo. New teammates clone → instant context.
- **No telemetry, ever.**
- **One job.** Vein captures decision lore. It does not index your codebase (your LLM and `git` already do that).

## The Lode Vein suite

Vein is part of a small family of tools by [@rex4ssd](https://github.com/rex4ssd):

| Tool | What it does | Status |
|---|---|---|
| **[Lode](https://rexcode.app/lode)** | Desktop GUI: file viewer, folder/file/binary compare, full-text search, git inspection | Shipping (App Store + Direct Sale) |
| **Vein** | Decision lore archive CLI + MCP server | Phase 0 (early access) |

The mining metaphor: **Lode** is the rich deposit of code; **Vein** is the path through it carrying the valuable decisions.

> Lode finds the code. Vein remembers the why.

## License

MIT. Built to be used, forked, and outlived.

## Sustainability

Vein is OSS and free for individuals. Future commercial features (team sync via `.vein/` push, RBAC, audit log) will follow an Open Core model. Lode covers maintenance costs — Vein doesn't need to monetize to survive.
