"""vein study — batch-fetch GitHub repos into a named collection and compare them.

Usage:
  vein study fetch study_llm simonw/llm BerriAI/litellm jlowin/fastmcp
  vein study compare study_llm
  vein study list
  vein study list study_llm
  vein study purge study_llm --keep-compare
  vein study watchlist add study_llm simonw/llm BerriAI/litellm
  vein study watchlist list
  vein study watchlist run [study_llm]

Design:
  - "Collection" is a tag: study:<name>. No new schema needed.
  - fetch: wraps vein fetch for each repo, injects study:<name> tag.
  - compare: pulls reference entries from the collection, calls ollama
    for a structured comparison, writes result back as a reference entry.
  - list: reads distinct study:* tags from the store.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..core.models import Entry
from ..core.store import VeinStore
from .fetch import (
    _build_content,
    _call_ollama_fetch,
    _collect_files,
    _normalise_github,
    _readme_fallback,
)

console = Console()

_COMPARE_MAX_ENTRIES_PER_REPO = 4
_COMPARE_MAX_BODY_CHARS       = 300
_COMPARE_MAX_CONTEXT_CHARS    = 6_000

_COMPARE_PROMPT = """\
You are a senior engineer comparing open-source projects in the "{collection}" study group.

Here are the key insights extracted from each project:

{context}

Provide a structured comparison with these sections:
1. One-liner per project (what it does, one sentence)
2. Key design differences and trade-offs between the projects
3. When to use which (concrete use-case guidance)
4. Overall verdict: ranking + recommended choice for someone building AI tooling

Be direct and opinionated. Total output should be concise — 15 to 30 lines.
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def _fetch_one_repo(
    store: VeinStore,
    slug: str,
    clone_url: str,
    collection_tag: str,
    extra_tags: list[str],
    max_files: int,
    fetch_model: str,
    base_url: str,
    embed_model: str,
    dry_run: bool,
    verbose: bool,
) -> list[Entry]:
    """Clone one repo, extract insights, write to store. Returns written entries."""
    import subprocess

    tmpdir = tempfile.mkdtemp(prefix="vein-study-")
    written: list[Entry] = []
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", clone_url, tmpdir],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            console.print(f"  [red]clone failed:[/] {result.stderr.strip()[:120]}")
            return []

        files   = _collect_files(Path(tmpdir), max_files)
        if not files:
            console.print(f"  [yellow]no markdown files found[/]")
            return []

        content = _build_content(files, 8_000)
        results = _call_ollama_fetch(content, base_url=base_url, model=fetch_model,
                                     verbose=verbose)

        if results is None:
            console.print(f"  [yellow]ollama unavailable — README fallback[/]")
            results = _readme_fallback(files, slug)
        elif not results:
            console.print(f"  [dim]nothing extracted[/]")
            return []

        github_url = clone_url.removesuffix(".git")
        base_tags  = ["fetch", "github", f"source:github/{slug}",
                      collection_tag] + extra_tags

        for item in results:
            raw_type = item.get("type", "reference")
            if raw_type not in ("decision", "lore", "pitfall", "reference"):
                raw_type = "reference"
            title = item.get("title", "").strip()
            body  = item.get("body",  "").strip()
            if not title:
                continue

            if dry_run:
                console.print(f"    [dim][{raw_type}] {title}[/]")
                continue

            entry = Entry.make(
                type=raw_type,          # type: ignore[arg-type]
                title=title,
                body=body,
                tags=base_tags,
                source=f"github:{slug}",
                source_url=github_url,
                source_title=slug,
                volatility="external-fact",
            )
            try:
                store.write_entry(entry, auto_index=True,
                                  base_url=base_url, embed_model=embed_model)
                written.append(entry)
            except Exception as exc:
                console.print(f"  [red]write failed:[/] {title[:50]} — {exc}")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return written


def _build_compare_context(entries_by_repo: dict[str, list[Entry]]) -> str:
    """Build context string for the comparison prompt."""
    parts: list[str] = []
    total = 0
    for slug, entries in entries_by_repo.items():
        header = f"\n--- {slug} ---\n"
        lines  = [header]
        for e in entries[:_COMPARE_MAX_ENTRIES_PER_REPO]:
            body_snip = e.body[:_COMPARE_MAX_BODY_CHARS].replace("\n", " ")
            lines.append(f"[{e.type}] {e.title}: {body_snip}")
        block = "\n".join(lines)
        if total + len(block) > _COMPARE_MAX_CONTEXT_CHARS:
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts)


