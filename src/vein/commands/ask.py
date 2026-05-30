"""vein ask — quick keyword search, returns direct answer."""

from __future__ import annotations

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ..core.store import VeinStore, cross_project_search

console = Console()


@click.command("ask")
@click.argument("question")
@click.option("--limit", "-n", default=5, show_default=True,
              help="Max results to show")
@click.option("--type", "-t", "entry_type", default=None,
              help="Filter by type (decision/lore/pitfall/reference)")
@click.option("--cross-project", "-x", is_flag=True,
              help="Also search other repos registered via `vein init`")
@click.option("--raw", is_flag=True, help="Print raw markdown body")
def cmd_ask(question: str, limit: int, entry_type: str | None,
            cross_project: bool, raw: bool) -> None:
    """Search .vein/ for answers to a question.

    Uses keyword matching (Phase 0). Semantic search in Phase 1.

    \b
    Examples:
      vein ask "why callback not polling"
      vein ask "DMA race condition" --type pitfall
      vein ask "app store reject" -x        # search across all projects
    """
    store = VeinStore.require()
    results = store.grep_entries(question, limit=limit)

    # filter by type if requested
    if entry_type:
        results = [(e, s) for e, s in results if e.type == entry_type]

    # cross-project hits (other registered repos)
    xhits = []
    if cross_project:
        xhits = cross_project_search(question, exclude_root=store.root, limit=limit)
        if entry_type:
            xhits = [(p, e, s) for p, e, s in xhits if e.type == entry_type]

    if not results and not xhits:
        console.print(f"[yellow]No results for:[/] {question}")
        console.print("[dim]Tip: try broader keywords, or use `vein log lore` to capture it[/]")
        if not cross_project:
            console.print("[dim]Or add [bold]-x[/] to search across all projects.[/]")
        return

    console.print(f"\n[bold]Results for:[/] [cyan]{question}[/]  "
                  f"[dim]({len(results)} here"
                  + (f", {len(xhits)} cross-project" if cross_project else "")
                  + ")[/]\n")

    def _render(entry, *, project: str | None = None) -> None:
        color = {"decision": "cyan", "lore": "green",
                 "pitfall": "yellow", "reference": "blue"}.get(entry.type, "white")
        tag = f"[magenta]{project}[/]  " if project else ""
        header = (
            f"{tag}[{color}]{entry.type}[/]  "
            f"[bold]{entry.title}[/]  "
            f"[dim]{entry.date_str}[/]"
            + (f"  [dim]tags: {', '.join(entry.tags[:4])}[/]" if entry.tags else "")
        )
        if raw:
            click.echo(f"\n--- {('[' + project + '] ') if project else ''}{entry.id} ---")
            click.echo(entry.body)
        else:
            console.print(Panel(
                Markdown(entry.body) if entry.body else "[dim](no body)[/]",
                title=header,
                border_style=color,
            ))

    for entry, score in results:
        _render(entry)

    if xhits:
        console.print("\n[dim]── from other projects ──────────────────────────[/]\n")
        for project, entry, score in xhits:
            _render(entry, project=project)

    if not cross_project:
        console.print(
            f"\n[dim]Use [bold]vein recall \"{question}\"[/] for semantic search "
            f"(requires ollama embedding), or [bold]-x[/] to search all projects.[/]"
        )
