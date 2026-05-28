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

    stats = store.stats()
    total = sum(stats.values())

    console.print(f"\n[bold cyan]{project_name}[/]  [dim]Phase {phase}[/]  "
                  f"[dim]{store.vein_dir}[/]")

    # ── counts table ──
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    t.add_column("type", style="cyan")
    t.add_column("count", justify="right")
    t.add_column("active", justify="right")
    for type_key in ("decision", "lore", "pitfall", "reference"):
        all_entries = store.list_entries(type_key, status_filter=None)  # type: ignore
        active = [e for e in all_entries if e.status == "active"]
        t.add_row(type_key, str(len(all_entries)), str(len(active)))
    t.add_section()
    t.add_row("[bold]total[/]", f"[bold]{total}[/]", "")
    console.print(t)

    # ── active pitfalls ──
    pitfalls = store.list_entries("pitfall", status_filter="active")
    if pitfalls:
        console.print(f"[bold yellow]⚠ Active pitfalls ({len(pitfalls)}):[/]")
        for e in pitfalls[:5]:
            console.print(f"  • [yellow]{e.title}[/]  [dim]{e.date_str}[/]")
        if len(pitfalls) > 5:
            console.print(f"  [dim]… and {len(pitfalls) - 5} more[/]")

    # ── recent entries ──
    console.print("\n[bold]Recent entries:[/]")
    all_recent = sorted(
        store.list_entries(status_filter=None if show_all else "active"),
        key=lambda e: e.date,
        reverse=True,
    )[:8]
    for e in all_recent:
        color = {"decision": "cyan", "lore": "green",
                 "pitfall": "yellow", "reference": "blue"}.get(e.type, "white")
        console.print(f"  [{color}]{e.type:10}[/] {e.date_str}  {e.title}")

    console.print()
