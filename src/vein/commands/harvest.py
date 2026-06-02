"""vein night-harvest + vein morning — nightly pipeline + morning report.

Night pipeline (run via cron or vein schedule):
  vein night-harvest
    1. Run all watchlists (fetch + compare + optional purge)
    2. Run vein debrief on recent commits
    3. Generate morning brief (< 100 lines) → .vein/lore/morning-YYYY-MM-DD.md

Morning report:
  vein morning
    Print today's morning brief. If not generated yet, generate on the fly.

Usage:
  vein night-harvest
  vein night-harvest --since HEAD~5 --purge-raw
  vein morning
  vein morning --date 2026-05-31

Cron example (02:00 daily):
  0 2 * * *  cd /Users/lion/Documents/vein && vein night-harvest >> ~/.vein-harvest.log 2>&1
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from ..core.models import Entry
from ..core.store import VeinStore

console = Console()

_MORNING_MAX_LINES = 80   # hard cap for morning brief

_HARVEST_PROMPT = """\
You are summarizing a day's worth of project knowledge entries for a developer's morning brief.

Entries captured in the last 24 hours:
{entries_block}

Write a morning brief in markdown. Format:
## New Insights ({count} entries)
- bullet per notable insight (max 15 bullets, one line each)

## Pitfalls & Warnings
- only if there are pitfall entries (else omit this section)

## Studies Updated
- list collections that got new compare summaries (else omit)

## Suggested Actions
- 2-4 concrete next steps based on what was learned

Rules:
- Total output MUST be under {max_lines} lines
- Be direct, no fluff, engineer tone
- Prioritise pitfalls > decisions > lore > references
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def _entries_since(store: VeinStore, hours: int = 24) -> list[Entry]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    all_e  = store.list_entries(status_filter="active")
    return [e for e in all_e
            if (e.date.replace(tzinfo=timezone.utc) if e.date.tzinfo is None else e.date)
            >= cutoff]


def _build_entries_block(entries: list[Entry], max_chars: int = 5000) -> str:
    # prioritise pitfalls > decisions > lore > references
    order = {"pitfall": 0, "decision": 1, "lore": 2, "reference": 3}
    sorted_e = sorted(entries, key=lambda e: order.get(e.type, 4))
    parts: list[str] = []
    total = 0
    for e in sorted_e:
        body_snip = e.body[:200].replace("\n", " ")
        line = f"[{e.type}] {e.title}: {body_snip}"
        if total + len(line) > max_chars:
            break
        parts.append(line)
        total += len(line)
    return "\n".join(parts)


def _call_ollama_harvest(entries_block: str, count: int,
                          base_url: str, model: str) -> str | None:
    try:
        import httpx
    except ImportError:
        return None

    prompt = _HARVEST_PROMPT.format(
        entries_block=entries_block,
        count=count,
        max_lines=_MORNING_MAX_LINES,
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.15},
    }
    try:
        resp = httpx.post(f"{base_url}/api/chat", json=payload, timeout=180.0)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip() or None
    except Exception:
        return None


def _morning_path(store: VeinStore, date: str) -> Path:
    return store.vein_dir / "lore" / f"morning-{date}.md"


def _run_debrief(store: VeinStore, since: str, model: str, base_url: str) -> int:
    """Run vein debrief programmatically. Returns number of entries written."""
    from .debrief import _get_diff, _trim_diff, _call_ollama_debrief
    from ..core.polish import fallback_polish

    diff = _get_diff(since)
    if not diff:
        return 0
    diff = _trim_diff(diff)
    cfg = store.load_config()
    debrief_model = model or cfg.get("model", {}).get("debrief_model", "qwen2.5-coder:7b")
    results = _call_ollama_debrief(diff, base_url=base_url, model=debrief_model)
    if not results:
        return 0

    written = 0
    for item in results:
        raw_type = item.get("type", "lore")
        if raw_type not in ("decision", "lore", "pitfall", "reference"):
            raw_type = "lore"
        title = item.get("title", "").strip()
        body  = item.get("body",  "").strip()
        if not title:
            continue
        if len(body) < 80:
            draft = fallback_polish(f"{title}. {body}", raw_type)  # type: ignore
            body  = draft.get("body", body)
        entry = Entry.make(
            type=raw_type,       # type: ignore
            title=title, body=body,
            tags=["debrief", "auto"],
            source="debrief",
        )
        store.write_entry(entry, auto_index=False)
        written += 1
    return written


