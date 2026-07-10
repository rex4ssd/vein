#!/usr/bin/env python3
"""vein_inbox_sync.py — batch-ingest per-repo VEIN_INBOX.md into the central .vein/ store.

WHY THIS EXISTS
---------------
Capturing lore via the vein MCP tool (vein_log) keeps the tool result in the
LLM context for the rest of the session — that was ~16% of recent usage.
Instead: during work, just APPEND plain text to each repo's own
`VEIN_INBOX.md` (zero context cost). This script, run once a day OUTSIDE any
LLM session, parses those inboxes, writes proper vein entry files into the
central store, then archives the inbox so nothing is re-imported.

    Lode finds the code. Vein remembers the why — this just batches the writing.

ZERO external deps. Pure stdlib. Python 3.9+.

INBOX FORMAT  (VEIN_INBOX.md)
-----------------------------
Each entry starts with a line `## <type> | <title>`. Then optional
`key: value` metadata lines, a blank line, then the body (verbatim).

    ## decision | DMA API uses callback not polling
    tags: dma, hal, callback
    related: 20260526-120000
    volatility: internal-invariant

    Why: SystemC DMA model is event-driven; polling would busy-wait.
    Trade-off: callbacks need careful ISR context management.

    ## pitfall | notarize staple fails on .dmg without --deep
    tags: notarize, codesign, dmg

    Symptom: stapler validate rejects the dmg.
    Root cause: nested .app not signed with --deep.
    Fix: codesign --deep --force before notarytool submit.

  - type ∈ {decision, lore, pitfall, reference}. Missing/unknown -> lore.
  - title optional; if omitted, derived from the first body line.
  - tags: comma-separated. `project:<repo>` is prepended automatically.
  - recognised metadata keys: tags, related, source_url, source_title, volatility, status

USAGE
-----
    python3 vein_inbox_sync.py                 # sync all repos in REPOS
    python3 vein_inbox_sync.py --dry-run       # parse + print, write nothing
    python3 vein_inbox_sync.py --init <path>   # drop a starter VEIN_INBOX.md in a repo
    python3 vein_inbox_sync.py --repo <path>   # sync just one repo (project = folder name)

Edit the REPOS list below to match your machine.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────
# Central vein store (where entry files are written).
VEIN_STORE = Path("/Users/lion/Documents/vein/.vein")

# Repos whose VEIN_INBOX.md should be ingested. project name = folder name,
# unless overridden with a (path, "project-name") tuple.
REPOS: list = [
    "/Users/lion/Documents/vein",
    "/Users/lion/Documents/lode",
    "/Users/lion/Documents/fubon_stock",
    "/Users/lion/Documents/py",
    # ("/Users/lion/Documents/some-repo", "custom-project-tag"),
]

INBOX_NAME = "VEIN_INBOX.md"
ARCHIVE_DIR = ".vein_inbox_archive"   # created inside each repo
VALID_TYPES = {"decision", "lore", "pitfall", "reference"}
META_KEYS = {"tags", "related", "source_url", "source_title", "volatility", "status"}

INBOX_TEMPLATE = """# VEIN_INBOX — append lore here; synced to the central .vein/ daily.
#
# One entry per `## <type> | <title>` block. type = decision|lore|pitfall|reference.
# Optional metadata lines (tags: a, b, c / related: <id> / volatility: ...),
# blank line, then the body. Everything is archived after sync.

