# Vein — Social Posts
> Ready-to-post content. Edit dates/links before publishing.
> Style ref: Lode market_260527.md

---

## Twitter / X

### Post A — Problem hook
```
Every AI session starts from zero.

You re-explain the same decisions.
Re-discover the same workarounds.
Re-load the same context.

That's the re-orient tax. Vein fixes it.

One command to capture. Instant recall. Any AI, any session.

🔗 rexcode.app/vein
#DevTools #AITools #MacOS
```

---

### Post B — Code example
```
Ever wish your AI remembered why you made that call?

$ vein log decision "drop SQLite for Parquet — single-writer constraint failed"
$ vein log lore "API returns 200 not 429 on rate-limit — see client.rs:142"

# 3 weeks later, new session
$ vein brief   # → 800-token primer, AI oriented in seconds

Lode finds the code. Vein remembers the why.

rexcode.app/vein
#AIAssistedDev #DeveloperTools
```

---

### Post C — Insight / thought leadership
```
The gap in AI-assisted development nobody talks about:

Your LLM can read every line of your code.
It cannot read the 3-hour debugging session that led to line 142.
It cannot recall why you chose callbacks over polling.
It cannot reconstruct the compliance decision that rewrote your auth layer.

The code is the present. The decisions are the past.
LLMs see the present. Vein remembers the past.

#SoftwareEngineering #AITools #DevProductivity
```

---

### Post D — Launch / early access
```
Introducing Vein 🌿

Decision & debug lore archive for AI-assisted development.

.vein/ lives in your repo like .git/
→ Clone the repo, get the memory
→ Switch AI tools, keep the memory
→ New teammate, hand them the memory

Part of the Lode Vein suite: Lode finds the code, Vein remembers the why.

Early access → rexcode.app/vein
#OSS #MacOS #DevTools #AITools
```

---

## LinkedIn

### Post A — Professional / thought leadership
```
The hidden cost of AI-assisted development: the re-orient tax.

Every new AI session, you pay it. You re-explain why the architecture looks the way it does. You re-discover that the third-party API returns 200 instead of 429 on rate-limit. You re-load context that hasn't changed since last week.

Most AI tools solve the code-reading problem. They index your files, parse your AST, follow your imports.

None of them solve the decision problem: why does the code work the way it does?

That's what we built Vein for.

Vein is a CLI tool that captures decision lore — the why behind technical choices — and stores it in .vein/, a directory that lives inside your project like .git/. One command to capture. Instant full-text and semantic recall. A session brief in under 2K tokens that any AI can consume.

Clone the repo, get the memory. Switch AI tools, keep the memory.

Early access: rexcode.app/vein

#SoftwareEngineering #AI #DeveloperTools #MacOS #AIAssistedDevelopment
```

---

### Post B — Feature focus
```
We built Vein because we kept paying the same 5,000-token tax.

New Claude session → paste the whole docs/ folder.
New Gemini session → repeat.
New Cursor session → repeat.

The code hadn't changed. The decisions hadn't changed. But each AI started from zero.

Vein's approach:
• vein log — one-line capture of decisions, lore, pitfalls
• vein brief — ≤800 token session primer, ready to paste
• .vein/ — committed to git, readable by any AI, any tool

The memory travels with the repo, not with the AI subscription.

Part of the Lode Vein family → rexcode.app

#DevTools #AI #MacOS #ProductivityTools #OpenSource
```

---

## Hacker News (Show HN)

### Show HN post
```
Show HN: Vein – local-first decision lore archive for AI-assisted development

We kept paying the same re-orient tax: every new AI session re-loads context 
that hasn't changed since the last one.

Vein is a CLI that captures why code works the way it does and stores it in 
.vein/ — a directory that lives inside your project like .git/.

  $ vein log decision "drop SQLite for Parquet — single-writer constraint failed"
  $ vein log lore "API returns 200 not 429 on rate-limit — see client.rs:142"
  $ vein brief   # → <800-token primer, paste into any AI session

Key properties:
- Plain markdown + YAML frontmatter. No proprietary format.
- Committed to git. Clone the repo, get the memory.
- Works with any AI tool (Claude, Gemini, Cursor, local models).
- FTS5 recall offline; local ollama for semantic search.
- MCP server planned (Phase 0.3) so any MCP client can query .vein/ directly.

We've been dogfooding it on two projects (~13 entries). The test that convinced 
us it works: starting a session with `vein brief` instead of pasting docs/ — 
same orientation, 10x fewer tokens.

Early access / watching: rexcode.app/vein
Repo will go public once vein log + vein recall have been used on a real project 
for ≥2 weeks.

Happy to discuss the design tradeoffs — particularly around capture-time polish 
vs. retrieval-time reranking.
```

---

## Short Taglines (for bios, headers, OG descriptions)

```
Lode finds the code. Vein remembers the why.
Your project's AI memory — in plain markdown, committed to git.
One command to capture. Instant recall. Any AI session.
The .git/ for decisions.
Stop re-explaining your codebase to every new AI session.
```

---

## Image / Visual Copy Suggestions

**Hero stat block** (like Lode's 20GB / 0 brew):
- `1 command` — to capture a decision
- `< 2K tokens` — to brief any AI session  
- `0 cloud` — plain markdown, local-first
- `∞ AI tools` — Claude · Gemini · GPT · Cursor · any MCP client

**Before / After comparison:**

| Before Vein | After Vein |
|-------------|------------|
| Paste 5,000 tokens of docs every session | `vein brief` → 800-token primer |
| Re-explain the same decision 10 times | `vein recall "..."` → instant answer |
| New teammate asks why code looks this way | Hand them the repo — `.vein/` is already there |
| Switch AI tools — lose all context | Clone, keep everything |
