#!/usr/bin/env python3
"""
migrate_lode_to_vein.py

把 Lode repo 裡 source=lode-retrospective-2026 的 entries
搬到 Vein 自己的 .vein/，並加上 project:lode tag。

使用方式：
  python3 /Users/lion/Documents/vein/shell/migrate_lode_to_vein.py

執行後：
  1. 24 條 lore 進 /Users/lion/Documents/vein/.vein/
  2. Lode .vein/ 的這些 entries 被移除
  3. vein reindex (在 vein 目錄) 讓 FTS 更新
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone

VEIN_SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(VEIN_SRC))

from vein.core.store import VeinStore
from vein.core.models import Entry

LODE_VEIN_DIR  = Path("/Users/lion/Documents/lode/.vein")
VEIN_VEIN_DIR  = Path("/Users/lion/Documents/vein")

SOURCES_TO_MIGRATE = {
    "lode-retrospective-2026",
    "lode-retrospective-2026-addendum",
}

PROJECT_TAG = "project:lode"


def add_project_tag(tags: list[str], project: str) -> list[str]:
    """Ensure project:xxx is the first tag."""
    tags = [t for t in tags if not t.startswith("project:")]
    return [project] + tags


def main():
    if not LODE_VEIN_DIR.exists():
        print(f"ERROR: {LODE_VEIN_DIR} not found. Run from correct location.")
        sys.exit(1)

    dest_store = VeinStore(VEIN_VEIN_DIR)

    migrated = 0
    skipped  = 0
    removed  = []

    type_dirs = ["decisions", "lore", "pitfalls", "references"]

    for type_dir in type_dirs:
        src_dir = LODE_VEIN_DIR / type_dir
        if not src_dir.exists():
            continue

        for md_file in sorted(src_dir.glob("*.md")):
            raw = md_file.read_text(encoding="utf-8")

            # parse frontmatter
            if not raw.startswith("---"):
                skipped += 1
                continue

            parts = raw.split("---", 2)
            if len(parts) < 3:
                skipped += 1
                continue

            try:
                import yaml
                fm = yaml.safe_load(parts[1])
            except Exception:
                skipped += 1
                continue

            source = fm.get("source", "")
            if source not in SOURCES_TO_MIGRATE:
                skipped += 1
                continue

            # build Entry from the parsed frontmatter + body
            body = parts[2].strip()
            tags = add_project_tag(fm.get("tags") or [], PROJECT_TAG)

            raw_date = fm.get("date")
            if isinstance(raw_date, str):
                try:
                    from datetime import datetime
                    parsed_date = datetime.fromisoformat(raw_date)
                except Exception:
                    parsed_date = datetime.now(timezone.utc)
            elif isinstance(raw_date, datetime):
                parsed_date = raw_date
            else:
                parsed_date = datetime.now(timezone.utc)

            entry = Entry(
                id=fm.get("id", Entry.new_id()),
                type=fm.get("type", type_dir.rstrip("s")),
                title=fm.get("title", ""),
                tags=tags,
                body=body,
                date=parsed_date,
                source=source,
                source_url=fm.get("source_url", ""),
                source_title=fm.get("source_title", ""),
                status=fm.get("status", "active"),
                related=fm.get("related") or [],
                volatility=fm.get("volatility", "unknown"),
                superseded_by=fm.get("superseded_by", ""),
            )

            dest_store.write_entry(entry)
            removed.append(md_file)
            migrated += 1
            print(f"  ✓ [{entry.type:8}] {entry.title[:60]}")

    print(f"\nMigrated {migrated} entries to {VEIN_VEIN_DIR}/.vein/")
    print(f"Skipped  {skipped} (not from lode-retrospective source)")

    # remove from lode .vein/
    if removed:
        print(f"\nRemoving {len(removed)} source files from {LODE_VEIN_DIR}...")
        for f in removed:
            f.unlink()
            print(f"  rm {f.relative_to(LODE_VEIN_DIR.parent)}")

    print("\nDone. Next steps:")
    print("  cd /Users/lion/Documents/vein && vein reindex")
    print("  vein recall 'project:lode app store'")
    print("  vein recall 'cloudflare'")


if __name__ == "__main__":
    main()