def _call_ollama_compare(context: str, collection: str,
                         base_url: str, model: str) -> str | None:
    """Call ollama for a collection comparison. Returns text or None."""
    try:
        import httpx
    except ImportError:
        return None

    prompt = _COMPARE_PROMPT.format(collection=collection, context=context)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.2},
    }
    try:
        resp = httpx.post(f"{base_url}/api/chat", json=payload, timeout=180.0)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip() or None
    except Exception:
        return None


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.group("study")
def cmd_study() -> None:
    """Batch-fetch GitHub repos into a named collection and compare them.

    \b
    vein study fetch study_llm simonw/llm BerriAI/litellm
    vein study compare study_llm
    vein study list
    vein study list study_llm
    """


@cmd_study.command("fetch")
@click.argument("collection")
@click.argument("repos", nargs=-1, required=True)
@click.option("--dry-run",   is_flag=True)
@click.option("--max-files", default=8, show_default=True)
@click.option("--model",     default="", help="Override ollama model")
@click.option("--tag", "extra_tags", multiple=True, help="Extra tag(s) (repeatable)")
@click.option("--verbose", "-v", is_flag=True)
def study_fetch(
    collection: str,
    repos: tuple[str, ...],
    dry_run: bool,
    max_files: int,
    model: str,
    extra_tags: tuple[str, ...],
    verbose: bool,
) -> None:
    """Fetch multiple GitHub repos into a named collection.

    \b
    Examples:
      vein study fetch study_llm simonw/llm BerriAI/litellm
      vein study fetch study_mcp jlowin/fastmcp modelcontextprotocol/python-sdk
    """
    store = VeinStore.require()
    cfg   = store.load_config()
    base_url    = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    fetch_model = (model
                   or cfg.get("model", {}).get("fetch_model")
                   or cfg.get("model", {}).get("debrief_model", "qwen2.5-coder:7b"))
    embed_model = cfg.get("model", {}).get("embed_model", "nomic-embed-text")
    collection_tag = f"study:{collection}"

    console.print(
        f"\n[bold]study fetch[/] [cyan]{collection}[/] — "
        f"{len(repos)} repo(s)  model={fetch_model}\n"
    )

    total_written = 0
    for raw in repos:
        try:
            clone_url, slug = _normalise_github(raw)
        except click.BadParameter:
            console.print(f"  [red]skip (bad URL):[/] {raw}")
            continue

        console.print(f"[bold]{slug}[/] …", end=" ")
        entries = _fetch_one_repo(
            store=store, slug=slug, clone_url=clone_url,
            collection_tag=collection_tag, extra_tags=list(extra_tags),
            max_files=max_files, fetch_model=fetch_model,
            base_url=base_url, embed_model=embed_model,
            dry_run=dry_run, verbose=verbose,
        )
        if entries:
            console.print(f"[green]✓[/] {len(entries)} entries")
            total_written += len(entries)
        elif not dry_run:
            console.print(f"[yellow]0 entries[/]")

    if not dry_run:
        console.print(
            f"\n[dim]Done. {total_written} total entries tagged [bold]{collection_tag}[/].\n"
            f"Run: [bold]vein study compare {collection}[/][/]"
        )


