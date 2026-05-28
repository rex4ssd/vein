"""vein ask — quick keyword search, returns direct answer."""

from __future__ import annotations

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ..core.store import VeinStore

console = Console()


@click.command("ask")
@click.argument("question")
@click.option("--limit", "-n", default=5, show_default=True,
              help="Max results to show")
@click.option("--type", "-t", "entry_type", default=None,
              help="Filter by type (decision/lore/pitfall/reference)")
@click.option("--raw", is_flag=True, help="Print raw markdown body")
def cmd_ask(question: str, limit: int, entry_type: str | None, raw: bool) -> None:
    """Search .vein/ for answers to a question.

    Uses keyword matching (Phase 0). Semantic search in Phase 1.

    \b
    Examples:
      vein ask "why callback not polling"
      vein ask "DMA race condition" --type pitfall
      vein ask "sqlite" -n 10
    """
    store = VeinStore.require()
    results = store.grep_entries(question, limit=limit)

    # filter by type if requested
    if entry_type:
        results = [(e, s) for e, s in results if e.type == entry_type]

    if not results:
        console.print(f"[yellow]No results for:[/] {question}")
        console.print("[dim]Tip: try broader keywords, or use `vein log lore` to capture it[/]")
        return

    console.print(f"\n[bold]Results for:[/] [cyan]{question}[/]  "
                  f"[dim]({len(results)} found)[/]\n")

    for i, (entry, score) in enumerate(results, 1):
        color = {"decision": "cyan", "lore": "green",
                 "pitfall": "yellow", "reference": "blue"}.get(entry.type, "white")
        header = (
            f"[{color}]{entry.type}[/]  "
            f"[bold]{entry.title}[/]  "
            f"[dim]{entry.date_str}[/]"
            + (f"  [dim]tags: {', '.join(entry.tags[:4])}[/]" if entry.tags else "")
        )
        if raw:
            click.echo(f"\n--- {entry.id} ---")
            click.echo(entry.body)
        else:
            console.print(Panel(
                Markdown(entry.body) if entry.body else "[dim](no body)[/]",
                title=header,
                border_style=color,
            ))

    if not results:
        return
    console.print(
        f"\n[dim]Use [bold]vein recall \"{question}\"[/] for semantic search "
        f"(requires ollama embedding).[/]"
    )
