# Vein

> **Lode finds the code. Vein remembers the why.**

Local-first decision & debug lore archive for AI-assisted development.
Part of the **[Lode Vein](https://rexcode.app)** suite.

---

## The problem

Your LLM reads every line of code. It cannot read your mind.

- Why did you add that workaround on line 142?
- Why did you drop SQLite in week 3?
- Which edge case took four days to find?

That knowledge lives in your head, a Slack thread, or nowhere.
Every new AI session starts from zero and pays the re-orient tax.

**Vein fixes that.**

---

## Install

```bash
pip install lode-vein
```

Requires Python 3.10+. No other dependencies for core use.
Optional: [ollama](https://ollama.com) for semantic search and auto-capture polish.

---

## Quick start

```bash
# Initialize in your project
cd /path/to/your/project
vein init

# Capture a decision as you make it
vein log decision "use sqlite not postgres — simpler deployment, no server needed"
vein log lore     "rate-limit API returns 200 not 429 — see client.py:142 workaround"
vein log pitfall  "never call submit() from within a callback — re-entrant crash"

# Next session, orient any AI in seconds
vein brief        # → session primer, paste into Claude / Gemini / GPT

# Search your lore
vein recall "sqlite"
vein recall "rate limit"
```

---

## Auto-capture (zero manual effort)

Install a post-commit hook — after every `git commit`, local AI scans the diff
and silently logs decisions worth keeping:

```bash
vein hooks install   # installs post-commit hook
```

Requires ollama running locally. If ollama is unavailable, silently skips.

---

## MCP server (Claude Desktop / Claude Code)

```bash
vein mcp   # starts stdio MCP server
```

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

Claude now has four tools available automatically:

| Tool | What it does |
|------|-------------|
| `vein_brief()` | Session primer — called at start of every session |
| `vein_recall(query)` | Search lore before making changes |
| `vein_log(type, message)` | Capture a decision in the moment |
| `vein_status()` | Project name + entry counts |

No manual prompting needed. Claude decides when to call them.

---

## How it works

```
.vein/
  decisions/   # why A not B: architecture, library, API design
  lore/        # API quirks, workarounds, "don't refactor this"
  pitfalls/    # things that went wrong, warnings for the future
  references/  # links to ADRs, issues, RFCs
```

Plain markdown + YAML frontmatter. Committed to git.
Clone the repo → get the memory. Switch AI tools → keep the memory.

---

## Commands

```bash
vein init                    # initialize .vein/ in current project
vein log decision "..."      # capture an architectural decision
vein log lore "..."          # capture debug lore / API quirk
vein log pitfall "..."       # capture a pitfall
vein recall "query"          # semantic + FTS search
vein brief                   # session primer (≤800 tokens)
vein debrief                 # auto-extract from last git diff (needs ollama)
vein hooks install           # post-commit hook → auto debrief
vein mcp                     # start MCP server
vein import docs/adr/        # bulk-import existing ADRs / changelogs
vein status                  # show .vein/ stats
```

---

## Why not just use X?

**vs native AI memory (Claude Memory, Cursor Memory):**
Native memory stores user preferences — cross-project habits, your background.
Vein stores project decisions — why the architecture looks the way it does.
They're complementary. Also: native memory is siloed to one tool. `.vein/` travels with the repo.

**vs `git log`:**
`git log` tells you *what* changed. Vein captures *why* — including rejected alternatives
and pitfalls discovered after the fact.

**vs ADR tools:**
ADRs require a full document per decision. Vein captures in one line.
`vein import docs/adr/` imports existing ADRs into `.vein/` automatically.

---

## Status

**Phase 0 / Early access.** Dogfood-driven — built for the [Lode](https://rexcode.app/lode) project.

- CLI: `vein init` / `vein log` / `vein recall` / `vein brief` / `vein debrief` — working
- MCP server: working
- Semantic search: requires `ollama pull nomic-embed-text` + `vein reindex`
- PyPI: `pip install lode-vein`

---

## License

MIT © 2026 [rex4ssd](https://github.com/rex4ssd)
