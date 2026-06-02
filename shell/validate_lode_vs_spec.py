#!/usr/bin/env python3
"""
validate_lode_vs_spec.py — Compare GUI behavior specs in .vein/ against Lode source code.

Reads all reference entries tagged 'gui' from .vein/, greps Lode src/,
optionally asks ollama for verdict, outputs a gap report.

Usage (run from vein project root):
  python3 shell/validate_lode_vs_spec.py
  python3 shell/validate_lode_vs_spec.py --lode /path/to/lode
  python3 shell/validate_lode_vs_spec.py --tag npp          # only npp specs
  python3 shell/validate_lode_vs_spec.py --tag vscode
  python3 shell/validate_lode_vs_spec.py --no-ollama        # grep-only, fast
  python3 shell/validate_lode_vs_spec.py --save             # write to .vein/lore/

Output:
  Prints gap report to stdout.
  With --save: also writes .vein/lore/lode-gap-YYYY-MM-DD.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path
from typing import Literal

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from vein.core.models import Entry
from vein.core.store import VeinStore

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_LODE = Path("/Users/lion/Documents/lode")

# Lode source extensions to search
LODE_EXTS = {".ts", ".tsx", ".rs", ".js", ".jsx"}

# Min grep hits to consider "possibly implemented"
GREP_HIT_THRESHOLD = 2

# ── Grep helpers ──────────────────────────────────────────────────────────────

def _keywords(text: str) -> list[str]:
    """Extract searchable keywords from a spec title/body."""
    # strip "NPP / area / " or "VSCode / area / " prefixes
    text = re.sub(r"^(NPP|VSCode)\s*/\s*\w+\s*/\s*", "", text)
    # remove short stop words
    words = re.findall(r"[A-Za-z]{3,}", text)
    stop = {"the", "and", "for", "with", "from", "into", "that", "this",
            "when", "file", "edit", "view", "area", "npp", "vscode"}
    return [w.lower() for w in words if w.lower() not in stop][:5]


def _grep_lode(lode_root: Path, keywords: list[str]) -> list[str]:
    """
    Grep Lode source for keywords. Returns matching file paths (deduplicated).
    Uses ripgrep if available, falls back to Python glob+read.
    """
    if not keywords:
        return []

    src_dirs = [lode_root / "src", lode_root / "src-tauri" / "src"]
    existing = [d for d in src_dirs if d.exists()]
    if not existing:
        return []

    pattern = "|".join(re.escape(k) for k in keywords[:3])
    hits: set[str] = set()

    # try rg first
    try:
        result = subprocess.run(
            ["rg", "--case-insensitive", "--files-with-matches",
             "--type-add", "web:*.{ts,tsx,js,jsx}", "--type", "web",
             "--type", "rust", pattern] + [str(d) for d in existing],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            rel = str(Path(line).relative_to(lode_root))
            hits.add(rel)
        return list(hits)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # fallback: Python search
    for src_dir in existing:
        for f in src_dir.rglob("*"):
            if f.suffix not in LODE_EXTS:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore").lower()
                if sum(1 for k in keywords[:3] if k in content) >= 2:
                    hits.add(str(f.relative_to(lode_root)))
            except Exception:
                pass

    return list(hits)


def _grep_snippet(lode_root: Path, keywords: list[str], max_lines: int = 8) -> str:
    """Return a short code snippet showing the best match."""
    src_dirs = [lode_root / "src", lode_root / "src-tauri" / "src"]
    pattern = "|".join(re.escape(k) for k in keywords[:2])

    try:
        result = subprocess.run(
            ["rg", "--case-insensitive", "-n", "--max-count", "3",
             "--type-add", "web:*.{ts,tsx,js,jsx}", "--type", "web",
             "--type", "rust", pattern] + [str(d) for d in src_dirs if d.exists()],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stdout.splitlines()[:max_lines]
        return "\n".join(lines)
    except Exception:
        return ""


# ── Ollama verdict ────────────────────────────────────────────────────────────

_VERDICT_PROMPT = """\
You are a code reviewer checking if a desktop app (Lode) implements a specific GUI behavior.

Behavior spec:
{spec}

Lode is a macOS desktop app (Tauri 2 + React + TypeScript + Rust).
It has these modes: Viewer, Git Viewer, Folder Compare, File Compare, Binary Compare, Search.

Grep evidence from Lode source ({hits} files matched):
{snippet}

Based ONLY on the evidence above, classify:
- "yes"     — clearly implemented (strong evidence)
- "partial" — partially implemented or uncertain (some evidence)
- "no"      — no evidence found (likely missing)