@cmd_study.command("compare")
@click.argument("collection")
@click.option("--dry-run",  is_flag=True, help="Print context sent to ollama, don't write")
@click.option("--model",    default="",   help="Override ollama model")
@click.option("--output",   default="",   help="Also save comparison to a .md file")
def study_compare(collection: str, dry_run: bool, model: str, output: str) -> None:
    """Compare all repos in a collection using local AI.

    \b
    Examples:
      vein study compare study_llm
      vein study compare study_llm --output ~/Desktop/llm_comparison.md
    """
    store = VeinStore.require()
    cfg   = store.load_config()
    base_url    = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    cmp_model   = (model
                   or cfg.get("model", {}).get("compare_model")
                   or cfg.get("model", {}).get("fetch_model")
                   or cfg.get("model", {}).get("debrief_model", "qwen2.5-coder:7b"))
    collection_tag = f"study:{collection}"

    # gather entries for this collection
    all_entries = store.list_entries(status_filter="active")
    coll_entries = [e for e in all_entries if collection_tag in e.tags]

    if not coll_entries:
        console.print(f"[yellow]No entries found for collection [bold]{collection}[/].[/]")
        console.print(f"Run [bold]vein study fetch {collection} owner/repo ...[/] first.")
        return

    # group by repo slug (source field: "github:owner/repo")
    entries_by_repo: dict[str, list[Entry]] = {}
    for e in coll_entries:
        slug = e.source.removeprefix("github:") if e.source.startswith("github:") else e.source
        entries_by_repo.setdefault(slug, []).append(e)

    console.print(
        f"\n[bold]study compare[/] [cyan]{collection}[/] — "
        f"{len(entries_by_repo)} repo(s), {len(coll_entries)} entries  model={cmp_model}\n"
    )
    for slug, entries in entries_by_repo.items():
        console.print(f"  {slug}: {len(entries)} entries")
    console.print()

    context = _build_compare_context(entries_by_repo)

    if dry_run:
        console.print(Panel(context, title="[dim]context sent to ollama[/]", border_style="dim"))
        return

    console.print(f"[dim]comparing with {cmp_model}…[/]")
    result = _call_ollama_compare(context, collection=collection,
                                  base_url=base_url, model=cmp_model)

    if not result:
        console.print("[yellow]ollama unavailable or returned nothing.[/]")
        return

    console.print(Panel(result, title=f"[bold cyan]{collection} — comparison[/]",
                        border_style="cyan"))

    # write as a reference entry
    entry = Entry.make(
        type="reference",
        title=f"study:{collection} — comparison",
        body=result,
        tags=["study", collection_tag, "compare", "auto"],
        source=f"study:compare:{collection}",
        volatility="external-fact",
    )
    path = store.write_entry(entry, auto_index=False)
    console.print(f"\n[dim]Saved → {path.relative_to(store.root)}[/]")

    if output:
        out_path = Path(output).expanduser()
        out_path.write_text(
            f"# {collection} — Comparison\n\n"
            f"*Generated by `vein study compare {collection}`*\n\n"
            f"{result}\n",
            encoding="utf-8",
        )
        console.print(f"[dim]Also written to {out_path}[/]")


@cmd_study.command("list")
@click.argument("collection", required=False, default="")
def study_list(collection: str) -> None:
    """List all collections, or repos within a collection.

    \b
    Examples:
      vein study list                  # show all collections
      vein study list study_llm        # show repos in study_llm
    """
    store = VeinStore.require()
    all_entries = store.list_entries(status_filter="active")

    if not collection:
        # show all study:* collections with counts
        from collections import Counter
        counts: Counter = Counter()
        for e in all_entries:
            for t in e.tags:
                if t.startswith("study:") and not t.startswith("study:compare:"):
                    counts[t.removeprefix("study:")] += 1

        if not counts:
            console.print("[dim]No study collections found. Run [bold]vein study fetch[/] to create one.[/]")
            return

        table = Table(show_header=True, header_style="bold dim")
        table.add_column("Collection", style="cyan")
        table.add_column("Entries",    style="dim", justify="right")
        for name, count in sorted(counts.items()):
            table.add_row(name, str(count))
        console.print(table)

    else:
        # show repos within a specific collection
        collection_tag = f"study:{collection}"
        coll_entries   = [e for e in all_entries if collection_tag in e.tags]

        if not coll_entries:
            console.print(f"[yellow]Collection [bold]{collection}[/] not found.[/]")
            return

        from collections import defaultdict
        by_repo: dict[str, list[Entry]] = defaultdict(list)
        for e in coll_entries:
            slug = e.source.removeprefix("github:")
            by_repo[slug].append(e)

        console.print(f"\n[bold cyan]{collection}[/] — {len(by_repo)} repo(s)\n")
        for slug, entries in sorted(by_repo.items()):
            types = ", ".join(sorted({e.type for e in entries}))
            console.print(f"  [bold]{slug}[/]  [dim]{len(entries)} entries ({types})[/]")
        console.print()


# ── purge ─────────────────────────────────────────────────────────────────────

@cmd_study.command("purge")
@click.argument("collection")
@click.option("--keep-compare", is_flag=True, default=True, show_default=True,
              help="Keep the compare summary entry (default: on)")
