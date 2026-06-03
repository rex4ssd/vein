"""vein fetch — ingest key insights from a GitHub repo into .vein/references/.

Usage:
  vein fetch owner/repo
  vein fetch https://github.com/owner/repo
  vein fetch owner/repo --dry-run
  vein fetch owner/repo --tag project:vein --tag ai-tools
  vein fetch owner/repo --max-files 15

Design:
  - Clones repo (depth=1) to a temp dir, walks README + docs, calls ollama,
    extracts reference/decision/lore/pitfall entries, writes to .vein/.
  - If ollama unavailable: falls back to a single reference entry from README.
  - Temp dir cleaned up on exit regardless of outcome.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from ..core.models import Entry
from ..core.polish import fallback_polish
from ..core.store import VeinStore

console = Console()

_MAX_CONTENT_CHARS = 8_000   # chars sent to ollama
_MAX_ENTRIES       = 6       # max entries per fetch

# Candidate file patterns to collect from repo (in priority order)
_CANDIDATE_PATTERNS = [
    "README.md", "README.rst", "README.txt", "Readme.md",
    "ARCHITECTURE.md", "DESIGN.md", "DECISIONS.md",
    "WHY.md", "RATIONALE.md", "OVERVIEW.md",
    "CHANGELOG.md", "docs/README.md",
]
_DOCS_GLOB = "docs/**/*.md"

_SYSTEM_PROMPT = """\
You are a senior engineer reading documentation for an open-source GitHub project.
Your job is to extract useful knowledge entries from the docs.

Output format: JSON array. Each item must have:
  {"type": "reference|decision|lore|pitfall", "title": "short title", "body": "2-4 sentence insight"}

Type guide:
  reference — what this project does, its positioning vs alternatives, when to use it
  decision  — a design choice the authors made and why (trade-offs)
  lore      — non-obvious behavior, integration quirks, patterns worth knowing
  pitfall   — known limitations, gotchas, common failure modes

Rules:
  - Output 3-6 entries. When in doubt, include it — a broad reference entry is better than nothing.
  - Always include at least one "reference" entry summarising what the project does.
  - Body should be 2-4 sentences of synthesised insight, not copy-pasted README text.
  - Output a valid JSON array even if the docs are thin.
