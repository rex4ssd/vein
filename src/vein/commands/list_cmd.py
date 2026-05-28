"""vein list — list entries with filtering."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from ..core.store import VeinStore

console = Console()

_TYPE_COLORS = {
    "decision":  "cyan",
    "lore":      "green",
    "pitfall":   "yellow",
    "reference": "blue",
}


@click.command("list")
@click.option("--type", "entry_type",
              type=click.Choice(["decision", "lore", "pitfall", "reference"]),
              default=None,
              help="Filter by entry type")
@click.option("--status", default="active",
              type=click.Choice(["active", "superseded", "archived", "all"]),
              show_default=True)
@click.option("--tag", "tag_filter", default=None, help="Filter by tag (substring match)")
@click.option("--limit", "-n", default=50, show_default=True)
@click.option("--ids-only", is_flag=True, help="Print only entry IDs (scriptable)")
def cmd_list(
    entry_type: str | None,
    status: str,
    tag_filter: str | None,
    limit: int,
    ids_only: bool,
) -> None:
    """List entries in .vein/.

    \b
    Examples:
      vein list
      vein list --type pitfall
      vein list --status all --tag dma
      vein list --ids-only | xargs -I{} vein show {}
    """
    store = VeinStore.require()
    status_arg = None if status == "all" else status

    entries = store.list_entries(
        type_filter=entry_type,
        status_filter=status_arg,
        limit=limit,
    )

    if tag_filter:
        tag_low = tag_filter.lower()
        entries = [e for e in entries if any(tag_low in t for t in e.tags)]

    if not entries:
        console.print("[yellow]No entries found.[/]")
        return

    if ids_only:
        for e in entries:
            click.echo(e.id)
        return

    table = Table(show_header=True, header_style="bold dim", expand=False)
    table.add_column("ID",     style="dim",    no_wrap=True, max_width=28)
    table.add_column("Type",   no_wrap=True,   max_width=10)
    table.add_column("Title",  min_width=30,   max_width=60)
    table.add_column("Tags",   style="dim",    max_width=30)
    table.add_column("Date",   style="dim",    no_wrap=True, max_width=12)

    for entry in entries:
        color = _TYPE_COLORS.get(entry.type, "white")
        table.add_row(
            entry.id,
            f"[{color}]{entry.type}[/]",
            entry.title,
            ", ".join(entry.tags[:4]),
            entry.date_str[:10],
        )

    console.print(table)
    console.print(f"[dim]{len(entries)} entries[/]")
