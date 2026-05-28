"""vein import — batch-import entries from existing docs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import track

from ..core.models import Entry, EntryType
from ..core.store import VeinStore

console = Console()

# ── decisions.md parser ───────────────────────────────────────────
# Matches:   ### D-017 — Title here
_D_HEADER = re.compile(r"^#{2,4}\s+D-\d+\s*[—–-]+\s*(.+)$", re.MULTILINE)
_D_BLOCK   = re.compile(
    r"^#{2,4}\s+D-\d+\s*[—–-]+\s*(.+?)\n(.*?)(?=^#{2,4}\s+D-\d+|^#{1,2}\s|\Z)",
    re.DOTALL | re.MULTILINE,
)


def _classify_decision_body(body: str) -> EntryType:
    """Heuristic: look for pitfall keywords."""
    low = body.lower()
    if any(w in low for w in ("雷", "pitfall", "bug", "fail", "broken", "symptom", "root cause")):
        return "pitfall"
    return "decision"


def _parse_decisions_md(path: Path) -> list[dict]:
    """
    Parse docs/decisions.md style:
      ### D-001 — Title
      **Date:** 2026-05-26
      body...
    Returns list of dicts: {title, type, tags, body, date_hint}
    """
    text = path.read_text(encoding="utf-8")
    entries = []

    for m in _D_BLOCK.finditer(text):
        raw_title = m.group(1).strip()
        raw_body  = m.group(2).strip()
        if not raw_title or not raw_body:
            continue

        # extract date from **Date:** line
        date_hint = None
        dm = re.search(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", raw_body)
        if dm:
            date_hint = dm.group(1)
            # remove the Date line from body
            raw_body = re.sub(r"\*\*Date:\*\*\s*\S+\n?", "", raw_body).strip()

        entry_type = _classify_decision_body(raw_body)

        # auto-extract tags from **Tags:** line if present
        tags: list[str] = []
        tm = re.search(r"\*\*Tags?:\*\*\s*(.+)", raw_body)
        if tm:
            tags = [t.strip().strip("`").lower() for t in re.split(r"[,，\s]+", tm.group(1)) if t.strip()]
            raw_body = re.sub(r"\*\*Tags?:\*\*\s*.+\n?", "", raw_body).strip()

        entries.append({
            "title":     raw_title,
            "type":      entry_type,
            "tags":      tags,
            "body":      raw_body,
            "date_hint": date_hint,
        })

    return entries


def _parse_plain_md(path: Path) -> list[dict]:
    """
    Import a plain .md file as a single lore entry.
    First heading → title; rest → body.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    title = path.stem.replace("_", " ").replace("-", " ").title()
    body = text

    # try first heading
    for line in lines:
        m = re.match(r"^#{1,3}\s+(.+)$", line)
        if m:
            title = m.group(1).strip()
            break

    return [{"title": title, "type": "lore", "tags": [], "body": body, "date_hint": None}]


@click.command("import")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option("--type", "entry_type",
              type=click.Choice(["decision", "lore", "pitfall", "reference", "auto"]),
              default="auto", show_default=True,
              help="Override entry type (auto = detect)")
@click.option("--dry-run", is_flag=True, help="Parse and show what would be imported, don't write")
@click.option("--no-index", is_flag=True, help="Skip embedding index update")
@click.option("--yes", "-y", is_flag=True, help="Skip per-entry confirmation")
def cmd_import(
    source: Path,
    entry_type: str,
    dry_run: bool,
    no_index: bool,
    yes: bool,
) -> None:
    """Import entries from an existing markdown file.

    SOURCE can be:
    \b
      docs/decisions.md   — parsed as D-xxx decision blocks
      any .md file        — imported as a single lore entry

    \b
    Examples:
      vein import docs/decisions.md
      vein import docs/decisions.md --dry-run
      vein import notes/dma_notes.md --type lore
    """
    store = VeinStore.require()
    cfg = store.load_config()
    base_url  = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    embed_model = cfg.get("model", {}).get("embed_model", "nomic-embed-text")

    # detect source format
    text_preview = source.read_text(encoding="utf-8")[:500]
    is_decisions_md = bool(_D_HEADER.search(text_preview))

    if is_decisions_md:
        raw_entries = _parse_decisions_md(source)
        console.print(f"[dim]Detected decisions.md format — {len(raw_entries)} D-xxx blocks[/]")
    else:
        raw_entries = _parse_plain_md(source)
        console.print(f"[dim]Plain markdown — importing as 1 entry[/]")

    if not raw_entries:
        console.print("[yellow]Nothing to import.[/]")
        return

    # apply type override
    if entry_type != "auto":
        for r in raw_entries:
            r["type"] = entry_type

    if dry_run:
        console.print(f"\n[bold]Dry run — {len(raw_entries)} entries would be imported:[/]\n")
        for r in raw_entries:
            console.print(f"  [{r['type']}] {r['title'][:80]}")
        return

    # import loop
    written = 0
    skipped = 0

    for r in track(raw_entries, description="Importing…", console=console):
        from datetime import datetime, timezone
        from ..core.models import Entry

        date_hint = r.get("date_hint")
        if date_hint:
            try:
                ts = datetime.fromisoformat(date_hint).replace(tzinfo=timezone.utc)
            except ValueError:
                ts = datetime.now(timezone.utc)
        else:
            ts = datetime.now(timezone.utc)

        entry = Entry(
            id=Entry.new_id(),
            type=r["type"],
            title=r["title"],
            tags=r.get("tags", []),
            date=ts,
            source=f"import:{source.name}",
            body=r.get("body", ""),
        )

        try:
            store.write_entry(
                entry,
                auto_index=(not no_index),
                base_url=base_url,
                embed_model=embed_model,
            )
            written += 1
        except Exception as exc:
            console.print(f"[red]Failed:[/] {entry.title[:60]} — {exc}", highlight=False)
            skipped += 1

    console.print(
        f"\n[green]Imported {written}[/] entr{'y' if written == 1 else 'ies'}."
        + (f"  [yellow]{skipped} skipped.[/]" if skipped else "")
    )
    console.print(f"[dim]Run [bold]vein status[/] to see the updated counts.[/]")