"""


# ── GitHub URL normalisation ──────────────────────────────────────────────────

def _normalise_github(source: str) -> tuple[str, str]:
    """Return (clone_url, display_slug) from user input.

    Accepts:
      owner/repo
      https://github.com/owner/repo
      github.com/owner/repo
    """
    source = source.strip().rstrip("/")

    # strip trailing .git
    if source.endswith(".git"):
        source = source[:-4]

    # already a full URL
    if source.startswith("https://github.com/"):
        slug = source.removeprefix("https://github.com/")
        return f"https://github.com/{slug}.git", slug

    # github.com/owner/repo
    if source.startswith("github.com/"):
        slug = source.removeprefix("github.com/")
        return f"https://github.com/{slug}.git", slug

    # owner/repo shorthand
    if re.match(r"^[\w.\-]+/[\w.\-]+$", source):
        return f"https://github.com/{source}.git", source

    raise click.BadParameter(
        f"Cannot parse GitHub source: {source!r}\n"
        "  Expected: owner/repo  or  https://github.com/owner/repo"
    )


# ── repo content collection ───────────────────────────────────────────────────

def _collect_files(repo_root: Path, max_files: int) -> list[Path]:
    """Return up to max_files candidate .md files, priority order.

    Uses resolved paths for dedup — handles macOS case-insensitive filesystem
    where README.md and Readme.md resolve to the same inode.
    """
    seen: set[Path] = set()   # resolved (real) paths
    result: list[Path] = []

    def _add(p: Path) -> bool:
        real = p.resolve()
        if real in seen:
            return False
        seen.add(real)
        result.append(p)
        return True

    # priority candidates
    for pattern in _CANDIDATE_PATTERNS:
        p = repo_root / pattern
        if p.exists():
            _add(p)
            if len(result) >= max_files:
                return result

    # docs/**/*.md
    for p in sorted(repo_root.glob(_DOCS_GLOB)):
        _add(p)
        if len(result) >= max_files:
            break

    return result


def _build_content(files: list[Path], max_chars: int) -> str:
    """Concatenate file contents, trimming to max_chars total."""
    parts: list[str] = []
    total = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        header = f"\n\n### {f.name}\n\n"
        chunk = (header + text)[:max_chars - total]
        parts.append(chunk)
        total += len(chunk)
        if total >= max_chars:
            parts.append(f"\n\n... (content trimmed at {max_chars} chars)")
            break
    return "".join(parts).strip()


# ── ollama call ───────────────────────────────────────────────────────────────

def _call_ollama_fetch(content: str, base_url: str, model: str,
                       verbose: bool = False) -> list[dict] | None:
    """Call ollama to extract insights. Returns list, [], or None (unavailable)."""
    try:
        import httpx
    except ImportError:
        return None

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": f"Project documentation:\n\n{content}"},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }

    try:
        resp = httpx.post(f"{base_url}/api/chat", json=payload, timeout=120.0)
        resp.raise_for_status()
        raw = resp.json().get("message", {}).get("content", "").strip()
        if verbose:
            print(f"\n[ollama raw]\n{raw[:1000]}\n")

        # strip ```json fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed = json.loads(raw)

        if isinstance(parsed, dict):
            for key in ("entries", "items", "results", "references"):
                if isinstance(parsed.get(key), list):
                    parsed = parsed[key]
                    break
            else:
                return []

        if not isinstance(parsed, list):
            return []

        valid = [item for item in parsed if isinstance(item, dict) and item.get("title")]
        return valid[:_MAX_ENTRIES]

    except (httpx.ConnectError, httpx.TimeoutException):
        return None
    except Exception:
        return []


# ── fallback: build one reference entry from README ───────────────────────────

def _readme_fallback(files: list[Path], slug: str) -> list[dict]:
    """If ollama unavailable, build a minimal reference entry from README."""
    for f in files:
        if f.name.lower().startswith("readme"):
            text = f.read_text(encoding="utf-8", errors="replace")
            # grab first 600 chars of body (skip heading)
            lines = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
            body = " ".join(lines)[:600]
            if body:
                return [{"type": "reference", "title": f"{slug} — overview", "body": body}]
    return [{"type": "reference", "title": f"{slug} — fetched", "body": "(no README found)"}]


# ── command ───────────────────────────────────────────────────────────────────

@click.command("fetch")
@click.argument("source")
@click.option("--dry-run", is_flag=True,
              help="Show what would be extracted, don't write")
@click.option("--no-index", is_flag=True,
              help="Skip embedding index update")
@click.option("--tag", "extra_tags", multiple=True,
              help="Extra tag(s) to add to all entries (repeatable)")
@click.option("--max-files", default=8, show_default=True,
              help="Max number of repo files to read")
@click.option("--model", default="",
              help="Override ollama model (e.g. deepseek-r1:14b)")
@click.option("--verbose", "-v", is_flag=True,
              help="Show raw ollama response (debug)")
@click.option("--force", "-f", is_flag=True,
              help="Re-fetch even if this repo was already fetched (overwrites existing entries)")
def cmd_fetch(
    source: str,
    dry_run: bool,
    no_index: bool,
    extra_tags: tuple[str, ...],
    max_files: int,
    model: str,
    verbose: bool,
    force: bool,
) -> None:
    """Fetch a GitHub repo and extract key insights into .vein/references/.

    SOURCE: owner/repo  or  https://github.com/owner/repo

    \b
    Examples:
      vein fetch pallets/click
      vein fetch https://github.com/BerriAI/litellm
      vein fetch tiangolo/fastapi --dry-run
      vein fetch simonw/llm --tag ai-tools --tag python
      vein fetch simonw/llm --force          re-fetch and overwrite existing entries
    """
    store = VeinStore.require()
    cfg = store.load_config()
    base_url      = cfg.get("model", {}).get("base_url",      "http://localhost:11434")
    fetch_model   = (
        model
        or cfg.get("model", {}).get("fetch_model")
        or cfg.get("model", {}).get("debrief_model")
        or cfg.get("model", {}).get("polish_model", "qwen2.5-coder:7b")
    )

    # normalise source
    try:
        clone_url, slug = _normalise_github(source)
    except click.BadParameter as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    github_url = clone_url.removesuffix(".git")

    # ── dedup check ───────────────────────────────────────────────────────────
    repo_tag = f"source:github/{slug}"
    existing = [e for e in store.iter_entries() if repo_tag in e.tags]
    if existing and not force and not dry_run:
        console.print(
            f"[yellow]Already fetched:[/] {slug} "
            f"({len(existing)} entr{'y' if len(existing) == 1 else 'ies'} in .vein/)\n"
            f"  Re-run with [bold]--force[/] to overwrite, "
            f"or [bold]--dry-run[/] to preview without writing."
        )
        raise SystemExit(0)

    if existing and force:
        # delete old entries before re-fetch
        deleted = 0
        for e in existing:
            try:
                if e._path and e._path.exists():
                    e._path.unlink()
                    deleted += 1
            except Exception:
                pass
        if deleted:
            console.print(f"[dim]--force: removed {deleted} existing entr{'y' if deleted == 1 else 'ies'} for {slug}[/]")

    console.print(f"[dim]fetch:[/] [bold]{slug}[/]  →  {github_url}")

    # ── clone to temp dir ─────────────────────────────────────────────────────
    tmpdir = tempfile.mkdtemp(prefix="vein-fetch-")
    try:
        console.print(f"[dim]cloning (depth=1)…[/]", end=" ")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", clone_url, tmpdir],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            console.print(f"[red]clone failed[/]")
            console.print(f"[dim]{result.stderr.strip()[:200]}[/]")
            raise SystemExit(1)
        console.print("[green]✓[/]")

        repo_root = Path(tmpdir)

        # ── collect files ─────────────────────────────────────────────────────
        files = _collect_files(repo_root, max_files)
        if not files:
            console.print("[yellow]No markdown files found in repo.[/]")
            raise SystemExit(0)

        console.print(
            f"[dim]reading {len(files)} file(s): "
            f"{', '.join(f.name for f in files[:5])}"
            f"{'…' if len(files) > 5 else ''}[/]"
        )

        content = _build_content(files, _MAX_CONTENT_CHARS)

        # ── call ollama ───────────────────────────────────────────────────────
        console.print(f"[dim]analysing with {fetch_model}…[/]", end=" ")
        results = _call_ollama_fetch(content, base_url=base_url, model=fetch_model,
                                     verbose=verbose)

        if results is None:
            console.print("[yellow]ollama unavailable — using README fallback[/]")
            results = _readme_fallback(files, slug)
        elif not results:
            console.print("[dim]nothing insightful extracted[/]")
            console.print(
                "[dim]Tip: try [bold]--verbose[/] to see raw response, "
                "or [bold]--model deepseek-r1:14b[/] for a stronger model.[/]"
            )
            raise SystemExit(0)
        else:
            console.print(f"[green]✓[/] {len(results)} insight(s) found")

        # ── build tags ────────────────────────────────────────────────────────
        repo_tag  = f"source:github/{slug}"
        base_tags = ["fetch", "github", repo_tag] + list(extra_tags)

        # ── write entries ─────────────────────────────────────────────────────
        written = []
        for item in results:
            raw_type = item.get("type", "reference")
            if raw_type not in ("decision", "lore", "pitfall", "reference"):
                raw_type = "reference"

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

            # enrich short bodies
            if len(body) < 80:
                draft = fallback_polish(f"{title}. {body}", raw_type)  # type: ignore[arg-type]
                body  = draft.get("body", body)

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
                path = store.write_entry(
                    entry,
                    auto_index=(not no_index),
                    base_url=base_url,
                    embed_model=cfg.get("model", {}).get("embed_model", "nomic-embed-text"),
                )
                written.append((entry, path))
            except Exception as exc:
                console.print(f"[red]Failed to write:[/] {title[:60]} — {exc}")

        if dry_run:
            return

        if written:
            console.print()
            for entry, path in written:
                console.print(
                    f"  [green]✓[/] [{entry.type}] [bold]{entry.title}[/]\n"
                    f"    [dim]{path.relative_to(store.root)}[/]"
                )
            console.print(
                f"\n[dim]Run [bold]vein recall {slug.split('/')[-1]}[/] "
                f"to search these entries.[/]"
            )
        else:
            console.print("[yellow]Nothing written.[/]")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
