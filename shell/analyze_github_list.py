#!/usr/bin/env python3
"""
analyze_github_list.py — Parse a GitHub repo list markdown → vein fetch + study compare.

Parses markdown files like:
  **App 類**
  - [IINA](https://github.com/iina/iina) — macOS 影片播放器
  - [Stats](https://github.com/exelban/stats) — menu bar 監控

For each repo:
  1. vein fetch owner/repo  (skip if already fetched, use --force to refresh)
  2. vein study compare <category>  (per category, if 2+ repos)

Usage:
  python3 shell/analyze_github_list.py docs/Ref_resources/github_260602.md
  python3 shell/analyze_github_list.py docs/Ref_resources/github_260602.md --dry-run
  python3 shell/analyze_github_list.py docs/Ref_resources/github_260602.md --force
  python3 shell/analyze_github_list.py docs/Ref_resources/github_260602.md --no-compare
  python3 shell/analyze_github_list.py docs/Ref_resources/github_260602.md --category "App 類"
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from vein.core.store import VeinStore

# ── parse markdown ────────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^\*\*(.+?)\*\*\s*$")
_REPO_RE    = re.compile(r"\[.+?\]\(https://github\.com/([\w.\-]+/[\w.\-]+)\)")


def parse_md(path: Path) -> dict[str, list[str]]:
    """
    Returns { category: [slug, ...] } preserving order.
    Also returns { "_all": [slug, ...] } for repos with no category heading.
    """
    categories: dict[str, list[str]] = {}
    current = "_all"
    categories[current] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        h = _HEADING_RE.match(line.strip())
        if h:
            current = h.group(1).strip()
            categories.setdefault(current, [])
            continue
        for slug in _REPO_RE.findall(line):
            categories[current].append(slug)

    # remove empty buckets
    return {k: v for k, v in categories.items() if v}


# ── vein wrappers ─────────────────────────────────────────────────────────────

def _vein(*args: str) -> int:
    """Run vein CLI; returns exit code."""
    cmd = [sys.executable, "-m", "vein"] + list(args)
    env = {"PYTHONPATH": str(_REPO_ROOT / "src")}
    import os
    env.update(os.environ)
    result = subprocess.run(cmd, env=env)
    return result.returncode


def already_fetched(store: VeinStore, slug: str) -> int:
    """Return count of existing entries for this slug."""
    tag = f"source:github/{slug}"
    return sum(1 for e in store.iter_entries() if tag in e.tags)


def slug_to_collection(category: str) -> str:
    """Convert category name to a safe collection name for vein study."""
    return re.sub(r"[^\w]", "_", category).strip("_").lower()


# ── main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", type=Path, help="Markdown file with GitHub repo list")
    p.add_argument("--dry-run", action="store_true",
                   help="Print plan, don't run anything")
    p.add_argument("--force", action="store_true",
                   help="Re-fetch even if already in .vein/")
    p.add_argument("--no-compare", action="store_true",
                   help="Skip vein study compare step")
    p.add_argument("--category", default="",
                   help="Only process this category (partial match ok)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    md_path = args.file if args.file.is_absolute() else _REPO_ROOT / args.file
    if not md_path.exists():
        print(f"[error] file not found: {md_path}")
        sys.exit(1)

    store = VeinStore.require()
    categories = parse_md(md_path)

    # category filter
    if args.category:
        categories = {k: v for k, v in categories.items()
                      if args.category.lower() in k.lower()}
        if not categories:
            print(f"[warn] no category matching '{args.category}'")
            sys.exit(0)

    # summary
    total = sum(len(v) for v in categories.values())
    print(f"Found {total} repos in {len(categories)} categor{'y' if len(categories)==1 else 'ies'}:\n")
    for cat, slugs in categories.items():
        print(f"  [{cat}]")
        for slug in slugs:
            n = already_fetched(store, slug)
            status = f"already fetched ({n})" if n else "new"
            print(f"    {slug:<45} {status}")
    print()

    if args.dry_run:
        print("Dry run — exiting.")
        return

    # ── fetch ──────────────────────────────────────────────────────────────────
    fetch_ok:   list[tuple[str, str]] = []   # (category, slug)
    fetch_skip: list[str]             = []
    fetch_fail: list[str]             = []

    for cat, slugs in categories.items():
        col = slug_to_collection(cat)
        print(f"\n{'═'*55}")
        print(f"  {cat}  →  collection: {col}")
        print(f"{'═'*55}")

        for slug in slugs:
            n = already_fetched(store, slug)
            if n and not args.force:
                print(f"  [skip] {slug} ({n} entries, use --force to re-fetch)")
                fetch_skip.append(slug)
                continue

            print(f"\n  → fetch: {slug}")
            extra = ["--force"] if (n and args.force) else []
            rc = _vein("fetch", slug, "--tag", f"study:{col}", "--tag", cat, *extra)
            if rc == 0:
                fetch_ok.append((cat, slug))
            else:
                fetch_fail.append(slug)

    # ── study compare ──────────────────────────────────────────────────────────
    if not args.no_compare:
        print(f"\n{'═'*55}")
        print("  vein study compare (per category)")
        print(f"{'═'*55}")

        for cat, slugs in categories.items():
            col = slug_to_collection(cat)
            # only compare if ≥2 repos were fetched (or already exist)
            available = [s for s in slugs if already_fetched(store, s) or
                         any(c == cat and sl == s for c, sl in fetch_ok)]
            if len(available) < 2:
                print(f"\n  [{cat}] only {len(available)} repo(s) — skipping compare")
                continue
            print(f"\n  [{cat}] comparing {len(available)} repos…")
            _vein("study", "compare", col)

    # ── summary ────────────────────────────────────────────────────────────────
    print(f"\n{'═'*55}")
    print(f"Done.")
    print(f"  fetched:  {len(fetch_ok)}")
    print(f"  skipped:  {len(fetch_skip)}")
    print(f"  failed:   {len(fetch_fail)}")
    if fetch_fail:
        print(f"  failures: {', '.join(fetch_fail)}")
    print(f"\nRecall:")
    for cat in categories:
        col = slug_to_collection(cat)
        print(f"  vein recall \"{col}\"")


if __name__ == "__main__":
    main()
