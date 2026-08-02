"""vein status — show .vein/ summary."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table
from rich import box

from ..core.store import VeinStore

console = Console()


@click.command("status")
@click.option("--all", "show_all", is_flag=True, help="Include resolved/superseded entries")
def cmd_status(show_all: bool) -> None:
    """Show .vein/ statistics and recent entries."""
    store = VeinStore.require()
    cfg = store.load_config()
    project_name = cfg.get("project", {}).get("name", store.root.name)
    phase = cfg.get("project", {}).get("phase", "0")

    # One full parse of the store — every section below derives from it.
    # (This command used to call list_entries ~7 times: once per type for the
    # table, once for index health, once for pitfalls, once for recents.)
    entries = store.list_entries(status_filter=None)
    disk_ids = store.entry_ids()  # filename-level truth, includes broken files
    total = len(disk_ids)

    console.print(f"\n[bold cyan]{project_name}[/]  [dim]Phase {phase}[/]  "
                  f"[dim]{store.vein_dir}[/]")

    # ── counts table ──
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    t.add_column("type", style="cyan")
    t.add_column("count", justify="right")
    t.add_column("active", justify="right")
    for type_key in ("decision", "lore", "pitfall", "reference"):
        of_type = [e for e in entries if e.type == type_key]
        active = [e for e in of_type if e.status == "active"]
        t.add_row(type_key, str(len(of_type)), str(len(active)))
    t.add_section()
    t.add_row("[bold]total[/]", f"[bold]{total}[/]", "")
    console.print(t)

    # ── unparseable files ──
    # A file whose frontmatter won't parse exists on disk but is invisible to
    # every command — no listing, no recall, no reindex. Name the ids so it's
    # fixable rather than a silent off-by-N in the counts.
    broken = disk_ids - {e.id for e in entries}
    if broken:
        shown = ", ".join(sorted(broken)[:3]) + ("…" if len(broken) > 3 else "")
        console.print(
            f"[yellow]⚠ {len(broken)} file(s) with unparseable frontmatter "
            f"(unsearchable):[/] [dim]{shown}[/]\n"
        )

    # ── index health ──
    # Entries land on disk even when embedding fails, so "on disk" and
    # "semantically searchable" drift apart silently. Surface the gap.
    try:
        idx = store.open_index()
        missing = len(idx.needs_reindex({e.id for e in entries}))
        unembedded = len(idx.unembedded_ids())
        embedded = idx.count_embedded()
        idx.close()
        if missing or unembedded:
            console.print(
                f"[yellow]⚠ Index:[/] {embedded}/{total} embedded — "
                f"{missing} unindexed, {unembedded} keyword-only.  "
                f"[dim]Run `vein reindex`.[/]\n"
            )
        else:
            console.print(f"[dim]Index: {embedded}/{total} embedded.[/]\n")
    except Exception:
        pass

    # ── active pitfalls ──
    pitfalls = [e for e in entries if e.type == "pitfall" and e.status == "active"]
    if pitfalls:
        console.print(f"[bold yellow]⚠ Active pitfalls ({len(pitfalls)}):[/]")
        for e in pitfalls[:5]:
            console.print(f"  • [yellow]{e.title}[/]  [dim]{e.date_str}[/]")
        if len(pitfalls) > 5:
            console.print(f"  [dim]… and {len(pitfalls) - 5} more[/]")

    # ── recent entries ──
    console.print("\n[bold]Recent entries:[/]")
    all_recent = sorted(
        (e for e in entries if show_all or e.status == "active"),
        key=lambda e: e.date,
        reverse=True,
    )[:8]
    for e in all_recent:
        color = {"decision": "cyan", "lore": "green",
                 "pitfall": "yellow", "reference": "blue"}.get(e.type, "white")
        console.print(f"  [{color}]{e.type:10}[/] {e.date_str}  {e.title}")

    console.print()
