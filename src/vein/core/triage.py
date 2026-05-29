"""triage.py — error log analysis: extract key terms + call AI for fix.

Used by `vein pipe` and `vein run`. Intentionally kept separate from
polish.py (which handles lore capture) so the call paths stay clean.
"""

from __future__ import annotations

import json
import re

# ── error term extraction ─────────────────────────────────────────

# Common error patterns to pull signal from noisy logs
_ERROR_PATTERNS = [
    # Rust: error[E0308]: mismatched types / error: ...
    re.compile(r"^error(?:\[[\w:]+\])?:\s*.{5,120}", re.IGNORECASE | re.MULTILINE),
    # Python: AttributeError / TypeError / ...
    re.compile(r"(?:AttributeError|TypeError|ValueError|KeyError|ImportError|RuntimeError|AssertionError):\s*.{3,100}"),
    # Generic: Error: ... / Exception: ... / Fatal: ...
    re.compile(r"(?:Exception|Fatal|FAILED|ERROR):\s*.{5,120}", re.IGNORECASE),
    # not found / undefined / cannot find
    re.compile(r"(?:undefined|not found|cannot find|no such file|not installed)[\w\s:\"'`./]{5,80}", re.IGNORECASE),
    # pytest FAILED
    re.compile(r"^FAILED\s+[\w/:.]+", re.MULTILINE),
    # cargo / make targets
    re.compile(r"(?:ld returned|linker.*error|undefined reference)", re.IGNORECASE),
    # note lines (Rust / compiler hints)
    re.compile(r"^note:\s*.{10,100}", re.MULTILINE),
    # ✗ markers
    re.compile(r"✗\s+.+"),
]

_NOISE = re.compile(
    r"^\s*(?:"
    r"Compiling|Finished|Running|Checking|Downloading|Updating|Resolving|"
    r"warning: unused|note: `#\[warn|Creating|Building|Installing|"
    r"\d+\s+warning|INFO|DEBUG"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


def extract_error_terms(log: str, max_chars: int = 600) -> str:
    """
    Distil a noisy error log into key signal lines.
    Returns a short string suitable for vein grep or AI prompt context.
    """
    lines = log.splitlines()

    # pass 1: grab lines with error signals
    signal_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _NOISE.match(stripped):
            continue
        for pat in _ERROR_PATTERNS:
            if pat.search(stripped):
                signal_lines.append(stripped)
                break

    if signal_lines:
        digest = "\n".join(signal_lines[:20])
    else:
        # fallback: last 20 non-empty lines
        non_empty = [l.strip() for l in lines if l.strip()]
        digest = "\n".join(non_empty[-20:])

    return digest[:max_chars]


# ── ollama triage call ────────────────────────────────────────────

_TRIAGE_SYSTEM = """\
You are a concise technical assistant helping a developer fix a command-line error.
Given: the command that failed, the error output, and any relevant context from the
project's lore archive.

Output a short, actionable fix. Format:
**Root cause:** one sentence
**Fix:** exact command(s) or code change needed
**Why this works:** one sentence (optional if obvious)

If the fix requires modifying a file, show only the changed lines.
Do NOT explain the error at length. Be terse. Max 10 lines.
"""


def call_ollama_triage(
    cmd: str,
    error_digest: str,
    lore_context: str = "",
    *,
    base_url: str = "http://localhost:11434",
    model: str = "qwen2.5-coder:7b",
    timeout: float = 120.0,
) -> str | None:
    """
    Call ollama to get a fix for a failed command.
    Returns markdown string, or None if ollama unavailable.
    """
    try:
        import httpx
    except ImportError:
        return None

    parts = [f"**Command:** `{cmd}`", f"\n**Error:**\n```\n{error_digest}\n```"]
    if lore_context:
        parts.append(f"\n**Related lore from project archive:**\n{lore_context}")

    user_msg = "\n".join(parts)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _TRIAGE_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        "stream": False,
        "options": {"temperature": 0.1},
    }

    try:
        resp = httpx.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception:
        return None