@click.option("--dry-run", is_flag=True)
@click.option("--yes", "-y", is_flag=True)
def study_purge(collection: str, keep_compare: bool, dry_run: bool, yes: bool) -> None:
    """Delete raw fetch entries for a collection, keep the compare summary.

    Use after `vein study compare` + git commit to reclaim disk space.

    \b
    Examples:
      vein study purge study_llm               # delete raw, keep compare
      vein study purge study_llm --no-keep-compare  # delete everything
      vein study purge study_llm --dry-run     # preview
    """
    store = VeinStore.require()
    collection_tag = f"study:{collection}"
    all_entries = store.list_entries(status_filter=None)
    targets = [
        e for e in all_entries
        if collection_tag in e.tags
        and not (keep_compare and e.source.startswith(f"study:compare:"))
    ]

    if not targets:
        console.print(f"[dim]No entries to purge in [bold]{collection}[/].[/]")
        return

    console.print(f"\n[bold]{len(targets)}[/] entries to delete from [cyan]{collection}[/]"
                  + (" [dim](dry-run)[/]" if dry_run else "") + ":")
    for e in targets:
        console.print(f"  [dim][{e.type}][/] {e.title[:70]}")

    if dry_run:
        return

    if not yes:
        click.confirm(f"\nDelete {len(targets)} entries?", abort=True)

    deleted = sum(1 for e in targets if store.delete_entry(e))
    console.print(f"[green]✓[/] Purged {deleted} entries from [cyan]{collection}[/].")
    console.print("[dim]Run [bold]vein reindex[/] to compact the index.[/]")


# ── watchlist ─────────────────────────────────────────────────────────────────

WATCHLIST_FILE = "watchlist.yaml"


def _load_watchlist(store: VeinStore) -> dict:
    p = store.vein_dir / WATCHLIST_FILE
    if not p.exists():
        return {"collections": {}}
    import yaml
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {"collections": {}}


def _save_watchlist(store: VeinStore, data: dict) -> None:
    import yaml
    p = store.vein_dir / WATCHLIST_FILE
    p.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


@cmd_study.group("watchlist")
def study_watchlist() -> None:
    """Manage persistent repo watchlists for automated nightly fetching.

    \b
    vein study watchlist add study_llm simonw/llm BerriAI/litellm
    vein study watchlist list
    vein study watchlist run [study_llm]
    """


@study_watchlist.command("add")
@click.argument("collection")
@click.argument("repos", nargs=-1, required=True)
@click.option("--compare/--no-compare", default=True, show_default=True,
              help="Auto-compare after fetch")
@click.option("--purge-raw/--no-purge-raw", default=False, show_default=True,
              help="Delete raw entries after compare")
def watchlist_add(collection: str, repos: tuple[str, ...],
                  compare: bool, purge_raw: bool) -> None:
    """Add repos to a watchlist collection.

    \b
    Examples:
      vein study watchlist add study_llm simonw/llm BerriAI/litellm
      vein study watchlist add study_mcp jlowin/fastmcp --purge-raw
    """
    store = VeinStore.require()
    data  = _load_watchlist(store)
    colls = data.setdefault("collections", {})
    coll  = colls.setdefault(collection, {
        "repos": [], "compare": compare, "purge_raw_after_compare": purge_raw,
    })
    existing = set(coll.get("repos", []))
    added = []
    for r in repos:
        r = r.strip().rstrip("/")
        if r not in existing:
            coll.setdefault("repos", []).append(r)
            existing.add(r)
            added.append(r)

    _save_watchlist(store, data)
    if added:
        console.print(f"[green]✓[/] Added {len(added)} repo(s) to [cyan]{collection}[/]: "
                      f"{', '.join(added)}")
    else:
        console.print(f"[dim]All repos already in [bold]{collection}[/].[/]")


@study_watchlist.command("list")
def watchlist_list() -> None:
    """Show all watchlists and their repos."""
    store = VeinStore.require()
    data  = _load_watchlist(store)
    colls = data.get("collections", {})

    if not colls:
        console.print("[dim]No watchlists. Run [bold]vein study watchlist add NAME repos...[/][/]")
        return

    for name, cfg in colls.items():
        repos   = cfg.get("repos", [])
        compare = cfg.get("compare", True)
        purge   = cfg.get("purge_raw_after_compare", False)
        flags   = []
        if compare: flags.append("compare")
        if purge:   flags.append("purge-raw")
        flag_str = f"  [dim]({', '.join(flags)})[/]" if flags else ""
        console.print(f"\n[bold cyan]{name}[/]{flag_str}")
        for r in repos:
            console.print(f"  {r}")


