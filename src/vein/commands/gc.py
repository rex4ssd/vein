"""vein gc — garbage-collect .vein/ entries.

Usage:
  vein gc --dry-run                       # show what would be deleted
  vein gc --stale                         # delete entries past volatility TTL
  vein gc --older-than 60                 # delete entries older than 60 days
  vein gc --collection study_llm          # purge a whole collection
  vein gc --collection study_llm --keep-compare   # keep compare summary
  vein gc --type reference                # only reference entries
  vein gc --committed --older-than 7      # safe: only git-committed entries

Design:
  - Entries are never modified, only deleted.
  - --dry-run always safe; --committed adds a git-check guard.
  - After deletion, the SQLite index is updated automatically (store.delete_entry).
  - Run `vein reindex` after large gc runs to compact the index.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ..core.models import VOLATILITY_TTL_DAYS, EntryType
from ..core.store import VeinStore

console = Console()


# ── git-committed guard ───────────────────────────────────────────────────────

def _is_committed(path: Path, repo_root: Path) -> bool:
    """Return True if the file is tracked and committed in git (not modified)."""
    try:
        rel = path.relative_to(repo_root)
        # git ls-files --error-unmatch: exits 0 if tracked, 1 if not
        r = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(rel)],
            cwd=repo_root, capture_output=True, timeout=5,
        )
        if r.returncode != 0:
            return False
        # check if modified (staged or unstaged)
        r2 = subprocess.run(
            ["git", "status", "--porcelain", str(rel)],
            cwd=repo_root, capture_output=True, text=True, timeout=5,
        )
        return r2.stdout.strip() == ""   # empty = clean
    except Exception:
        return False


# ── command ───────────────────────────────────────────────────────────────────

@click.command("gc")
@click.option("--dry-run",   is_flag=True,
              help="Show what would be deleted without deleting")
@click.option("--stale",     is_flag=True,
              help="Delete entries past their volatility TTL")
@click.option("--older-than", "older_than", default=0, type=int, metavar="DAYS",
              help="Delete entries older than N days")
@click.option("--collection", default="",
              help="Limit to a study collection (tag: study:NAME)")
@click.option("--keep-compare", is_flag=True,
              help="When --collection is set, keep the compare summary entry")
@click.option("--type", "entry_type", default="",
              type=click.Choice(["", "decision", "lore", "pitfall", "reference"]),
              help="Limit to a specific entry type")
@click.option("--committed",  is_flag=True,
              help="Only delete entries that are committed to git (safe guard)")
@click.option("--yes", "-y",  is_flag=True,
              help="Skip confirmation prompt")
def cmd_gc(
    dry_run: bool,
    stale: bool,
    older_than: int,
    collection: str,
    keep_compare: bool,
    entry_type: str,
    committed: bool,
    yes: bool,
) -> None:
    """Garbage-collect .vein/ entries to reclaim disk space.

    \b
    Examples:
      vein gc --dry-run                        # preview everything
      vein gc --collection study_llm --keep-compare  # purge raw, keep summary
      vein gc --stale --dry-run                # show entries past TTL
      vein gc --older-than 90 --type reference # purge old reference entries
      vein gc --committed --older-than 30      # safe: only remove git-committed
    """
    if not any([stale, older_than, collection]):
        console.print(
            "[yellow]Nothing to do.[/] Specify at least one filter:\n"
            "  --stale, --older-than N, --collection NAME, --type T"
        )
        raise SystemExit(0)

    store = VeinStore.require()
    now   = datetime.now(timezone.utc)

    all_entries = store.list_entries(
        type_filter=entry_type or None,      # type: ignore[arg-type]
        status_filter=None,
    )

    # ── filter ────────────────────────────────────────────────────────────────
    candidates = []
    for e in all_entries:
        # collection filter
        if collection:
            coll_tag = f"study:{collection}"
            if coll_tag not in e.tags:
                continue
            # --keep-compare: skip the summary entry
            if keep_compare and e.source.startswith(f"study:compare:"):
                continue

        # stale filter
        if stale and not e.is_stale:
            continue

        # age filter
        if older_than:
            age = (now - e.date.replace(tzinfo=timezone.utc)
                   if e.date.tzinfo is None else now - e.date).days
            if age < older_than:
                continue

        # --committed guard
        if committed:
            path = e._path
            if path is None:
                from ..core.store import ENTRY_DIRS
                subdir = ENTRY_DIRS.get(e.type, "lore")
                path = store.vein_dir / subdir / f"{e.id}.md"
            if not _is_committed(path, store.root):
                continue

        candidates.append(e)

    if not candidates:
        console.print("[dim]No entries match the given filters.[/]")
        return

    # ── display ───────────────────────────────────────────────────────────────
    table = Table(show_header=True, header_style="bold dim")
    table.add_column("Type",  style="dim", max_width=10)
    table.add_column("Title", max_width=55)
    table.add_column("Age",   style="dim", max_width=8)
    table.add_column("Tags",  style="dim", max_width=30)

    for e in candidates:
        age_days = (now - (e.date.replace(tzinfo=timezone.utc)
                           if e.date.tzinfo is None else e.date)).days
        tag_str  = ", ".join(t for t in e.tags if not t.startswith("source:"))[:30]
        table.add_row(e.type, e.title[:55], f"{age_days}d", tag_str)

    console.print(f"\n[bold]{len(candidates)}[/] entries selected for deletion"
                  + (" [dim](dry-run)[/]" if dry_run else "") + ":\n")
    console.print(table)

    if dry_run:
        return

    # ── confirm + delete ─────────────────────────────────────────────────────
    if not yes:
        click.confirm(f"\nDelete {len(candidates)} entries?", abort=True)

    deleted = sum(1 for e in candidates if store.delete_entry(e))
    console.print(f"\n[green]✓[/] Deleted {deleted} entries.")
    if deleted:
        console.print("[dim]Run [bold]vein reindex[/] to compact the search index.[/]")
