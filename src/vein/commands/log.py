"""vein log — capture a decision, lore, pitfall, or reference."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from ..core.config import load_ai_providers, load_env, get_local_config
from ..core.models import Entry, EntryType
from ..core.polish import (
    call_ollama_polish,
    fallback_polish,
    interactive_confirm,
)
from ..core.store import VeinStore

console = Console()

_TYPE_ALIASES = {
    "d": "decision", "dec": "decision",
    "l": "lore",
    "p": "pitfall", "pit": "pitfall",
    "r": "reference", "ref": "reference",
}


def _resolve_type(raw: str) -> EntryType:
    t = raw.lower().strip()
    return _TYPE_ALIASES.get(t, t)  # type: ignore[return-value]


@click.command("log")
@click.argument("entry_type", metavar="TYPE")
@click.argument("message", required=False)
@click.option("--tag", "-t", multiple=True, help="Add a tag (repeatable)")
@click.option("--no-polish", is_flag=True, help="Skip ollama polish, use raw input")
@click.option("--yes", "-y", is_flag=True, help="Auto-accept polish output")
@click.option("--source-url", default="", help="Source URL (web clipper)")
@click.option("--source-title", default="", help="Source page title")
@click.option("--related", multiple=True, help="Related entry IDs")
def cmd_log(
    entry_type: str,
    message: str | None,
    tag: tuple[str, ...],
    no_polish: bool,
    yes: bool,
    source_url: str,
    source_title: str,
    related: tuple[str, ...],
) -> None:
    """Capture a lore entry into .vein/.

    TYPE: decision (d) | lore (l) | pitfall (p) | reference (r)

    MESSAGE: raw text (reads from stdin if omitted)

    \b
    Examples:
      vein log decision "DMA uses callback not polling: SystemC is event-driven"
      vein log pitfall "Seed 0x42A3 reproduces the DMA race condition"
      vein log lore "gc_trigger_wait holds DMA lock — watch for deadlock"
      echo "long note..." | vein log decision
    """
    etype = _resolve_type(entry_type)
    valid_types = ("decision", "lore", "pitfall", "reference")
    if etype not in valid_types:
        raise click.BadParameter(
            f"Unknown type '{entry_type}'. Valid: {', '.join(valid_types)} (or d/l/p/r)",
            param_hint="TYPE",
        )

    # read message from stdin if not provided
    if not message:
        if not click.get_text_stream("stdin").isatty():
            message = click.get_text_stream("stdin").read().strip()
        else:
            message = click.prompt("Message")
    if not message:
        raise click.UsageError("No message provided.")

    store = VeinStore.require()
    load_env(store.root)
    providers = load_ai_providers(store.root)
    local_cfg = get_local_config(providers)

    base_url = local_cfg.get("base_url", "http://localhost:11434")
    polish_model = local_cfg.get("polish_model", "qwen2.5-coder:7b")

    # ── polish ──────────────────────────────────────────────────
    draft: dict | None = None

    if not no_polish:
        console.print(f"[dim]Polishing with {polish_model}…[/]", end=" ")
        results = call_ollama_polish(
            message,
            base_url=base_url,
            model=polish_model,
            hint_type=etype,
        )
        if results:
            console.print("[green]✓[/]")
            # handle multi-entry response
            if len(results) > 1:
                console.print(f"[yellow]ollama returned {len(results)} entries. Using first.[/]")
            draft = results[0]
            # enforce the hinted type
            draft["type"] = etype
        else:
            console.print("[yellow]ollama unavailable — using raw input[/]")

    if draft is None:
        draft = fallback_polish(message, etype)

    # merge explicit CLI tags
    existing_tags = draft.get("tags") or []
    for t in tag:
        if t not in existing_tags:
            existing_tags.append(t)
    draft["tags"] = existing_tags

    # ── confirm ─────────────────────────────────────────────────
    if yes or no_polish:
        confirmed = draft
    else:
        confirmed = interactive_confirm(draft, console=console)

    if confirmed is None:
        return  # aborted

    # ── build and write entry ────────────────────────────────────
    entry = Entry.make(
        type=confirmed["type"],
        title=confirmed.get("title", ""),
        body=confirmed.get("body", ""),
        tags=confirmed.get("tags", []),
        source="local",
        source_url=source_url,
        source_title=source_title,
        related=list(related),
    )

    path = store.write_entry(entry)
    console.print(f"\n[bold green]✓ Saved[/] [cyan]{entry.id}[/] → [dim]{path.relative_to(store.root)}[/]")
    console.print(f"  [bold]{entry.title}[/]")
    if entry.tags:
        console.print(f"  [dim]tags: {', '.join(entry.tags)}[/]")