"""


# ── PARSING ─────────────────────────────────────────────────────────────────
_ENTRY_RE = re.compile(r"^##\s+(.*)$", re.MULTILINE)


def parse_inbox(text: str) -> list[dict]:
    """Split an inbox into entry dicts: {type, title, meta{}, body}."""
    # strip comment/blank lines that are not entry headers from the preamble only;
    # entry bodies are kept verbatim.
    starts = [m.start() for m in _ENTRY_RE.finditer(text)]
    entries: list[dict] = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        block = text[start:end].strip()
        entry = _parse_block(block)
        if entry:
            entries.append(entry)
    return entries


def _parse_block(block: str) -> dict | None:
    lines = block.splitlines()
    header = lines[0][2:].strip()  # drop leading "##"
    if "|" in header:
        type_part, title = (s.strip() for s in header.split("|", 1))
    else:
        type_part, title = header.strip(), ""
    etype = type_part.lower()
    if etype not in VALID_TYPES:
        # header was probably just a title; treat whole header as title, type=lore
        title = title or header.strip()
        etype = "lore"

    meta: dict[str, str] = {}
    body_start = 1
    for j in range(1, len(lines)):
        ln = lines[j]
        if not ln.strip():
            body_start = j + 1
            break
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", ln)
        if m and m.group(1).lower() in META_KEYS:
            meta[m.group(1).lower()] = m.group(2).strip()
            body_start = j + 1
        else:
            body_start = j
            break

    body = "\n".join(lines[body_start:]).strip()
    if not body and not title:
        return None
    if not title:
        first = body.splitlines()[0] if body else "untitled"
        first = re.sub(r"^[*_#>\s-]+", "", first)
        title = (first[:80]).strip() or "untitled"
    return {"type": etype, "title": title, "meta": meta, "body": body}


# ── WRITING ───────────────────────────────────────────────────────────────
def make_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def y(s: str) -> str:
    """Emit a YAML scalar safely (JSON is a valid YAML flow scalar)."""
    return json.dumps(s, ensure_ascii=False)


def render_entry(entry: dict, project: str, entry_id: str) -> str:
    meta = entry["meta"]
    raw_tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    tags = [f"project:{project}"] + [t for t in raw_tags if t != f"project:{project}"]
    related = [r.strip() for r in meta.get("related", "").split(",") if r.strip()]
    now = datetime.now().astimezone().isoformat()

    fm = ["---", f"id: {entry_id}", f"type: {entry['type']}", f"title: {y(entry['title'])}"]
    fm.append("tags:")
    fm += [f"- {y(t)}" for t in tags]
    fm.append(f"date: {y(now)}")
    fm.append("source: inbox")
    if meta.get("source_url"):
        fm.append(f"source_url: {y(meta['source_url'])}")
    if meta.get("source_title"):
        fm.append(f"source_title: {y(meta['source_title'])}")
    if related:
        fm.append("related:")
        fm += [f"- {r}" for r in related]
    if meta.get("status"):
        fm.append(f"status: {meta['status']}")
    if meta.get("volatility"):
        fm.append(f"volatility: {meta['volatility']}")
    fm.append("---")
    return "\n".join(fm) + "\n\n" + entry["body"] + "\n"


# ── SYNC ──────────────────────────────────────────────────────────────────
def resolve_repos(repo_arg: str | None) -> list[tuple[Path, str]]:
    src = [repo_arg] if repo_arg else REPOS
    out: list[tuple[Path, str]] = []
    for item in src:
        if isinstance(item, (tuple, list)):
            path, project = Path(item[0]), item[1]
        else:
            path = Path(item)
            project = path.name
        out.append((path.resolve(), project))
    return out


def sync_repo(repo: Path, project: str, dry_run: bool) -> int:
    inbox = repo / INBOX_NAME
    if not inbox.exists():
        return 0
    text = inbox.read_text(encoding="utf-8")
    entries = parse_inbox(text)
    if not entries:
        return 0

    written = []
    for entry in entries:
        eid = make_id()
        subdir = VEIN_STORE / (entry["type"] + "s")  # decisions/lore/pitfalls/references
        # lore -> "lores"? no: dirs are decisions/lore/pitfalls/references
        dirname = {"decision": "decisions", "lore": "lore",
                   "pitfall": "pitfalls", "reference": "references"}[entry["type"]]
        subdir = VEIN_STORE / dirname
        target = subdir / f"{eid}.md"
        rendered = render_entry(entry, project, eid)
        print(f"  [{entry['type']:9}] {entry['title'][:70]}  -> {dirname}/{eid}.md")
        if not dry_run:
            subdir.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
        written.append(target)

    if not dry_run:
        # archive the whole inbox, then reset to template (idempotent: nothing re-imports)
        adir = repo / ARCHIVE_DIR
        adir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(inbox, adir / f"{stamp}.md")
        inbox.write_text(INBOX_TEMPLATE, encoding="utf-8")

    return len(entries)


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync per-repo VEIN_INBOX.md into the central .vein/ store.")
    ap.add_argument("--dry-run", action="store_true", help="parse and print, write nothing")
    ap.add_argument("--repo", help="sync only this repo path (project = folder name)")
    ap.add_argument("--init", metavar="PATH", help="drop a starter VEIN_INBOX.md into PATH and exit")
    args = ap.parse_args()

    if args.init:
        p = Path(args.init).resolve() / INBOX_NAME
        if p.exists():
            print(f"already exists: {p}")
        else:
            p.write_text(INBOX_TEMPLATE, encoding="utf-8")
            print(f"created: {p}")
        return 0

    if not VEIN_STORE.exists() and not args.dry_run:
        print(f"ERROR: central store not found: {VEIN_STORE}", file=sys.stderr)
        return 1

    total = 0
    for repo, project in resolve_repos(args.repo):
        if not repo.exists():
            continue
        n = sync_repo(repo, project, args.dry_run)
        if n:
            print(f"{repo.name}: {n} entr{'y' if n == 1 else 'ies'}"
                  f"{' (dry-run)' if args.dry_run else ''}")
        total += n

    tag = " (dry-run, nothing written)" if args.dry_run else ""
    print(f"\nDone. {total} entr{'y' if total == 1 else 'ies'} synced{tag}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
