"""vein debrief — extract decisions from recent git diff using local AI.

Design philosophy:
  The best capture moment is AFTER a commit, not during.
  The diff is a complete record of "what changed". Local AI decides
  what's worth keeping. If no AI is available, silently skip.

Usage:
  vein debrief                    # diff since HEAD~1, interactive output
  vein debrief --since HEAD~3     # last 3 commits
  vein debrief --silent           # for post-commit hook (no output if nothing found)
  vein debrief --dry-run          # show what would be logged, don't write
  git diff HEAD~1 | vein debrief  # from stdin

Post-commit hook (installed by `vein hooks install`):
  cd /your/project && vein debrief --silent
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from ..core.models import Entry
from ..core.polish import fallback_polish
from ..core.store import VeinStore

console = Console()

# ── ollama prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a senior engineer analyzing a git diff to identify knowledge worth preserving.

Extract ONLY entries that would help a future developer (or AI) understand WHY
the code changed — not just WHAT changed.

Worth logging:
  decision — "why A not B": architecture, library choice, API design
  lore     — non-obvious behavior, external API quirks, workarounds
  pitfall  — things that went wrong; warnings for future developers

Do NOT log:
  - Routine refactors or renames with no decision behind them
  - Typo/formatting fixes
  - Changes that are obvious from reading the diff
  - Test additions without architectural insight

Output format: JSON array. Each item must have:
  {"type": "decision|lore|pitfall", "title": "short title", "body": "why this matters"}

If nothing is worth logging output exactly: []
"""

_DIFF_TOO_LARGE = 6000   # chars — trim diff if larger
_MAX_ENTRIES    = 5      # max entries per debrief run


def _get_diff(since: str) -> str | None:
    """Get git diff for the given revision range. Returns None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "diff", since, "--", ".", ":(exclude).vein"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            # HEAD~1 fails on first commit (only 1 commit in repo) — fallback to show HEAD
            result = subprocess.run(
                ["git", "show", "HEAD", "--", ".", ":(exclude).vein"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return None

        diff = result.stdout.strip()
        return diff or None
    except Exception:
        return None


def _trim_diff(diff: str) -> str:
    """Keep the most signal-dense parts of a large diff."""
    if len(diff) <= _DIFF_TOO_LARGE:
        return diff
    # keep first N chars (file headers + early hunks have most signal)
    return diff[:_DIFF_TOO_LARGE] + f"\n... (diff trimmed at {_DIFF_TOO_LARGE} chars)"


def _call_ollama_debrief(diff: str, base_url: str, model: str) -> list[dict] | None:
    """Ask ollama to extract decisions from a diff. Returns list of dicts or None."""
    try:
        import httpx
    except ImportError:
        return None

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": f"Git diff:\n\n```diff\n{diff}\n```"},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }

    try:
        resp = httpx.post(
            f"{base_url}/api/chat",
            json=payload,
            timeout=90.0,
        )
        resp.raise_for_status()
        raw = resp.json().get("message", {}).get("content", "").strip()

        # parse JSON — model might wrap in ```json blocks
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return None
        return parsed[:_MAX_ENTRIES]

    except Exception:
        return None


# ── command ───────────────────────────────────────────────────────────────────

@click.command("debrief")
@click.option("--since", default="HEAD~1", show_default=True,
              help="Git revision range (e.g. HEAD~3, main..HEAD)")
@click.option("--silent", is_flag=True,
              help="No output if nothing found (for post-commit hook)")
@click.option("--dry-run", is_flag=True,
              help="Show what would be logged without writing")
@click.option("--model", default="",
              help="Override ollama model (default: from config or qwen2.5-coder:7b)")
def cmd_debrief(since: str, silent: bool, dry_run: bool, model: str) -> None:
    """Extract decisions from recent git diff using local AI.

    Reads the diff since HEAD~1, asks a local ollama model to identify
    decisions worth capturing, and silently writes them to .vein/.

    Safe to use in post-commit hooks — exits silently if:
      · no .vein/ found
      · ollama is unavailable
      · diff has nothing worth logging

    \b
    Examples:
      vein debrief                     # review last commit
      vein debrief --since HEAD~5      # last 5 commits
      vein debrief --dry-run           # preview without writing
      git diff HEAD~1 | vein debrief   # from stdin
    """
    # ── find store (graceful: not all repos have .vein/) ────────────────
    store = VeinStore.find()
    if store is None:
        if not silent:
            console.print("[dim]vein debrief: no .vein/ found — run `vein init` first[/]")
        return

    cfg = store.load_config()
    base_url    = cfg.get("model", {}).get("base_url",      "http://localhost:11434")
    debrief_model = (
        model
        or cfg.get("model", {}).get("debrief_model")
        or cfg.get("model", {}).get("polish_model", "qwen2.5-coder:7b")
    )

    # ── get diff ─────────────────────────────────────────────────────────
    if not sys.stdin.isatty():
        diff = sys.stdin.read().strip()
    else:
        diff = _get_diff(since)

    if not diff:
        if not silent:
            console.print(f"[dim]vein debrief: no diff found for {since}[/]")
        return

    diff = _trim_diff(diff)

    # ── call ollama ───────────────────────────────────────────────────────
    if not silent:
        console.print(f"[dim]debrief: analysing diff with {debrief_model}…[/]", end=" ")

    results = _call_ollama_debrief(diff, base_url=base_url, model=debrief_model)

    if results is None:
        if not silent:
            console.print("[yellow]ollama unavailable — skipped[/]")
        return

    if not results:
        if not silent:
            console.print("[dim]nothing worth logging[/]")
        return

    if not silent:
        console.print(f"[green]✓[/] {len(results)} entr{'y' if len(results)==1 else 'ies'} found")

    # ── write entries ─────────────────────────────────────────────────────
    written = []
    for item in results:
        raw_type = item.get("type", "lore")
        valid = ("decision", "lore", "pitfall", "reference")
        if raw_type not in valid:
            raw_type = "lore"

        title = item.get("title", "").strip()
        body  = item.get("body",  "").strip()
        if not title:
            continue

        if dry_run:
            console.print(Panel(
                f"**type:** {raw_type}\n\n{body}",
                title=f"[cyan]{title}[/]",
                border_style="dim",
                subtitle="[dim]dry-run — not written[/]",
            ))
            continue

        # use fallback_polish to build structured body if body is short
        if len(body) < 80:
            draft = fallback_polish(f"{title}. {body}", raw_type)  # type: ignore[arg-type]
            body = draft.get("body", body)

        entry = Entry.make(
            type=raw_type,     # type: ignore[arg-type]
            title=title,
            body=body,
            tags=["debrief", "auto"],
            source="debrief",
        )
        path = store.write_entry(entry)
        written.append((entry, path))

    if written and not silent:
        console.print()
        for entry, path in written:
            console.print(
                f"  [green]✓[/] [{entry.type}] [bold]{entry.title}[/]\n"
                f"    [dim]{path.relative_to(store.root)}[/]"
            )
        console.print(
            f"\n[dim]Run [bold]vein reindex[/] to make these searchable.[/]"
        )
    elif written and silent:
        # silent mode: write a one-liner to stderr so user can see it in terminal
        # but it won't interrupt scripts
        n = len(written)
        print(f"vein: debrief captured {n} entr{'y' if n==1 else 'ies'}", file=sys.stderr)
