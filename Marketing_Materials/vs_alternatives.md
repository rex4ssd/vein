# Vein vs. Alternatives
> Comparison copy for rexcode.app/vein — honest, specific, no FUD.

---

## The Short Version

| | Vein | Native AI memory | `git log` | ADR tools | Note RAG |
|---|---|---|---|---|---|
| Stores *why* decisions were made | ✅ | ❌ | ⚠️ sometimes | ✅ | ⚠️ |
| Works across AI tools | ✅ | ❌ siloed | ✅ | ✅ | ⚠️ |
| One-command capture | ✅ | ✅ | ❌ | ❌ | ⚠️ |
| Structured for AI retrieval | ✅ | ✅ | ❌ | ❌ | ❌ |
| Lives with the repo | ✅ | ❌ | ✅ | ✅ | ❌ |
| No cloud required | ✅ | ❌ | ✅ | ✅ | ⚠️ |

---

## Vein vs. Native AI Memory (Claude Memory, Cursor Memory, etc.)

**Native AI memory answers: "Who is this person?"**
It stores user preferences — how you like responses formatted, your background, your cross-project habits. Useful. Not the same thing.

**Vein answers: "Why does this project work this way?"**
It stores project decisions — why the architecture looks the way it does, which approaches were tried and failed, which external API has a surprise quirk.

**The other difference: portability.**
Native AI memory is siloed to one tool. Switch from Claude Code to Gemini CLI — the memory is gone.
`.vein/` is plain markdown. Clone the repo, get the memory. Switch tools, keep the memory. Hand it to a new teammate, they hit the ground running.

> Use both. They're complementary, not competing.

---

## Vein vs. `git log` / Commit Messages

`git log` tells you **what** changed. It rarely tells you **why** — and when it does, the context is buried in a commit message that nobody re-reads.

**git log:**
```
commit a3f91b2
"Refactor auth middleware"
```

**Vein:**
```
title: "Dropped session-token storage from middleware"
why:   Legal flagged it under new compliance requirements.
       Session tokens were being stored in a format that doesn't
       meet the updated data retention policy (effective 2026-Q2).
file:  decisions/20260520_auth_compliance.md
```

One is archaeology. The other is a searchable answer.

---

## Vein vs. ADR Tools (adr-tools, log4brains, etc.)

ADR tools require a full structured document per decision — right level of rigor for major architectural choices.

**The problem:** most decisions that matter are too small for a formal ADR.
- A 3-line function signature choice
- A timing assumption in a simulation model  
- A workaround for a third-party library bug

These never get written down. Vein captures them with **one command**.

Vein is compatible with ADRs. `vein import docs/adr/` pulls existing ADRs into `.vein/` and makes them searchable alongside new entries.

---

## Vein vs. Note RAG Tools (Obsidian + RAG, Notion AI, etc.)

Most "AI memory" tools do retrieval over raw notes: dump text in, semantic search brings it back.

**The problem with raw retrieval:** retrieval quality depends entirely on how well you happened to phrase the original note.

Vein uses **capture-time polish**: when you run `vein log`, a local model structures the raw input into a typed entry with a title, extracted trade-offs, tags, and related entries. The entry becomes retrievable even if future queries use completely different phrasing.

**Also:** raw note tools are not built around the repo unit. Vein's `.vein/` lives inside the project directory, committed to git — the memory and the code stay together permanently.

---

## Vein vs. Writing Better Comments and Docs

Comments explain **what** code does.
Vein captures **why** a decision was made — including rejected alternatives, constraints that drove the choice, and pitfalls discovered afterward.

You *could* write this in comments. You usually won't, because the full context isn't obvious while you're writing the code, and comments aren't structured for retrieval.

Vein is a deliberate capture step, separate from implementation. It takes 10 seconds per entry.

---

## Vein vs. Just Using a Big Context Window

Dumping your entire docs/ directory into the context window works — until it doesn't.

- **Cost:** large payloads on every turn
- **Speed:** slower responses, slower iteration
- **Limit:** eventually you hit the context ceiling
- **Relevance:** LLM sees everything, retrieves nothing specifically

Vein's approach: pre-process at capture time, serve a targeted ≤ 2 K token brief at session start. Your AI gets the relevant past, not everything ever written.

---

## Bottom Line

Vein is not trying to replace any of these tools. It fills the gap between "code the LLM can read" and "context the LLM cannot reconstruct."

If you're doing AI-assisted development and re-explaining the same decisions session after session — that's the gap Vein closes.
