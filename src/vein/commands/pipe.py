"""vein pipe — pipe error output → search vein → optional AI triage.

Usage:
    cargo check 2>&1          | vein pipe
    pytest tests/ 2>&1        | vein pipe --cmd "pytest tests/"
    make build 2>&1           | vein pipe --ai
    cat build.log             | vein pipe --log

This eliminates the manual copy-paste loop:
  fail → copy error → open browser/chat → paste → copy fix → paste back
becomes:
  fail → pipe to vein → instant answer from project lore (or AI)
"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

from ..core.store import VeinStore
from ..core.triage import call_ollama_triage, extract_error_terms

console = Console()


@click.command("pipe")
@click.option("--cmd", "-c", default="", help="The command that produced this output")
@click.option("--ai", is_flag=True, help="Call local AI (ollama) if vein has no answer")
@click.option("--ai-always", is_flag=True, help="Always call AI, even if vein has a match")
@click.option("--log", "-l", is_flag=True,
              help="Log this failure as a pitfall entry after triage")
@click.option("--no-search", is_flag=True, help="Skip vein search, go straight to AI")
@click.option("--limit", "-n", default=3, show_default=True)
def cmd_pipe(
    cmd: str,
    ai: bool,
    ai_always: bool,
    log: bool,
    no_search: bool,
    limit: int,
) -> None:
    """Pipe an error log into vein for instant triage.

    Reads stdin, extracts key error terms, searches .vein/ for known pitfalls,
    and optionally calls local AI (ollama) for a fix suggestion.

    \b
    Examples:
      cargo check 2>&1          | vein pipe
      pytest -q 2>&1            | vein pipe --cmd "pytest"
      make build 2>&1           | vein pipe --ai
      cat build.log             | vein pipe --ai-always

    \b
    Shell alias (add to ~/.zshrc):
      alias vp='vein pipe'
      # then: cargo check 2>&1 | vp --ai
    """
    # read stdin
    raw_log = sys.stdin.read()
    if not raw_log.strip():
        console.print("[yellow]vein pipe: no input received on stdin[/]")
        return

    # show the raw log so user still sees it
    console.print(raw_log, end="", highlight=False)
    console.print(Rule("[dim]vein triage[/]", style="dim"))

    # extract signal
    error_digest = extract_error_terms(raw_log)

    # load store
    try:
        store = VeinStore.require()
    except RuntimeError:
        console.print("[yellow]No .vein/ found — run `vein init` first.[/]")
        if ai or ai_always:
            _call_ai(cmd, error_digest, lore_context="", store=None)
        return

    cfg = store.load_config()
    base_url    = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    polish_model = cfg.get("model", {}).get("polish_model", "qwen2.5-coder:7b")

    # ── 1. search vein ────────────────────────────────────────────
    lore_hits: list = []
    if not no_search:
        query = f"{cmd} {error_digest}".strip()
        lore_hits = store.grep_entries(query, limit=limit)

        # also try FTS index
        if not lore_hits:
            try:
                idx = store.open_index()
                hit_ids = idx.fts_search(error_digest[:200], k=limit)
                idx.close()
                for eid in hit_ids:
                    try:
                        lore_hits.append((store.read_entry(eid), 1))
                    except Exception:
                        pass
            except Exception:
                pass

    if lore_hits:
        console.print(f"\n[bold yellow]⚡ Found in project lore:[/]\n")
        lore_context_parts = []
        for entry, _score in lore_hits:
            color = {"decision": "cyan", "lore": "green",
                     "pitfall": "yellow", "reference": "blue"}.get(entry.type, "white")
            console.print(Panel(
                Markdown(entry.body) if entry.body else "[dim](no body)[/]",
                title=f"[{color}]{entry.type}[/]  [bold]{entry.title}[/]",
                border_style=color,
                subtitle=f"[dim]{entry.date_str}[/]",
            ))
            lore_context_parts.append(f"[{entry.type}] {entry.title}\n{entry.body[:400]}")
        lore_context = "\n\n".join(lore_context_parts)
    else:
        lore_context = ""
        console.print("[dim]No matching entries in .vein/ — [/]", end="")
        if not (ai or ai_always):
            console.print(
                "[dim]run with [bold]--ai[/] to call local AI, "
                "or [bold]vein log p[/] to capture this as a pitfall[/]"
            )

    # ── 2. AI triage ─────────────────────────────────────────────
    if ai_always or (ai and not lore_hits):
        _call_ai(
            cmd=cmd,
            error_digest=error_digest,
            lore_context=lore_context,
            base_url=base_url,
            model=polish_model,
            store=store,
        )

    # ── 3. optional: log as pitfall ───────────────────────────────
    if log:
        console.print(Rule("[dim]capture[/]", style="dim"))
        _log_as_pitfall(store, cmd, error_digest, base_url, polish_model)


def _call_ai(
    cmd: str,
    error_digest: str,
    lore_context: str,
    base_url: str = "http://localhost:11434",
    model: str = "qwen2.5-coder:7b",
    store=None,
) -> None:
    console.print("[dim]Calling AI…[/] ", end="")
    fix = call_ollama_triage(
        cmd=cmd,
        error_digest=error_digest,
        lore_context=lore_context,
        base_url=base_url,
        model=model,
    )
    if fix:
        console.print()
        console.print(Panel(
            Markdown(fix),
            title="[bold green]AI suggestion[/]  [dim](qwen2.5-coder:7b · local)[/]",
            border_style="green",
        ))
    else:
        console.print("[yellow]AI unavailable[/] — ensure ollama is running:\n"
                      "  ollama serve")


def _log_as_pitfall(store, cmd: str, error_digest: str,
                    base_url: str, model: str) -> None:
    """Quick-log this failure as a pitfall entry (no interactive confirm)."""
    from ..core.models import Entry
    from ..core.polish import auto_title

    title = auto_title(f"{cmd}: {error_digest}") if cmd else auto_title(error_digest)
    body = (
        f"**Symptom:** `{cmd}` fails\n\n"
        f"**Root cause:** (fill in)\n\n"
        f"**Fix:** (fill in)\n\n"
        f"**Error log:**\n```\n{error_digest[:400]}\n```"
    )

    entry = Entry(
        id=Entry.new_id(),
        type="pitfall",
        title=title,
        tags=[],
        body=body,
        source="vein-pipe",
    )
    path = store.write_entry(entry, auto_index=True, base_url=base_url)
    console.print(f"[green]✓ Logged pitfall:[/] {path.name}")
    console.print(f"  [dim]Edit to fill in root cause + fix: {path}[/]")
