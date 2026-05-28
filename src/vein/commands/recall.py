"""vein recall — semantic search (Phase 0: keyword fallback)."""

from __future__ import annotations

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ..core.store import VeinStore

console = Console()


@click.command("recall")
@click.argument("query")
@click.option("--limit", "-n", default=5, show_default=True)
@click.option("--budget", default="2k",
              type=click.Choice(["2k", "32k", "200k", "raw"]),
              help="Output budget tier")
@click.option("--raw", "raw_output", is_flag=True)
def cmd_recall(query: str, limit: int, budget: str, raw_output: bool) -> None:
    """Semantic search over .vein/ lore.

    Phase 0: keyword search (same as `vein ask`).
    Phase 1: embedding-based semantic search via sqlite-vec + nomic-embed-text.

    \b
    Examples:
      vein recall "DMA timeout"
      vein recall "race condition" --budget 32k
    """
    store = VeinStore.require()

    # Phase 0: keyword search
    # Phase 1: try vector search first, fall back to keyword
    results = store.grep_entries(query, limit=limit)

    if not results:
        console.print(f"[yellow]No results for:[/] {query}")
        console.print("[dim]Try: vein ask, or broaden the query[/]")
        return

    console.print(f"\n[bold]Recall:[/] [cyan]{query}[/]  "
                  f"[dim](keyword search · Phase 0 · {len(results)} results)[/]\n")

    for entry, _score in results:
        color = {"decision": "cyan", "lore": "green",
                 "pitfall": "yellow", "reference": "blue"}.get(entry.type, "white")
        header = (
            f"[{color}]{entry.type}[/]  [bold]{entry.title}[/]  "
            f"[dim]{entry.id}[/]"
        )
        if raw_output:
            click.echo(f"\n=== {entry.id} ===")
            click.echo(entry.to_file_content())
        else:
            console.print(Panel(
                Markdown(entry.body) if entry.body else "[dim](no body)[/]",
                title=header,
                border_style=color,
                subtitle=f"[dim]{entry.date_str} · {', '.join(entry.tags[:4])}[/]",
            ))

    console.print(
        "\n[dim]Phase 1 will add embedding-based semantic search "
        "(nomic-embed-text + sqlite-vec).[/]"
    )
