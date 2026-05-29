"""vein run — execute a command; on failure, auto-triage via vein + AI.

This is the "zero copy-paste" wrapper. Instead of:
  1. run command → fail
  2. copy error → open browser/Claude chat
  3. paste error, get answer
  4. copy command → paste into terminal

You just do:
  vein run cargo check
  vein run pytest tests/ --ai
  vein run "make build" --ai --log
"""

from __future__ import annotations

import subprocess
import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

from ..core.store import VeinStore
from ..core.triage import call_ollama_triage, extract_error_terms

console = Console()


@click.command("run")
@click.argument("cmd", nargs=-1, required=True)
@click.option("--ai", is_flag=True, help="Call local AI on failure if vein has no answer")
@click.option("--ai-always", is_flag=True, help="Always call AI on failure")
@click.option("--log", "-l", is_flag=True, help="Log failure as pitfall entry")
@click.option("--no-search", is_flag=True, help="Skip vein search on failure")
@click.option("--limit", "-n", default=3, show_default=True)
def cmd_run(
    cmd: tuple[str, ...],
    ai: bool,
    ai_always: bool,
    log: bool,
    no_search: bool,
    limit: int,
) -> None:
    """Run a command and auto-triage on failure.

    On success: exits 0, passthrough.
    On failure: searches .vein/ for known pitfalls, then optionally calls AI.

    \b
    Examples:
      vein run cargo check
      vein run pytest tests/ -q
      vein run "make build" --ai
      vein run npm install --ai --log
      vein run python -m vein status

    \b
    vs manual copy-paste loop:
      BEFORE: run → fail → copy → open chat → paste → copy fix → paste back
      AFTER:  vein run <cmd> --ai
    """
    full_cmd = " ".join(cmd)

    # run the command, streaming output to terminal
    console.print(f"[dim]$ {full_cmd}[/]")

    result = subprocess.run(
        full_cmd,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,   # merge stderr into stdout for display
    )

    # always print the output
    if result.stdout:
        click.echo(result.stdout, nl=False)

    if result.returncode == 0:
        sys.exit(0)

    # ── command failed ────────────────────────────────────────────
    console.print(Rule(f"[red]✗ exit {result.returncode}[/]  vein triage", style="dim red"))

    raw_output = result.stdout or ""
    error_digest = extract_error_terms(raw_output)

    # load store
    try:
        store = VeinStore.require()
    except RuntimeError:
        console.print("[yellow]No .vein/ — run `vein init` to enable lore search[/]")
        if ai or ai_always:
            _call_ai(full_cmd, error_digest, "", console=console)
        sys.exit(result.returncode)

    cfg = store.load_config()
    base_url     = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    polish_model = cfg.get("model", {}).get("polish_model", "qwen2.5-coder:7b")

    lore_hits: list = []
    lore_context = ""

    if not no_search:
        query = f"{full_cmd} {error_digest}".strip()
        lore_hits = store.grep_entries(query, limit=limit)

        # FTS fallback
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
            parts = []
            for entry, _ in lore_hits:
                color = {
                    "decision": "cyan", "lore": "green",
                    "pitfall": "yellow", "reference": "blue",
                }.get(entry.type, "white")
                console.print(Panel(
                    Markdown(entry.body) if entry.body else "[dim](no body)[/]",
                    title=f"[{color}]{entry.type}[/]  [bold]{entry.title}[/]",
                    border_style=color,
                    subtitle=f"[dim]{entry.date_str}[/]",
                ))
                parts.append(f"[{entry.type}] {entry.title}\n{entry.body[:400]}")
            lore_context = "\n\n".join(parts)
        else:
            console.print(
                "[dim]No matching entries in .vein/ — "
                "add [bold]--ai[/] for local AI triage[/]"
            )

    # AI triage
    if ai_always or (ai and not lore_hits):
        _call_ai(
            cmd=full_cmd,
            error_digest=error_digest,
            lore_context=lore_context,
            base_url=base_url,
            model=polish_model,
            console=console,
        )

    # optional: log as pitfall
    if log:
        _log_pitfall(store, full_cmd, error_digest, base_url)

    sys.exit(result.returncode)


def _call_ai(
    cmd: str,
    error_digest: str,
    lore_context: str,
    base_url: str = "http://localhost:11434",
    model: str = "qwen2.5-coder:7b",
    console: Console = None,
) -> None:
    if console is None:
        console = Console()
    console.print("\n[dim]Calling AI…[/] ", end="")
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
        console.print(
            "[yellow]AI unavailable[/] — ensure ollama is running:\n"
            "  ollama serve && ollama pull qwen2.5-coder:7b"
        )


def _log_pitfall(store, cmd: str, error_digest: str, base_url: str) -> None:
    from ..core.models import Entry
    from ..core.polish import auto_title

    title = auto_title(f"{cmd}: {error_digest}")
    body = (
        f"**Symptom:** `{cmd}` fails\n\n"
        f"**Root cause:** (fill in)\n\n"
        f"**Fix:** (fill in)\n\n"
        f"**Error log:**\n```\n{error_digest[:400]}\n```"
    )
    entry = Entry(
        id=Entry.new_id(), type="pitfall", title=title,
        tags=[], body=body, source="vein-run",
    )
    path = store.write_entry(entry, auto_index=True, base_url=base_url)
    console.print(f"\n[green]✓ Logged pitfall:[/] {path.name}")
    console.print(f"  [dim]Fill in root cause: {path}[/]")