# ── night-harvest ─────────────────────────────────────────────────────────────

@click.command("night-harvest")
@click.option("--since",     default="HEAD~1", show_default=True,
              help="Git revision range for debrief step")
@click.option("--purge-raw", is_flag=True,
              help="Purge raw fetch entries after compare (overrides watchlist config)")
@click.option("--model",     default="",
              help="Override ollama model for all steps")
@click.option("--no-debrief",   is_flag=True, help="Skip the debrief step")
@click.option("--no-watchlist", is_flag=True, help="Skip the watchlist step")
@click.option("--hours",     default=24, show_default=True,
              help="Look-back window for morning brief (hours)")
def cmd_night_harvest(
    since: str,
    purge_raw: bool,
    model: str,
    no_debrief: bool,
    no_watchlist: bool,
    hours: int,
) -> None:
    """Run the nightly pipeline: watchlists → debrief → morning brief.

    Designed to run unattended via cron at ~02:00.

    \b
    Examples:
      vein night-harvest
      vein night-harvest --since HEAD~3 --purge-raw
      vein night-harvest --no-watchlist   # debrief + brief only
    """
    store = VeinStore.require()
    cfg   = store.load_config()
    base_url    = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    fetch_model = model or cfg.get("model", {}).get("fetch_model", "qwen2.5-coder:7b")
    brief_model = model or cfg.get("model", {}).get("analyze_model",
                  cfg.get("model", {}).get("fetch_model", "qwen2.5-coder:7b"))

    today = datetime.now().strftime("%Y-%m-%d")
    log: list[str] = [f"# night-harvest {today}\n"]

    console.print(f"\n[bold cyan]vein night-harvest[/] {today}\n")

    # ── step 1: watchlists ─────────────────────────────────────────────────
    if not no_watchlist:
        console.print("[bold]Step 1:[/] watchlists")
        from .study import _load_watchlist, _fetch_one_repo, _build_compare_context, _call_ollama_compare, _normalise_github
        import click as _click

        data  = _load_watchlist(store)
        colls = data.get("collections", {})

        if not colls:
            console.print("  [dim]No watchlists configured.[/]")
            log.append("watchlists: none configured")
        else:
            embed_model = cfg.get("model", {}).get("embed_model", "nomic-embed-text")
            for coll_name, coll_cfg in colls.items():
                repos    = coll_cfg.get("repos", [])
                do_cmp   = coll_cfg.get("compare", True)
                do_purge = purge_raw or coll_cfg.get("purge_raw_after_compare", False)
                coll_tag = f"study:{coll_name}"
                total = 0

                console.print(f"  [cyan]{coll_name}[/] ({len(repos)} repos)")
                for raw in repos:
                    try:
                        clone_url, slug = _normalise_github(raw)
                    except Exception:
                        continue
                    entries = _fetch_one_repo(
                        store=store, slug=slug, clone_url=clone_url,
                        collection_tag=coll_tag, extra_tags=[],
                        max_files=8, fetch_model=fetch_model,
                        base_url=base_url, embed_model=embed_model,
                        dry_run=False, verbose=False,
                    )
                    total += len(entries)
                    console.print(f"    {slug}: {len(entries)}", end="  ")
                console.print()

                line = f"watchlist {coll_name}: {total} entries"
                if do_cmp and total > 0:
                    all_e    = store.list_entries(status_filter="active")
                    coll_e   = [e for e in all_e if coll_tag in e.tags]
                    by_repo  = {}
                    for e in coll_e:
                        s = e.source.removeprefix("github:")
                        by_repo.setdefault(s, []).append(e)
                    ctx    = _build_compare_context(by_repo)
                    result = _call_ollama_compare(ctx, collection=coll_name,
                                                  base_url=base_url, model=fetch_model)
                    if result:
                        cmp_entry = Entry.make(
                            type="reference",
                            title=f"study:{coll_name} — comparison",
                            body=result,
                            tags=["study", coll_tag, "compare", "auto"],
                            source=f"study:compare:{coll_name}",
                            volatility="external-fact",
                        )
                        store.write_entry(cmp_entry, auto_index=False)
                        line += ", compare written"

                        if do_purge:
                            raw_entries = [e for e in coll_e
                                           if not e.source.startswith("study:compare:")]
                            purged = sum(1 for e in raw_entries if store.delete_entry(e))
                            line += f", {purged} raw purged"
                log.append(line)
    else:
        log.append("watchlists: skipped")

    # ── step 2: debrief ────────────────────────────────────────────────────
    if not no_debrief:
        console.print("\n[bold]Step 2:[/] debrief")
        n = _run_debrief(store, since=since, model=model, base_url=base_url)
        console.print(f"  {n} entries from git diff")
        log.append(f"debrief: {n} entries")
    else:
        log.append("debrief: skipped")

    # ── step 3: morning brief ──────────────────────────────────────────────
    console.print("\n[bold]Step 3:[/] morning brief")
    recent = _entries_since(store, hours=hours)
    console.print(f"  {len(recent)} entries in last {hours}h")

    if not recent:
        console.print("  [dim]Nothing to brief.[/]")
        log.append("morning brief: no entries")
    else:
        block  = _build_entries_block(recent)
        result = _call_ollama_harvest(block, count=len(recent),
                                      base_url=base_url, model=brief_model)
        if result:
            # enforce line cap
            lines = result.splitlines()
            if len(lines) > _MORNING_MAX_LINES:
                lines = lines[:_MORNING_MAX_LINES]
                lines.append(f"\n*[truncated at {_MORNING_MAX_LINES} lines]*")
            result = "\n".join(lines)

            brief_md = (
                f"# Morning Brief — {today}\n"
                f"*Generated by `vein night-harvest` · {len(recent)} entries · "
                f"{datetime.now().strftime('%H:%M')}*\n\n"
                + result
            )

            # write to .vein/lore/morning-YYYY-MM-DD.md
            out_path = _morning_path(store, today)
            out_path.write_text(brief_md, encoding="utf-8")
            console.print(f"  [green]✓[/] Brief written → {out_path.relative_to(store.root)}")
            log.append(f"morning brief: {len(result.splitlines())} lines → {out_path.name}")
        else:
            console.print("  [yellow]ollama unavailable — brief skipped[/]")
            log.append("morning brief: ollama unavailable")

    # ── harvest log entry ──────────────────────────────────────────────────
    harvest_entry = Entry.make(
        type="lore",
        title=f"night-harvest {today}",
        body="\n".join(log),
        tags=["harvest", "auto", "nightly"],
        source="night-harvest",
        volatility="external-fact",
    )
    store.write_entry(harvest_entry, auto_index=False)
    console.print(f"\n[dim]Harvest log saved.[/]")


