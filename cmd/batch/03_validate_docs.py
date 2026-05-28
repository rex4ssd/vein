#!/usr/bin/env python3
"""03_validate_docs.py — sanity check on docs/ markdown files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # PROJECT_ROOT

ERRORS: list[str] = []


def check_decisions(path: Path) -> None:
    """decisions.md: verify D-xxx entries have a date line."""
    text = path.read_text(encoding="utf-8")
    entries = re.findall(r"^### (D-\d+) —", text, re.MULTILINE)
    for entry_id in entries:
        # check that **Date:** follows within 10 lines
        pattern = rf"### {re.escape(entry_id)} —.+?\n(\*\*Date:\*\*)"
        if not re.search(pattern, text, re.DOTALL):
            ERRORS.append(f"decisions.md: {entry_id} missing **Date:** field")


def check_no_html_in_md(docs_dir: Path) -> None:
    """No raw HTML tags in docs/ markdown (same rule as py/ daily reports)."""
    for md in docs_dir.rglob("*.md"):
        if "docs_cloudflare" in str(md):
            continue  # public docs may use HTML
        text = md.read_text(encoding="utf-8")
        hits = re.findall(r"<(?!--)[a-zA-Z/][^>]*>", text)
        if hits:
            ERRORS.append(f"{md.relative_to(ROOT)}: HTML tags found: {hits[:3]}")


def check_ai_providers_yaml(path: Path) -> None:
    """config/ai_providers.yaml must be valid YAML."""
    try:
        import yaml
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        ERRORS.append(f"ai_providers.yaml: invalid YAML: {e}")


def main() -> int:
    print("[03] validate docs")

    decisions = ROOT / "docs" / "decisions.md"
    if decisions.exists():
        check_decisions(decisions)

    docs_dir = ROOT / "docs"
    if docs_dir.exists():
        check_no_html_in_md(docs_dir)

    ai_yaml = ROOT / "config" / "ai_providers.yaml"
    if ai_yaml.exists():
        check_ai_providers_yaml(ai_yaml)
    else:
        print("  config/ai_providers.yaml not found — skip")

    if ERRORS:
        print(f"\n[03] FAILED — {len(ERRORS)} error(s):")
        for e in ERRORS:
            print(f"  ✗ {e}")
        return 1

    print(f"[03] validate OK — no errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
