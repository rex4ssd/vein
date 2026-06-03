#!/usr/bin/env python3
"""
prune_noise.py — Delete low-signal auto-fetch noise from Vein's .vein/ store.

Categories (approved 2026-06-02):
  A  IINA symbol dumps        title starts "Swift/iina"
  B  GitHub auto-fetch        tags contain BOTH `fetch` and `github`
                              (README overviews + fake decision/pitfall/lore)
  C  comparison stubs         tag `auto`
  D  empty/broken entries     body < 15 chars after frontmatter

SAFETY NET: never deletes entries whose source is `lode:docs/decisions.md`
(the real Lode lore just imported), regardless of category match.

Default is DRY-RUN. Nothing is deleted until you pass --yes.

  cd /Users/lion/Documents/vein && python3 shell/prune_noise.py            # preview
  cd /Users/lion/Documents/vein && python3 shell/prune_noise.py --yes      # delete
  ... --categories AB        # only prune A and B
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

VEIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(VEIN_ROOT / "src"))

from vein.core.store import VeinStore   # noqa: E402

PROTECTED_SOURCES = {"lode:docs/decisions.md"}


def classify(entry) -> str | None:
    """Return category letter A/B/C/D if entry is noise, else None."""
    if entry.source in PROTECTED_SOURCES:
        return None
    tags = set(entry.tags or [])
    title = (entry.title or "").strip()
    body_len = len((entry.body or "").strip())

    if title.startswith("Swift/iina"):
        return "A"
    if {"fetch", "github"} <= tags:
        return "B"
    if "auto" in tags:
        return "C"
    if body_len < 15:
        return "D"
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="actually delete (default: dry-run)")
    ap.add_argument("--categories", default="ABCD",
                    help="subset of A/B/C/D to prune (default all)")
    args = ap.parse_args()
    wanted = {c for c in args.categories.upper() if c in "ABCD"}

    store = VeinStore(VEIN_ROOT)

    buckets: dict[str, list] = {c: [] for c in "ABCD"}
    for e in store.iter_entries():
        cat = classify(e)
        if cat and cat in wanted:
            buckets[cat].append(e)

    labels = {
        "A": "IINA symbol dumps",
        "B": "GitHub auto-fetch (README/fake decision-pitfall-lore)",
        "C": "comparison stubs",
        "D": "empty/broken entries",
    }

    total = 0
    mode = "DELETING" if args.yes else "DRY-RUN (nothing deleted)"
    print(f"=== prune_noise — {mode} ===\n")
    for c in "ABCD":
        if c not in wanted:
            continue
        items = buckets[c]
        print(f"[{c}] {labels[c]} — {len(items)}")
        for e in items:
            print(f"     {e.type:9} {e.title[:60]}")
            if args.yes and e._path and Path(e._path).exists():
                Path(e._path).unlink()
        total += len(items)
        print()

    print(f"Total: {total} entries")
    if not args.yes:
        print("\nThis was a DRY-RUN. Re-run with --yes to delete.")
        return

    # reindex after deletion
    vein = shutil.which("vein")
    if vein:
        print("Reindexing ...")
        subprocess.run([vein, "reindex"], cwd=str(VEIN_ROOT))
    else:
        print(f"Now run:  cd {VEIN_ROOT} && vein reindex")
    print(f"\nDone. Verify counts:  vein status")


if __name__ == "__main__":
    main()
