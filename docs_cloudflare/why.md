# Why Vein?

> **Lode finds the code. Vein remembers the why.**

---

## The problem

Every non-trivial project accumulates two kinds of knowledge.

The first kind lives in the code: what the system does, how it's structured, what the tests cover. Tools are good at this. `grep`, LSPs, code search — they all work.

The second kind doesn't live anywhere:

- Why does the DMA API take a callback instead of returning a value?
- Why did you abandon the embedded database approach in week 3?
- Which random seed reproduces the race condition that took four days to find?
- What's the difference between how the SystemC model behaves and how the real chip behaves — and which code paths are affected?

This knowledge lives in engineers' heads, Slack threads, and outdated PR comments. It survives only as long as the people who made the decisions are still around and still remember.

When a new engineer joins, they spend two weeks asking questions whose answers already exist — they just aren't written down anywhere useful.

When a new AI session starts, it spends 5,000 tokens grepping around trying to understand a codebase that hasn't changed since the last session.

When someone leaves the team, the decisions they made become archaeology.

---

## What Vein does

Vein is a CLI tool that captures **decision lore** — the *why* behind technical choices — and stores it in `.vein/`, a directory that lives inside your project like `.git/`.

```bash
# capture a decision as you make it
vein log decision \
  "DMA API uses callback not polling: SystemC model is event-driven \
   (sc_event), polling would busy-wait in HOST build. MP build's IRQ \
   handler maps naturally to callback. Trade-off: callback requires \
   careful ISR context management — never call from within a callback."

# one month later, new session, new engineer, or new AI tool
vein ask "why does DMA use callback?"
→ Finds it immediately. No grep. No archaeology.

# start any session in 30 seconds
vein brief
→ Top decisions, active pitfalls, recent lore. ~800 tokens.
```

The lore lives in `.vein/`, committed to git, readable by any tool.

---

## The core insight

**Project memory should travel with the project, not with the person or the tool.**

`.git/` doesn't belong to any one engineer. It doesn't belong to any one IDE. It's part of the project, and anyone who clones the repo gets the full history.

`.vein/` works the same way: the decisions, pitfalls, and lore are project assets. Clone the repo, get the memory. Switch AI tools, keep the memory. New team member, hand them the memory.

---

## Why not just use X?

### Native AI memory (Claude Memory, Cursor Memory, etc.)

Built-in AI memory stores *user preferences* — how you like to be spoken to, your background, your cross-project habits. It answers "who is this person?"

Vein stores *project decisions* — why the architecture looks like it does, which approaches failed, which pitfalls to avoid. It answers "why does this project work this way?"

They're complementary. Use both.

The other difference: native AI memory is siloed to one tool. If you switch from Claude Code to Gemini CLI, the memory is gone. `.vein/` is plain markdown — any tool can read it.

### Writing better comments and docs

Comments explain *what* code does. Vein captures *why* a decision was made — including the rejected alternatives, the constraints that drove the choice, and the pitfalls discovered afterward.

You could write this in comments. You usually won't, because the full context isn't obvious while you're writing the code. Vein is a deliberate capture step, separate from implementation.

### gbrain / note RAG tools

Most "AI memory" tools do retrieval over raw notes: you dump text in, semantic search brings it back.

Vein's approach is different: **capture-time polish**. When you run `vein log`, a local model structures the raw input into a typed entry with a clear title, extracted trade-offs, suggested tags, and related entries. Retrieval quality is determined at write time, not search time.

Raw note: *"don't use poll-based DMA, it doesn't work with SystemC"*

Vein entry after polish:
```
title: "DMA API uses callback not polling"
type: decision
tags: [dma, hal, systemc, callback, host-build]

Why: SystemC DMA model is event-driven (sc_event); polling busy-waits
     in HOST build, wasting simulation time.
Trade-off: callbacks require ISR context discipline.
Pitfall: calling hal_dma_submit from within a callback causes
         re-entrant callback hell.
```

The second form is retrievable, explainable, and still useful a year later.

### ADR tools (adr-tools, log4brains, etc.)

ADR tools require you to write a full structured document per decision. That's the right level of rigor for major architectural choices — Vein is compatible with ADRs and can import them.

But most decisions that matter are too small for a formal ADR: a 3-line function signature choice, a timing assumption in a simulation model, a workaround for a third-party library bug. These never get written down. Vein captures them with one command.

---

## Who is Vein for?

Vein is for developers who work on projects complex enough that the *why* gets lost:

- **Solo developers** working across multiple long-running projects who context-switch and lose thread
- **Small teams** where domain knowledge is concentrated and turnover is painful  
- **AI-heavy workflows** where you're constantly starting new sessions and paying the re-orient cost every time
- **Hardware/firmware engineers** working across simulation and real silicon, where behavior differences are critical and underdocumented

Vein is not the right tool for throwaway scripts, weekend projects, or anything where a good README already captures everything that matters.

---

## Current status

Vein is in early development (Phase 0 — dogfood). The CLI is not yet available.

Watch the repo: [github.com/rex4ssd/vein](https://github.com/rex4ssd/vein)

The repo is currently private. It will open once `vein init`, `vein log`, and `vein recall` are working and have been used on a real project for at least two weeks.
