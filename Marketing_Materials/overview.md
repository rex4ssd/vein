# Vein — Overview Copy
> Marketing copy for the rexcode.app/vein landing page.
> Style ref: rexcode.app/lode — punchy, developer-focused, specific numbers.

---

## Hero

### Tagline (primary)
**Lode finds the code. Vein remembers the why.**

### Sub-tagline options
- *Your AI starts every session from zero. Vein fixes that.*
- *The project memory that travels with your repo — not your AI tool.*
- *One command to capture. Instant recall. Any AI, any session.*

### Hero paragraph (≤ 40 words)
Every time you start a new AI session, you pay the re-orient tax — re-explaining decisions, re-discovering workarounds, re-loading context. Vein stores that knowledge once, in `.vein/`, and any AI can pull it instantly.

---

## The Problem (3-line version)

Your LLM reads code. It cannot read your mind.

- **Why** did you add that workaround on line 142?
- **Why** did you drop SQLite in week 3?
- **Which** random seed reproduces the race condition?

That knowledge lives in your head, a Slack thread, or nowhere. Vein gives it a home.

---

## Stat Cards (like Lode's 20 GB / 0 brew / 6 tools)

| Stat | Label |
|------|-------|
| **1 command** | to capture a decision |
| **< 2 K tokens** | to brief any AI session |
| **0 cloud** | plain markdown, local-first |
| **∞ AI tools** | works with Claude, Gemini, GPT, Cursor, any MCP client |

---

## Value Props (short)

### 🧠 Project memory that outlives your AI session
Native AI memory stores user preferences — cross-project habits, your background.
Vein stores project decisions — why the architecture looks the way it does, which approaches failed, which pitfalls to avoid.
They're complementary. Use both.

### 📁 Lives in the repo, not the tool
`.vein/` sits next to `.git/`. Clone the repo, get the memory.
Switch from Claude to Cursor to Gemini CLI — the knowledge follows.

### ⚡ Capture in seconds, recall in milliseconds
```bash
vein log lore "API returns 200 not 429 on rate-limit — see client.rs:142"
vein recall "rate limit"   # → finds it instantly
vein brief                 # → ~800-token session primer
```

### 🔍 Designed for AI retrieval, not just human reading
Capture-time polish: raw input → structured entry with title, trade-offs, tags, related decisions.
Retrieval quality is determined at write time — not search time.

---

## CTA Block

> **Vein is in early access.** CLI in active development.
>
> Watch the repo → [github.com/rex4ssd/vein](https://github.com/rex4ssd/vein)
> Part of the **Lode Vein** suite → [rexcode.app](https://rexcode.app)

---

## Who Is It For?

**Solo developers** switching between long-running projects who lose thread between sessions.

**AI-heavy workflows** — if you're burning tokens re-explaining context every session, Vein pays for itself in 10 minutes.

**Small teams** where domain knowledge concentrates in one person and turnover is painful.

**Hardware / firmware engineers** working across simulation and real silicon — behavior differences that are critical and chronically underdocumented.

---

## One-liner (for meta description / OG)
> Vein — local-first decision & debug lore archive. Capture why your code works the way it does. Recall it instantly in any AI session.