Respond with JSON: {{"verdict": "yes|partial|no", "reason": "one sentence"}}
"""

Verdict = Literal["yes", "partial", "no", "unknown"]


def _ollama_verdict(spec_text: str, hits: list[str], snippet: str,
                    base_url: str, model: str) -> tuple[Verdict, str]:
    prompt = _VERDICT_PROMPT.format(
        spec=spec_text[:800],
        hits=len(hits),
        snippet=snippet[:600] or "(no code evidence)",
    )
    payload = json.dumps({
        "model": model, "prompt": prompt, "stream": False, "format": "json",
        "options": {"temperature": 0.1},
    }).encode()
    try:
        req = urllib.request.Request(
            f"{base_url}/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            raw = result.get("response", "{}").strip()
            parsed = json.loads(raw)
            verdict = parsed.get("verdict", "unknown")
            if verdict not in ("yes", "partial", "no"):
                verdict = "unknown"
            return verdict, parsed.get("reason", "")
    except Exception:
        return "unknown", ""


def _ollama_ok(base_url: str) -> bool:
    try:
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


# ── Report rendering ──────────────────────────────────────────────────────────

ICONS: dict[str, str] = {
    "yes":     "✅",
    "partial": "⚠️",
    "no":      "❌",
    "unknown": "❓",
}


def _render_report(results: list[dict], tag_filter: str) -> str:
    today = date.today().isoformat()
    lines = [
        f"# Lode vs {tag_filter.upper()} GUI Spec — Gap Report",
        f"\n**Generated:** {today}  ",
        f"**Specs checked:** {len(results)}  ",
    ]

    yes     = [r for r in results if r["verdict"] == "yes"]
    partial = [r for r in results if r["verdict"] == "partial"]
    no      = [r for r in results if r["verdict"] == "no"]
    unknown = [r for r in results if r["verdict"] == "unknown"]

    lines += [
        f"**✅ Implemented:** {len(yes)}  ",
        f"**⚠️  Partial:** {len(partial)}  ",
        f"**❌ Missing:** {len(no)}  ",
        f"**❓ Unknown:** {len(unknown)}  ",
        "",
    ]

    for label, group in [("❌ Missing", no), ("⚠️ Partial", partial),
                          ("✅ Implemented", yes), ("❓ Unknown", unknown)]:
        if not group:
            continue
        lines.append(f"\n## {label}\n")
        for r in group:
            lines.append(f"### {r['title']}")
            if r.get("reason"):
                lines.append(f"> {r['reason']}")
            if r.get("files"):
                lines.append(f"\nEvidence: {', '.join(r['files'][:3])}")
            lines.append("")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lode", default=str(DEFAULT_LODE),
                   help=f"Path to Lode repo (default: {DEFAULT_LODE})")
    p.add_argument("--tag", default="gui",
                   help="Filter specs by tag (default: gui; try: npp, vscode)")
    p.add_argument("--no-ollama", action="store_true",
                   help="Grep-only mode (fast, no AI verdict)")
    p.add_argument("--save", action="store_true",
                   help="Save report to .vein/lore/lode-gap-YYYY-MM-DD.md")
    p.add_argument("--limit", type=int, default=0,
                   help="Max specs to check (0 = all, useful for testing)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    lode_root = Path(args.lode)
    if not lode_root.exists():
        print(f"[error] Lode not found at {lode_root}")
        print("  Pass correct path with --lode /path/to/lode")
        sys.exit(1)

    store = VeinStore.require()
    cfg   = store.load_config()
    base_url     = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    digest_model = cfg.get("model", {}).get("digest_model", "llama3.2:3b")

    use_ollama = not args.no_ollama and _ollama_ok(base_url)
    print(f"Lode:   {lode_root}")
    print(f"ollama: {'✓ ' + digest_model if use_ollama else 'unavailable — grep-only'}")

    # load specs
    specs: list[Entry] = [
        e for e in store.iter_entries()
        if e.type == "reference" and args.tag in e.tags
    ]
    if not specs:
        print(f"\n[warn] No reference entries with tag '{args.tag}' found in .vein/")
        print(f"  Run: python3 shell/fetch_npp_ux.py   or   python3 shell/fetch_vscode_ux.py")
        sys.exit(0)

    if args.limit:
        specs = specs[:args.limit]

    print(f"\nChecking {len(specs)} specs (tag={args.tag}) against Lode source…\n")

    results: list[dict] = []

    for i, entry in enumerate(specs):
        title   = entry.title
        body    = entry.body
        kw      = _keywords(title + " " + body[:200])
        files   = _grep_lode(lode_root, kw)
        snippet = _grep_snippet(lode_root, kw) if files else ""

        if use_ollama:
            verdict, reason = _ollama_verdict(
                f"{title}\n\n{body[:500]}", files, snippet, base_url, digest_model
            )
        else:
            # grep-only heuristic
            if len(files) >= GREP_HIT_THRESHOLD:
                verdict, reason = "partial", f"{len(files)} file(s) matched"
            elif files:
                verdict, reason = "partial", f"{files[0]}"
            else:
                verdict, reason = "no", "no grep hits"

        icon = ICONS[verdict]
        short = title[:65]
        print(f"  [{i+1:3}/{len(specs)}] {icon}  {short}")
        if reason and verdict != "yes":
            print(f"           {reason}")

        results.append({
            "title":   title,
            "verdict": verdict,
            "reason":  reason,
            "files":   files,
        })

    # summary
    yes  = sum(1 for r in results if r["verdict"] == "yes")
    part = sum(1 for r in results if r["verdict"] == "partial")
    no   = sum(1 for r in results if r["verdict"] == "no")
    unk  = sum(1 for r in results if r["verdict"] == "unknown")

    print(f"\n{'─'*55}")
    print(f"✅ {yes}  ⚠️  {part}  ❌ {no}  ❓ {unk}  (total {len(results)})")

    report = _render_report(results, args.tag)

    if args.save:
        today = date.today().isoformat()
        fname = f"lode-gap-{today}.md"
        out_path = store.vein_dir / "lore" / fname
        out_path.write_text(report, encoding="utf-8")
        print(f"\nSaved: {out_path.relative_to(store.root)}")
        print(f"  vein recall \"lode gap {args.tag}\"")
    else:
        print("\n" + "─"*55)
        print(report)
        print("\nTip: re-run with --save to persist the report to .vein/lore/")


if __name__ == "__main__":
    main()
