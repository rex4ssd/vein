"""vein recall — hybrid semantic search (FTS5 + embedding re-rank)."""

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
@click.option("--fts-only", is_flag=True, help="Force keyword-only search (skip embedding)")
def cmd_recall(query: str, limit: int, budget: str, raw_output: bool, fts_only: bool) -> None:
    """Semantic search over .vein/ lore.

    Uses FTS5 BM25 pre-filter → nomic-embed-text cosine re-rank when ollama is
    available. Falls back gracefully to keyword search when ollama is offline.

    \b
    Examples:
      vein recall "DMA timeout"
      vein recall "race condition" --budget 32k
      vein recall "uart" --fts-only
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
        # FTS fallback (index exists) or full grep fallback
        try:
            idx = store.open_index()
            hit_ids = idx.fts_search(query, k=limit)
            idx.close()
            if hit_ids:
                search_mode = "fts"
        except Exception:
            pass

    # Final fallback: grep
    if not hit_ids:
        results = store.grep_entries(query, limit=limit)
        if not results:
            console.print(f"[yellow]No results for:[/] {query}")
            console.print("[dim]Tip: vein reindex — to build search index[/]")
            return
        _render_results(
            [entry for entry, _ in results],
            query=query,
            mode="keyword",
            raw_output=raw_output,
        )
        return

    # Resolve hit_ids → Entry objects
    entries = []
    for eid in hit_ids:
        try:
            entries.append(store.read_entry(eid))
        except (KeyError, Exception):
            continue

    if not entries:
        console.print(f"[yellow]No results for:[/] {query}")
        return

    _render_results(entries, query=query, mode=search_mode, raw_output=raw_output)


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