# ── morning ───────────────────────────────────────────────────────────────────

@click.command("morning")
@click.option("--date", default="",
              help="Date to show (YYYY-MM-DD, default: today)")
@click.option("--generate", is_flag=True,
              help="Re-generate even if today's brief already exists")
@click.option("--hours", default=24, show_default=True,
              help="Look-back window when generating (hours)")
def cmd_morning(date: str, generate: bool, hours: int) -> None:
    """Print today's morning brief (< 100 lines).

    Generated by `vein night-harvest`. If not yet generated today,
    runs a quick on-demand generation.

    \b
    Examples:
      vein morning
      vein morning --date 2026-05-31
      vein morning --generate       # force re-generation
    """
    store = VeinStore.require()
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    brief_path  = _morning_path(store, target_date)

    if brief_path.exists() and not generate:
        console.print(brief_path.read_text(encoding="utf-8"))
        return

    # not found or force re-generate
    console.print(f"[dim]No brief for {target_date} — generating on-demand…[/]\n")

    cfg = store.load_config()
    base_url    = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    brief_model = (cfg.get("model", {}).get("analyze_model")
                   or cfg.get("model", {}).get("fetch_model", "qwen2.5-coder:7b"))

    recent = _entries_since(store, hours=hours)
    if not recent:
        console.print(f"[dim]No entries in the last {hours}h.[/]")
        return

    block  = _build_entries_block(recent)
    result = _call_ollama_harvest(block, count=len(recent),
                                   base_url=base_url, model=brief_model)
    if not result:
        console.print("[yellow]ollama unavailable.[/] Try [bold]vein list --since 24h[/] instead.")
        return

    lines = result.splitlines()
    if len(lines) > _MORNING_MAX_LINES:
        lines = lines[:_MORNING_MAX_LINES]
        lines.append(f"\n*[truncated at {_MORNING_MAX_LINES} lines]*")
    result = "\n".join(lines)

    brief_md = (
        f"# Morning Brief — {target_date}\n"
        f"*on-demand · {len(recent)} entries · {datetime.now().strftime('%H:%M')}*\n\n"
        + result
    )
    brief_path.write_text(brief_md, encoding="utf-8")
    console.print(brief_md)
