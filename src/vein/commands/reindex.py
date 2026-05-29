"""vein reindex — rebuild .vein/index/vein.db from all entries."""

from __future__ import annotations

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ..core.store import VeinStore

console = Console()


@click.command("reindex")
@click.option("--force", is_flag=True, help="Drop and rebuild index from scratch")
@click.option("--type", "entry_type",
              type=click.Choice(["decision", "lore", "pitfall", "reference"]),
              default=None,
              help="Only reindex this entry type")
def cmd_reindex(force: bool, entry_type: str | None) -> None:
    """Rebuild the search index for all .vein/ entries.

    Run this after:
    \b
      - First time setting up ollama (to generate embeddings)
      - Adding/changing nomic-embed-text model
      - Manual edits to .vein/*.md files
      - Migrating from an older vein version

    \b
    Examples:
      vein reindex
      vein reindex --force
      vein reindex --type pitfall
    """
    store = VeinStore.require()
    cfg = store.load_config()
    base_url    = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    embed_model = cfg.get("model", {}).get("embed_model", "nomic-embed-text")

    idx = store.open_index()

    if idx.relocated_to is not None:
        console.print(
            f"[yellow]Note:[/] this filesystem can't host a SQLite index "
            f"(network/FUSE/synced dir).\n"
            f"[dim]Index relocated to {idx.relocated_to}[/]\n"
        )

    if force:
        # drop and recreate
        idx.conn.executescript("""
            DROP TABLE IF EXISTS embeddings;
            DROP TABLE IF EXISTS fts;
        """)
        idx._setup()
        console.print("[yellow]Index dropped — rebuilding from scratch.[/]")

    entries = store.list_entries(type_filter=entry_type, status_filter=None)
    if not entries:
        console.print("[yellow]No entries found.[/]")
        idx.close()
        return

    console.print(f"[dim]Indexing {len(entries)} entries via [bold]{embed_model}[/] @ {base_url} …[/]\n")

    embedded = 0
    skipped  = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Indexing…", total=len(entries))

        def _cb(i: int, total: int, entry) -> None:
            progress.update(task, completed=i,
                            description=f"[dim]{entry.type}[/] {entry.title[:50]}")

        embedded, skipped = idx.reindex_all(
            entries,
            base_url=base_url,
            embed_model=embed_model,
            progress_cb=_cb,
        )

    idx.close()

    console.print(
        f"[green]Done.[/]  "
        f"embedded: [bold]{embedded}[/]  "
        f"fts-only: [yellow]{skipped}[/]  "
        f"(skipped = ollama unavailable or no vector returned)"
    )
    if skipped > 0:
        console.print(
            f"\n[dim]To get embeddings, ensure ollama is running:\n"
            f"  ollama serve\n"
            f"  ollama pull {embed_model}[/]"
        )
