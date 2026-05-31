# Vein — Feature Highlights
> Marketing-ready feature descriptions. Plain language, developer audience.

---

## Core Commands

### `vein log` — Capture in one line
No editor to open. No template to fill. One command, one line of context.

```bash
vein log decision "drop SQLite for Parquet — single-writer constraint failed at scale"
vein log lore     "DMA API uses callback not polling: SystemC model is sc_event-driven"
vein log pitfall  "never call hal_dma_submit from within a callback — re-entrant hell"
```

Three entry types, zero friction.

---

### `vein recall` — Full-text + semantic search
No grep. No archaeology. Type what you remember, get the decision back.

```bash
vein recall "sqlite"          # → decision about dropping SQLite
vein recall "rate limit api"  # → the 200-not-429 lore entry
vein recall "DMA callback"    # → the pitfall + the why
```

Works offline via FTS5. Add local ollama for semantic (embedding) search.

---

### `vein brief` — 30-second AI session primer
```bash
vein brief
```
Outputs ≤ 2 K tokens: top decisions, active pitfalls, recent lore.
Paste into any AI session. Your LLM is oriented in seconds, not minutes.

---

### `vein ask` — Natural language Q&A over your lore
```bash
vein ask "why does the DMA API use callbacks?"
```
Queries your `.vein/` archive and returns the matching entry.
Works with local ollama or a connected MCP client.

---

### `vein review` — Weekly lore digest
```bash
vein review --since 7d
```
What decisions did you make this week? What pitfalls did you hit?
Good for weekly retros, onboarding new teammates, or auditing AI-assisted work.

---

### `vein import` — Bring in existing docs
```bash
vein import docs/adr/
vein import CHANGELOG.md
```
Already have ADRs, changelogs, or design docs? Import them into `.vein/` and they become searchable alongside new entries.

---

## The `.vein/` Directory

```
.vein/
  decisions/    # architectural choices, why A over B
  lore/         # API quirks, workarounds, "don't refactor this"
  pitfalls/     # things that went wrong and how to avoid them
  references/   # links to ADRs, issues, RFCs
```

Plain markdown + YAML frontmatter. Committed to git.
Any editor can read it. Any AI can consume it. No proprietary format.

---

## Key Properties

| Property | Detail |
|----------|--------|
| **Local-first** | All data stays on your machine. No cloud sync required. |
| **Git-native** | `.vein/` is committed to the repo. Clone = get the memory. |
| **AI-agnostic** | Works with Claude, Gemini, ChatGPT, Cursor, any MCP client. |
| **Offline capable** | FTS5 recall works without network or ollama. |
| **Zero telemetry** | No analytics, no phoning home. |
| **Plain text** | Future-proof. Readable by humans and tools for decades. |

---

## Planned: MCP Server (Phase 0.3)

Any MCP client — Claude Desktop, Cursor, Cline — will be able to query your `.vein/` directly as a tool call.

```
// Claude Desktop config
"vein": {
  "command": "vein",
  "args": ["mcp"]
}
```

Your lore becomes a live tool in any AI workspace. No copy-paste, no manual briefs.

---

## Capture-Time Polish (powered by local AI)

When you `vein log`, a local model (via ollama) structures your raw input:

**Raw input:**
> "don't use polling for DMA, it doesn't work with SystemC"

**After polish:**
```yaml
title: "DMA API uses callback not polling"
type: decision
tags: [dma, hal, systemc, callback, host-build]
body: |
  Why: SystemC DMA model is event-driven (sc_event); polling busy-waits
       in HOST build, wasting simulation time.
  Trade-off: callbacks require ISR context discipline.
related: [pitfalls/dma_callback_reentrant.md]
```

Retrieval quality is locked in at write time. Future sessions find the right entry even if you phrase the question differently.

*(Works without ollama — raw entry is saved; polish runs when ollama is available.)*
