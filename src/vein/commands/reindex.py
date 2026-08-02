"""vein reindex — rebuild .vein/index/vein.db from all entries."""

from __future__ import annotations

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ..core.store import VeinStore

console = Console()


@click.command("reindex")
@click.option("--force", is_flag=True, help="Drop and rebuild index from scratch")
@click.option("--all", "reindex_all_flag", is_flag=True,
              help="Re-embed every entry, including ones already indexed")
@click.option("--type", "entry_type",
              type=click.Choice(["decision", "lore", "pitfall", "reference"]),
              default=None,
              help="Only reindex this entry type")
def cmd_reindex(force: bool, reindex_all_flag: bool, entry_type: str | None) -> None:
    """Rebuild the search index for .vein/ entries.

    Incremental by default — re-embeds only entries that are missing from the
    index, indexed without a vector (ollama was down at capture time), or
    carrying a vector of the wrong width (embed_model changed since). That
    makes it cheap enough to actually run: a full re-embed of a large store
    takes minutes, so in practice it never got run and gaps accumulated.

    Run this after:
    \b
      - First time setting up ollama (to generate embeddings)
      - Manual edits to .vein/*.md files
      - Changing embed_model in config.yaml (detected automatically)
      - `vein status` reports an index gap

    \b
    Examples:
      vein reindex                # backfill what's missing
      vein reindex --all          # re-embed everything, keep the DB
      vein reindex --force        # drop the DB and rebuild
      vein reindex --type pitfall
    """
    store = VeinStore.require()
    base_url, embed_model = store.model_cfg()

    idx = store.open_index()

    # Vectors from a different model have a different dimension and can never
    # be compared against a query — an incremental pass would leave them as
    # permanent dead weight, so a model switch means re-embedding everything.
    prev_model = idx.meta_get("embed_model")
    if prev_model and prev_model != embed_model:
        console.print(
            f"[yellow]Embedding model changed:[/] "
            f"[dim]{prev_model}[/] → [bold]{embed_model}[/] — re-embedding all entries."
        )
        reindex_all_flag = True

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
            DROP TABLE IF EXISTS meta;
        """)
        idx._setup()
        console.print("[yellow]Index dropped — rebuilding from scratch.[/]")

    entries = store.list_entries(type_filter=entry_type, status_filter=None)
    if not entries:
        console.print("[yellow]No entries found.[/]")
        idx.close()
        return

    total_on_disk = len(entries)
    if not (force or reindex_all_flag):
        stale = idx.unembedded_ids() | idx.needs_reindex({e.id for e in entries})

        # Vectors of a different width were embedded by another model and are
        # unreachable by any query — probe the live model for its dimension and
        # sweep them in too, so a plain `vein reindex` repairs the drift.
        from ..core.embed import embed_text
        probe = embed_text("vein index probe", base_url=base_url, model=embed_model)
        if probe:
            wrong_dim = idx.ids_with_other_dim(len(probe))
            if wrong_dim:
                console.print(
                    f"[yellow]{len(wrong_dim)} entries[/] were embedded at a different "
                    f"dimension than [bold]{embed_model}[/] ({len(probe)}) — re-embedding."
                )
            stale |= wrong_dim

        entries = [e for e in entries if e.id in stale]
        if not entries:
            console.print(
                f"[green]Index is current.[/]  {total_on_disk} entries, "
                f"{idx.count_embedded()} embedded.  [dim]--all to re-embed anyway.[/]"
            )
            idx.close()
            return
        console.print(
            f"[dim]{total_on_disk} entries on disk, "
            f"[bold]{len(entries)}[/] need embedding.[/]"
        )

    # Drop index rows whose .md file is gone, so recall can't return dead ids.
    # entry_ids() reads filenames only — no second full-store YAML parse.
    for dead in idx.stale_ids(store.entry_ids()):
        idx.remove(dead)

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
