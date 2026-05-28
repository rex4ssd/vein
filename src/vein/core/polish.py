"""ollama polish — capture-time polish for vein log entries."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Entry

# ── prompt templates ──────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a technical lore archivist for software/hardware projects.
Your job: take raw engineer notes and convert them into structured, retrievable lore entries.

Rules:
- title: imperative form, ≤10 words, no generic words like "thing" or "issue"
- type: decision (a choice was made between alternatives),
        lore (an observation or behavior worth knowing),
        pitfall (a trap that causes bugs or wasted time),
        reference (an external resource with context for this project)
- tags: 3-5 tags, snake_case, specific over generic (prefer "dma_callback" over "architecture")
- body: markdown, sections depend on type:
    decision  → **Why:** (forces/constraints driving the choice) + **Trade-off:** (what you give up)
    lore      → **Observation:** + **Context:** (when does this matter)
    pitfall   → **Symptom:** + **Root cause:** + **Fix:** (may add **Reproduction:** if seed/steps known)
    reference → **Summary:** (why this matters to THIS project)
- If the input clearly contains multiple distinct topics, output an array of entries.

Output: JSON only. No text outside JSON.
JSON schema (single entry):
{
  "type": "decision|lore|pitfall|reference",
  "title": "...",
  "tags": ["...", "..."],
  "body": "**Why:** ...\\n\\n**Trade-off:** ..."
}
Or array: [{...}, {...}]
"""

_FEW_SHOTS = [
    {
        "role": "user",
        "content": "sqlite can't handle concurrent writes from multiple goroutines"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "type": "pitfall",
            "title": "SQLite rejects concurrent writes from multiple goroutines",
            "tags": ["sqlite", "concurrency", "goroutine", "database"],
            "body": (
                "**Symptom:** `database is locked` error under concurrent write load.\n\n"
                "**Root cause:** SQLite default journal mode (DELETE) uses file-level lock;"
                " concurrent writers serialize or fail.\n\n"
                "**Fix:** Use WAL mode (`PRAGMA journal_mode=WAL`) or serialize writes via"
                " a single writer goroutine."
            )
        })
    },
    {
        "role": "user",
        "content": "hal_dma_submit uses callback not polling because systemc is event-driven"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "type": "decision",
            "title": "HAL DMA API uses callback, not polling",
            "tags": ["dma", "hal", "systemc", "callback", "host_build"],
            "body": (
                "**Why:** SystemC DMA model is event-driven (`sc_event`); polling would"
                " busy-wait in HOST build, wasting simulation time. MP build's IRQ handler"
                " maps naturally to callback semantics.\n\n"
                "**Trade-off:** Callbacks require ISR context discipline."
                " Never call `hal_dma_submit` from within a callback — re-entrant callback hell."
            )
        })
    },
]


# ── ollama HTTP call ──────────────────────────────────────────────

def _build_messages(raw_text: str, hint_type: str | None = None) -> list[dict]:
    user_msg = raw_text
    if hint_type:
        user_msg = f"[hint: this is probably a {hint_type}]\n{raw_text}"
    return [
        *_FEW_SHOTS,
        {"role": "user", "content": user_msg},
    ]


def call_ollama_polish(
    raw_text: str,
    *,
    base_url: str = "http://localhost:11434",
    model: str = "qwen2.5-coder:7b",
    timeout: float = 120.0,
    hint_type: str | None = None,
) -> list[dict] | None:
    """
    Call ollama to polish raw_text into structured entry dict(s).
    Returns list of dicts, or None if ollama is unavailable / parse fails.
    """
    try:
        import httpx
    except ImportError:
        return None

    messages = _build_messages(raw_text, hint_type)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": _SYSTEM_PROMPT}, *messages],
        "stream": False,
        "options": {"temperature": 0.1},
    }

    try:
        resp = httpx.post(
            f"{base_url}/api/chat",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
    except Exception:
        return None

    try:
        content = resp.json()["message"]["content"].strip()
    except Exception:
        return None

    return _parse_json_response(content)


def _parse_json_response(content: str) -> list[dict] | None:
    """Extract JSON from LLM response (may have markdown fences)."""
    # strip ```json ... ``` fences
    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
    content = re.sub(r"```\s*$", "", content, flags=re.MULTILINE).strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return None


# ── fallback (no ollama) ─────────────────────────────────────────

def auto_title(raw_text: str) -> str:
    """Generate a basic title from raw text (first sentence, ≤100 chars)."""
    first = raw_text.strip().splitlines()[0].strip()
    first = re.sub(r"[.!?]+$", "", first)
    if len(first) > 100:
        first = first[:97] + "…"
    return first


def fallback_polish(raw_text: str, entry_type: str) -> dict:
    """Minimal structure when ollama is unavailable."""
    from .models import BODY_SECTIONS
    sections = BODY_SECTIONS.get(entry_type, ["Note"])
    body_lines = [f"**{s}:** {raw_text}" if i == 0 else f"**{s}:** "
                  for i, s in enumerate(sections)]
    return {
        "type": entry_type,
        "title": auto_title(raw_text),
        "tags": [],
        "body": "\n\n".join(body_lines),
    }


# ── interactive confirm ───────────────────────────────────────────

def interactive_confirm(draft: dict, console=None) -> dict | None:
    """
    Show the polished draft to the user and ask to confirm/edit/abort.
    Returns the (possibly edited) dict, or None if aborted.
    Uses rich console if provided, else plain print.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax

    con = console or Console()

    preview = json.dumps({k: v for k, v in draft.items() if k != "body"},
                          ensure_ascii=False, indent=2)
    con.print(Panel(
        Syntax(preview, "json", theme="monokai", word_wrap=True),
        title=f"[bold cyan]vein log draft[/] — type: [yellow]{draft.get('type')}[/]",
        border_style="cyan",
    ))
    if draft.get("body"):
        con.print(Panel(draft["body"], title="body", border_style="dim"))

    while True:
        con.print("\n[bold]Accept?[/] \\[y/n/e(dit)] ", end="")
        choice = input().strip().lower()
        if choice in ("y", ""):
            return draft
        if choice == "n":
            con.print("[yellow]Aborted.[/]")
            return None
        if choice == "e":
            edited = _open_editor(draft)
            return edited
        con.print("  y = accept  n = abort  e = open $EDITOR")


def _open_editor(draft: dict) -> dict:
    """Open $EDITOR with the JSON draft, return parsed result."""
    import os
    import tempfile

    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w",
                                     encoding="utf-8", delete=False) as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
        tmp = f.name
    os.system(f'{editor} "{tmp}"')
    try:
        with open(tmp, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return draft
    finally:
        import pathlib
        pathlib.Path(tmp).unlink(missing_ok=True)