@study_watchlist.command("run")
@click.argument("collection", required=False, default="")
@click.option("--model",     default="", help="Override ollama model")
@click.option("--max-files", default=8,  show_default=True)
@click.option("--dry-run",   is_flag=True)
def watchlist_run(collection: str, model: str, max_files: int, dry_run: bool) -> None:
    """Fetch + compare all watchlists (or one). Used by night-harvest.

    \b
    Examples:
      vein study watchlist run              # run all watchlists
      vein study watchlist run study_llm    # run one
    """
    from click.testing import CliRunner
    store = VeinStore.require()
    data  = _load_watchlist(store)
    colls = data.get("collections", {})

    if not colls:
        console.print("[dim]No watchlists defined.[/]")
        return

    targets = {collection: colls[collection]} if collection and collection in colls else colls
    if collection and collection not in colls:
        console.print(f"[yellow]Watchlist [bold]{collection}[/] not found.[/]")
        return

    cfg_store = store.load_config()
    base_url    = cfg_store.get("model", {}).get("base_url", "http://localhost:11434")
    fetch_model = (model
                   or cfg_store.get("model", {}).get("fetch_model")
                   or cfg_store.get("model", {}).get("debrief_model", "qwen2.5-coder:7b"))
    embed_model = cfg_store.get("model", {}).get("embed_model", "nomic-embed-text")

    summary: list[str] = []

    for coll_name, coll_cfg in targets.items():
        repos      = coll_cfg.get("repos", [])
        do_compare = coll_cfg.get("compare", True)
        do_purge   = coll_cfg.get("purge_raw_after_compare", False)
        coll_tag   = f"study:{coll_name}"

        console.print(f"\n[bold]watchlist:[/] [cyan]{coll_name}[/] — {len(repos)} repo(s)")

        total = 0
        for raw in repos:
            try:
                clone_url, slug = _normalise_github(raw)
            except Exception:
                console.print(f"  [red]bad URL:[/] {raw}")
                continue
            console.print(f"  {slug} …", end=" ")
            entries = _fetch_one_repo(
                store=store, slug=slug, clone_url=clone_url,
                collection_tag=coll_tag, extra_tags=[],
                max_files=max_files, fetch_model=fetch_model,
                base_url=base_url, embed_model=embed_model,
                dry_run=dry_run, verbose=False,
            )
            n = len(entries)
            console.print(f"[green]✓[/] {n}" if n else "[dim]0[/]")
            total += n

        line = f"{coll_name}: {total} entries fetched"

        if do_compare and total > 0 and not dry_run:
            console.print(f"  [dim]comparing {coll_name}…[/]")
            # reuse compare logic inline
            all_entries = store.list_entries(status_filter="active")
            coll_entries = [e for e in all_entries if coll_tag in e.tags]
            by_repo: dict[str, list] = {}
            for e in coll_entries:
                s = e.source.removeprefix("github:")
                by_repo.setdefault(s, []).append(e)
            context = _build_compare_context(by_repo)
            cmp_model = (cfg_store.get("model", {}).get("compare_model")
                         or fetch_model)
            result = _call_ollama_compare(context, collection=coll_name,
                                          base_url=base_url, model=cmp_model)
            if result:
                entry = Entry.make(
                    type="reference",
                    title=f"study:{coll_name} — comparison",
                    body=result,
                    tags=["study", coll_tag, "compare", "auto"],
                    source=f"study:compare:{coll_name}",
                    volatility="external-fact",
                )
                store.write_entry(entry, auto_index=False)
                line += ", compare written"

                if do_purge:
                    raw_entries = [e for e in coll_entries
                                   if not e.source.startswith("study:compare:")]
                    purged = sum(1 for e in raw_entries if store.delete_entry(e))
                    line += f", {purged} raw purged"

        summary.append(line)

    console.print("\n[bold]watchlist run summary:[/]")
    for s in summary:
        console.print(f"  {s}")
