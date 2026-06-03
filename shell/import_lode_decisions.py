#!/usr/bin/env python3
"""
import_lode_decisions.py — Suck Lode's real decision/pitfall lore into Vein.

Lode keeps its hard-won lore in `lode/docs/decisions.md`:
  - `## 架構決策（不要改）`        — a markdown table of architecture decisions
  - `## 已知問題 / 小坑（還沒修）`  — a markdown table of known issues
  - `### 🔴 / 🟡 <title>` blocks   — ~40 "走過的雷" (the crown jewels)

These are exactly the "all pitfalls walked" content Rex wants in Vein, but they
were NOT in the .vein/ store (only generic GitHub-fetched noise was). This parser
extracts them into proper Vein entries.

Design:
  - pitfalls  ← every `### 🔴/🟡/⛔ ...` block (body = until next ### / ##)
  - decisions ← rows of the 架構決策 table
  - pitfalls  ← rows of the 已知問題 table
  - volatility = internal-invariant (3yr TTL — our own architecture rationale)
  - IDEMPOTENT: dedup by (source, title); re-run after editing decisions.md and
    only new entries get added. Safe to run repeatedly.

Run inside your venv (vein on PATH):
  cd /Users/lion/Documents/vein && python3 shell/import_lode_decisions.py
  # then it auto-reindexes; verify:  vein recall "read_to_end take cap"
"""

from __future__ import annotations

import re
import subprocess
import sys
import shutil
from pathlib import Path

VEIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(VEIN_ROOT / "src"))

from vein.core.store import VeinStore          # noqa: E402
from vein.core.models import Entry             # noqa: E402

LODE_DECISIONS = Path.home() / "Documents" / "lode" / "docs" / "decisions.md"
SOURCE = "lode:docs/decisions.md"
PROJECT = "project:lode"
VOLATILITY = "internal-invariant"


# ── parsers ──────────────────────────────────────────────────────────────

# Generic section headers that happen to be `###` but aren't real pitfalls.
GENERIC_TITLES = {"修復清單", "修復", "Bug", "Known Issue"}


def parse_heading_pitfalls(text: str) -> list[tuple[str, str]]:
    """Every `### [emoji] title` block → (title, body) until next ###/##."""
    out = []
    pat = re.compile(r"^###[ \t]+(.+?)[ \t]*$", re.M)
    ms = list(pat.finditer(text))
    for i, m in enumerate(ms):
        raw_title = m.group(1)
        # strip leading status emoji / marker
        title = re.sub(r"^(?:🔴|🟡|🟢|⛔|⚠️)\s*", "", raw_title).strip()
        if not title or title in GENERIC_TITLES:
            continue
        start = m.end()
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        body = text[start:end]
        # don't bleed past a new ## section
        nxt = re.search(r"^##[ \t]", body, re.M)
        if nxt:
            body = body[: nxt.start()]
        body = body.strip()
        if len(body) < 25:          # skip near-empty headers like "### 修復清單"
            continue
        out.append((title, body))
    return out


def _split_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def parse_table(text: str, heading_kw: str) -> list[list[str]]:
    """Return data rows (list of cells) of the markdown table under the
    `## ...heading_kw...` section."""
    rows: list[list[str]] = []
    in_section = False
    seen_header = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_section = heading_kw in line
            seen_header = False
            continue
        if not in_section:
            continue
        if not line.strip().startswith("|"):
            continue
        if re.match(r"^\s*\|[\s\-:|]+\|\s*$", line):   # |---|---| separator
            seen_header = True
            continue
        cells = _split_row(line)
        if not seen_header:        # first | row is the column header
            seen_header = True
            continue
        if any(cells):
            rows.append(cells)
    return rows


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    if not LODE_DECISIONS.exists():
        print(f"[error] {LODE_DECISIONS} not found")
        sys.exit(1)

    text = LODE_DECISIONS.read_text(encoding="utf-8")
    store = VeinStore(VEIN_ROOT)

    # existing (source, title) pairs for idempotent dedup
    existing = {
        (e.source, e.title.strip())
        for e in store.iter_entries()
    }

    staged: list[Entry] = []

    # 1. 🔴/🟡 pitfall blocks
    for title, body in parse_heading_pitfalls(text):
        staged.append(Entry.make(
            type="pitfall", title=title, body=body,
            tags=[PROJECT, "lode-pitfall", "雷"],
            source=SOURCE, volatility=VOLATILITY,
        ))

    # 2. architecture decisions table
    for cells in parse_table(text, "架構決策"):
        if len(cells) < 2:
            continue
        decision, reason = cells[0], cells[1]
        title = (decision[:78] + "…") if len(decision) > 80 else decision
        body = f"{decision}\n\n**Why:** {reason}"
        staged.append(Entry.make(
            type="decision", title=title, body=body,
            tags=[PROJECT, "lode-decision", "架構決策"],
            source=SOURCE, volatility=VOLATILITY,
        ))

    # 3. known-issues table → pitfalls
    for cells in parse_table(text, "已知問題"):
        if len(cells) < 3:
            continue
        problem, where, note = cells[0], cells[1], cells[2]
        body = f"**Where:** `{where}`\n\n{note}"
        staged.append(Entry.make(
            type="pitfall", title=problem, body=body,
            tags=[PROJECT, "lode-known-issue", "雷"],
            source=SOURCE, volatility=VOLATILITY,
        ))

    # write (skip dupes)
    written = skipped = 0
    for e in staged:
        if (e.source, e.title.strip()) in existing:
            skipped += 1
            continue
        store.write_entry(e)
        existing.add((e.source, e.title.strip()))
        written += 1
        print(f"  + [{e.type:8}] {e.title[:64]}")

    print(f"\nParsed {len(staged)} candidates → wrote {written}, skipped {skipped} (dupes).")

    # reindex so FTS/semantic search can see them
    vein = shutil.which("vein")
    if vein:
        print("Reindexing ...")
        subprocess.run([vein, "reindex"], cwd=str(VEIN_ROOT))
    else:
        print(f"Now run:  cd {VEIN_ROOT} && vein reindex")

    print('\nVerify:  vein recall "read_to_end take cap growing file"')
    print('         vein recall "monaco setValue cursor reset"')


if __name__ == "__main__":
    main()
