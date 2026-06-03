#!/usr/bin/env python3
"""
import_project_lore.py — Generic markdown → vein importer for ANY project.

Generalises import_lode_decisions.py: point it at any project's lore doc,
split on a heading level, import each block as a tagged vein entry.

Each `<heading> Title` block → one entry; body = text until the next
same-or-shallower heading. Leading markers in titles are stripped
(status emoji, `Pn —`, `D-nnn`).

IDEMPOTENT: dedup by (source, title). Re-run after editing the doc to add
only new blocks.

Examples:
  # lode_iphone pitfalls (## Pn — ... format)
  python3 shell/import_project_lore.py \\
      --project lode-iphone --type pitfall --heading "##" \\
      --file ~/Documents/lode_iphone/docs/PITFALLS.md

  # SunnyWalker alarm-app spec questions (as reference)
  python3 shell/import_project_lore.py \\
      --project sunnywalker --type reference --heading "##" \\
      --file ~/Documents/SunnyWalker/docs/plan/validation_rule_260602.md

  # lode-style ### 🔴 blocks
  python3 shell/import_project_lore.py \\
      --project lode --type pitfall --heading "###" \\
      --file ~/Documents/lode/docs/decisions.md
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

VEIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(VEIN_ROOT / "src"))

from vein.core.store import VeinStore   # noqa: E402
from vein.core.models import Entry      # noqa: E402

# titles that are section headers, not real entries
GENERIC_TITLES = {"修復清單", "修復", "Bug", "Known Issue", "目錄", "Overview"}

# strip leading markers: status emoji, "P12 —", "D-007:", numbering
_MARKER_RE = re.compile(r"^(?:🔴|🟡|🟢|⛔|⚠️|✅)?\s*(?:P\d+|D-\d+|\d+)\s*[—\-：:.]\s*", )


def strip_marker(title: str) -> str:
    t = re.sub(r"^(?:🔴|🟡|🟢|⛔|⚠️|✅)\s*", "", title).strip()
    t = _MARKER_RE.sub("", t).strip()
    return t or title.strip()


def parse_blocks(text: str, heading: str) -> list[tuple[str, str]]:
    """Split on exact heading level (## or ###). Body until next heading of
    that level OR shallower."""
    level = len(heading)
    # match the target heading level exactly (not deeper)
    pat = re.compile(rf"^#{{{level}}}[ \t]+(.+?)[ \t]*$", re.M)
    # any heading of level<=target bounds a block
    bound = re.compile(rf"^#{{1,{level}}}[ \t]+", re.M)

    out: list[tuple[str, str]] = []
    ms = list(pat.finditer(text))
    for i, m in enumerate(ms):
        title = strip_marker(m.group(1))
        if not title or title in GENERIC_TITLES:
            continue
        start = m.end()
        end = len(text)
        nb = bound.search(text, start)
        if nb:
            end = nb.start()
        body = text[start:end].strip()
        if len(body) < 20:
            continue
        out.append((title, body))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="project slug → project:<slug> tag")
    ap.add_argument("--file", required=True, help="markdown file to import")
    ap.add_argument("--type", default="pitfall",
                    choices=["decision", "lore", "pitfall", "reference"])
    ap.add_argument("--heading", default="##", choices=["##", "###"],
                    help="heading level that delimits one entry")
    ap.add_argument("--tag", action="append", default=[], help="extra tag (repeatable)")
    ap.add_argument("--volatility", default="internal-invariant",
                    choices=["internal-invariant", "external-fact", "unknown"])
    ap.add_argument("--source", default="", help="source label (default: project:<file>)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.file).expanduser()
    if not path.exists():
        print(f"[error] {path} not found"); sys.exit(1)

    project_tag = f"project:{args.project}"
    source = args.source or f"{args.project}:{path.name}"
    text = path.read_text(encoding="utf-8")
    blocks = parse_blocks(text, args.heading)

    store = VeinStore(VEIN_ROOT)
    existing = {(e.source, e.title.strip()) for e in store.iter_entries()}

    tags = [project_tag, args.type, *args.tag]
    written = skipped = 0
    print(f"=== import {len(blocks)} blocks from {path.name} "
          f"→ project:{args.project} ({args.type}) "
          f"{'[DRY-RUN]' if args.dry_run else ''} ===\n")
    for title, body in blocks:
        if (source, title.strip()) in existing:
            skipped += 1
            continue
        print(f"  + {title[:64]}")
        if not args.dry_run:
            e = Entry.make(type=args.type, title=title, body=body, tags=tags,
                           source=source, volatility=args.volatility)
            store.write_entry(e)
            existing.add((source, title.strip()))
        written += 1

    print(f"\n{'would write' if args.dry_run else 'wrote'} {written}, skipped {skipped} (dupes).")
    if args.dry_run:
        print("Re-run without --dry-run to import.")
        return

    vein = shutil.which("vein")
    if vein:
        print("Reindexing ...")
        subprocess.run([vein, "reindex"], cwd=str(VEIN_ROOT))
    else:
        print(f"Now run:  cd {VEIN_ROOT} && vein reindex")
    print(f'\nVerify:  vein recall "..." (entries tagged {project_tag})')


if __name__ == "__main__":
    main()
