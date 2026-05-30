"""vein recall — hybrid semantic search (FTS5 + embedding re-rank)."""

from __future__ import annotations

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ..core.store import VeinStore, cross_project_search

console = Console()


@click.command("recall")
@click.argument("query")
@click.option("--limit", "-n", default=5, show_default=True)
@click.option("--budget", default="2k",
              type=click.Choice(["2k", "32k", "200k", "raw"]),
              help="Output budget tier")
@click.option("--raw", "raw_output", is_flag=True)
@click.option("--fts-only", is_flag=True, help="Force keyword-only search (skip embedding)")
@click.option("--cross-project", "-x", is_flag=True,
              help="Also search other repos registered via `vein init`")
def cmd_recall(query: str, limit: int, budget: str, raw_output: bool,
               fts_only: bool, cross_project: bool) -> None:
    """Semantic search over .vein/ lore.

    Uses FTS5 BM25 pre-filter → nomic-embed-text cosine re-rank when ollama is
    available. Falls back gracefully to keyword search when ollama is offline.

    \b
    Examples:
      vein recall "DMA timeout"
      vein recall "race condition" --budget 32k
      vein recall "app store reject" -x      # search across all projects
    """
    store = VeinStore.require()
    cfg = store.load_config()
    base_url = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    embed_model = cfg.get("model", {}).get("embed_model", "nomic-embed-text")
    min_score = cfg.get("capture", {}).get("min_cosine_threshold", 0.30)

    hit_ids: list[str] = []
    search_mode = "keyword"

    if not fts_only:
        # Try hybrid vector search
        try:
            idx = store.open_index()
            hits = idx.vector_search(
                query,
                base_url=base_url,
                embed_model=embed_model,
                k=limit,
                min_score=min_score,
            )
            idx.close()
            if hits:
                hit_ids = [eid for eid, _ in hits]
                search_mode = "semantic"
        except Exception:
            pass

    if not hit_ids:
        # FTS fallback (index exists)
        try:
            idx = store.open_index()
            hit_ids = idx.fts_search(query, k=limit)
            idx.close()
            if hit_ids:
                search_mode = "fts"
        except Exception:
            pass

    # Resolve local hits → Entry objects (grep as final fallback)
    entries: list = []
    if hit_ids:
        for eid in hit_ids:
            try:
                entries.append(store.read_entry(eid))
            except Exception:
                continue
    else:
        entries = [entry for entry, _ in store.grep_entries(query, limit=limit)]
        search_mode = "keyword"

    # Cross-project hits from other registered repos (keyword grep, no ollama)
    xhits = (
        cross_project_search(query, exclude_root=store.root, limit=limit)
        if cross_project else []
    )

    if not entries and not xhits:
        console.print(f"[yellow]No results for:[/] {query}")
        console.print("[dim]Tip: vein reindex — to build search index[/]")
        if not cross_project:
            console.print("[dim]Or add [bold]-x[/] to search across all projects.[/]")
        return

    if entries:
        _render_results(entries, query=query, mode=search_mode, raw_output=raw_output)
    elif cross_project:
        console.print(f"\n[bold]Recall:[/] [cyan]{query}[/]  "
                      f"[dim](nothing here — cross-project only)[/]")

    if xhits:
        console.print("\n[dim]── from other projects ──────────────────────────[/]")
        _render_xproject(xhits, raw_output=raw_output)


def _render_xproject(xhits: list, *, raw_output: bool) -> None:
    for project, entry, _score in xhits:
        color = {
            "decision": "cyan", "lore": "green",
            "pitfall": "yellow", "reference": "blue",
        }.get(entry.type, "white")
        header = (
            f"[magenta]{project}[/]  [{color}]{entry.type}[/]  "
            f"[bold]{entry.title}[/]  [dim]{entry.id}[/]"
        )
        if raw_output:
            click.echo(f"\n=== [{project}] {entry.id} ===")
            click.echo(entry.to_file_content())
        else:
            console.print(Panel(
                Markdown(entry.body) if entry.body else "[dim](no body)[/]",
                title=header,
                border_style=color,
                subtitle=f"[dim]{entry.date_str} · {', '.join(entry.tags[:4])}[/]",
            ))


def _render_results(
    entries: list,
    *,
    query: str,
    mode: str,
    raw_output: bool,
) -> None:
    mode_label = {
        "semantic": "[green]semantic[/] (FTS+embed)",
        "fts":      "[cyan]FTS5 BM25[/]",
        "keyword":  "[yellow]keyword[/]",
    }.get(mode, mode)

    console.print(
        f"\n[bold]Recall:[/] [cyan]{query}[/]  "
        f"[dim]({mode_label} · {len(entries)} results)[/]\n"
    )

    for entry in entries:
        color = {
            "decision": "cyan",
            "lore":     "green",
            "pitfall":  "yellow",
            "reference": "blue",
        }.get(entry.type, "white")

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
