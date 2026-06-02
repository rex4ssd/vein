#!/usr/bin/env python3
"""
validate_lode_vs_spec.py — Compare GUI behavior specs in .vein/ against Lode source.

Usage:
  python3 shell/validate_lode_vs_spec.py
  python3 shell/validate_lode_vs_spec.py --tag npp-ux
  python3 shell/validate_lode_vs_spec.py --tag vscode
  python3 shell/validate_lode_vs_spec.py --no-ollama   # grep-only
  python3 shell/validate_lode_vs_spec.py --save        # write to .vein/lore/
  python3 shell/validate_lode_vs_spec.py --debug       # show rg output
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

# ── defaults ──────────────────────────────────────────────────────────────────

DEFAULT_LODE  = Path("/Users/lion/Documents/lode")
SOURCE_SUBDIRS = ["src", "src-tauri/src"]   # relative to lode root
SOURCE_GLOBS  = "*.{ts,tsx,js,jsx,rs}"      # file extensions to search

Verdict = Literal["yes", "partial", "no", "unknown"]

# ── single rg wrapper ─────────────────────────────────────────────────────────

def _rg(
    lode_root: Path,
    pattern: str,
    *,
    files_only: bool = True,
    max_count: int = 3,
    debug: bool = False,
) -> list[str]:
    """
    Single rg implementation used everywhere.
    files_only=True  → returns relative file paths (for hit counting)
    files_only=False → returns matching lines with line numbers (for snippets)
    """
    lode_resolved = lode_root.resolve()
    src_dirs = [
        lode_root / sub
        for sub in SOURCE_SUBDIRS
        if (lode_root / sub).exists()
    ]
    if not src_dirs:
        return []

    cmd = ["rg", "-i", "--glob", SOURCE_GLOBS]
    if files_only:
        cmd += ["--files-with-matches"]
    else:
        cmd += ["-n", f"--max-count={max_count}"]
    cmd += [pattern] + [str(d) for d in src_dirs]

    if debug:
        print(f"    [rg] {' '.join(cmd[:8])}… {pattern!r}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        if debug and result.returncode > 1:
            print(f"    [rg] rc={result.returncode} stderr={result.stderr[:120]!r}")

        if result.returncode > 1:   # 0=matches found, 1=no matches, 2=error
            return []

        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]

        if files_only:
            # return paths relative to lode_root
            rel = []
            for line in lines:
                try:
                    rel.append(str(Path(line).resolve().relative_to(lode_resolved)))
                except ValueError:
                    rel.append(line)
            if debug:
                print(f"    [rg] {len(rel)} files")
            return rel
        else:
            if debug:
                print(f"    [rg] {len(lines)} lines")
            return lines

    except FileNotFoundError:
        print("  [warn] rg not found — install ripgrep")
        return []
    except subprocess.TimeoutExpired:
        print("  [warn] rg timed out")
        return []


# ── keyword extraction ────────────────────────────────────────────────────────

_STOP = {"the", "and", "for", "with", "from", "into", "that", "this",
         "when", "area", "npp", "vscode", "summary", "notepad", "plus"}


def _keywords(text: str) -> list[str]:
    """Extract searchable keywords from entry title + body."""
    # strip "NPP / area / " or "VSCode / area / " prefix
    text = re.sub(r"^(NPP|VSCode)\s*/\s*\w+\s*/\s*", "", text)
    words = re.findall(r"[A-Za-z]{3,}", text)
    seen: set[str] = set()
    result: list[str] = []
    for w in words:
        w = w.lower()
        if w not in _STOP and w not in seen:
            seen.add(w)
            result.append(w)
    return result[:6]


# ── grep-based search ─────────────────────────────────────────────────────────

def find_files(lode_root: Path, keywords: list[str], debug: bool = False) -> list[str]:
    """Return files matching at least 2 of the top keywords (intersection)."""
    if not keywords:
        return []
    kw = keywords[:3]
    if len(kw) >= 2:
        # intersect: files matching kw[0] AND kw[1]
        set0 = set(_rg(lode_root, re.escape(kw[0]), files_only=True, debug=debug))
        set1 = set(_rg(lode_root, re.escape(kw[1]), files_only=True, debug=debug))
        hits = set0 & set1
        if not hits:                       # fallback: any single keyword
            hits = set0
    else:
        hits = set(_rg(lode_root, re.escape(kw[0]), files_only=True, debug=debug))
    return list(hits)


def get_snippet(lode_root: Path, keywords: list[str], debug: bool = False) -> str:
    """Return actual matching code lines for the top 2 keywords."""
    if not keywords:
        return ""
    pattern = "|".join(re.escape(k) for k in keywords[:2])
    lines = _rg(lode_root, pattern, files_only=False, max_count=3, debug=debug)
    return "\n".join(lines[:12])


# ── ollama ────────────────────────────────────────────────────────────────────

_VERDICT_PROMPT = """\
You are a code reviewer checking if a desktop app (Lode) implements a GUI behavior.

Lode is a macOS desktop app (Tauri 2 + React + TypeScript + Rust) with modes:
Viewer, Git Viewer, Folder Compare, File Compare, Binary Compare, Search.

Behavior spec:
{spec}

Grep evidence ({hits} files matched keywords):
{snippet}

Classify strictly based on the evidence:
  "yes"     — clearly implemented
  "partial" — some evidence but incomplete or uncertain
  "no"      — no relevant evidence found

Respond with JSON only: {{"verdict": "yes|partial|no", "reason": "one sentence"}}
"""


def _ollama_ok(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(
            urllib.request.Request(f"{base_url}/api/tags"), timeout=3
        ):
            return True
    except Exception:
        return False


def ollama_verdict(
    spec_text: str, files: list[str], snippet: str,
    base_url: str, model: str,
) -> tuple[Verdict, str]:
    prompt = _VERDICT_PROMPT.format(
        spec=spec_text[:800],
        hits=len(files),
        snippet=snippet[:800] if snippet else "(no matching code found)",
    )
    payload = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "format": "json", "options": {"temperature": 0.1},
    }).encode()
    try:
        req = urllib.request.Request(
            f"{base_url}/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=40) as resp:
            raw = json.loads(resp.read()).get("response", "{}").strip()
            parsed = json.loads(raw)
            v = parsed.get("verdict", "unknown")
            if v not in ("yes", "partial", "no"):
                v = "unknown"
            return v, parsed.get("reason", "")
    except Exception as e:
        return "unknown", str(e)[:80]


# ── report ────────────────────────────────────────────────────────────────────

ICONS: dict[str, str] = {"yes": "✅", "partial": "⚠️", "no": "❌", "unknown": "❓"}


def render_report(results: list[dict], tag: str) -> str:
    today = date.today().isoformat()
    counts = {v: sum(1 for r in results if r["verdict"] == v)
              for v in ("yes", "partial", "no", "unknown")}
    lines = [
        f"# Lode vs {tag.upper()} GUI Spec — Gap Report",
        f"\n**Generated:** {today}  ",
        f"**Specs checked:** {len(results)}  ",
        f"**✅ Implemented:** {counts['yes']}  ",
        f"**⚠️  Partial:** {counts['partial']}  ",
        f"**❌ Missing:** {counts['no']}  ",
        f"**❓ Unknown:** {counts['unknown']}  ",
        "",
    ]
    for label, verdict in [("❌ Missing", "no"), ("⚠️ Partial", "partial"),
                            ("✅ Implemented", "yes"), ("❓ Unknown", "unknown")]:
        group = [r for r in results if r["verdict"] == verdict]
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


# ── main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lode", default=str(DEFAULT_LODE))
    p.add_argument("--tag", default="gui",
                   help="Spec tag filter (default: gui; try: npp-ux, vscode)")
    p.add_argument("--no-ollama", action="store_true")
    p.add_argument("--save", action="store_true",
                   help="Write report to .vein/lore/lode-gap-YYYY-MM-DD.md")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--debug", action="store_true",
                   help="Print rg commands and output for debugging")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    lode_root = Path(args.lode)
    if not lode_root.exists():
        print(f"[error] Lode not found: {lode_root}")
        sys.exit(1)

    store = VeinStore.require()
    cfg = store.load_config()
    base_url     = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    digest_model = cfg.get("model", {}).get("digest_model", "llama3.2:3b")

    use_ollama = not args.no_ollama and _ollama_ok(base_url)
    print(f"Lode:   {lode_root}")
    print(f"ollama: {'✓ ' + digest_model if use_ollama else 'unavailable — grep-only'}")

    specs = [e for e in store.iter_entries()
             if e.type == "reference" and args.tag in e.tags]
    if not specs:
        print(f"\n[warn] No reference entries with tag '{args.tag}' in .vein/")
        print("  Run: python3 shell/fetch_npp_ux.py   or   python3 shell/fetch_vscode_ux.py")
        sys.exit(0)

    if args.limit:
        specs = specs[:args.limit]

    print(f"\nChecking {len(specs)} specs (tag={args.tag})…\n")

    results: list[dict] = []
    for i, entry in enumerate(specs):
        kw      = _keywords(entry.title + " " + entry.body[:300])
        files   = find_files(lode_root, kw, debug=args.debug)
        snippet = get_snippet(lode_root, kw, debug=args.debug)

        if args.debug:
            print(f"  keywords: {kw}")
            print(f"  files: {len(files)}  snippet_lines: {len(snippet.splitlines())}")

        if use_ollama:
            verdict, reason = ollama_verdict(
                f"{entry.title}\n\n{entry.body[:500]}",
                files, snippet, base_url, digest_model,
            )
        else:
            if len(files) >= 5:
                verdict, reason = "partial", f"{len(files)} file(s) matched"
            elif files:
                verdict, reason = "partial", files[0]
            else:
                verdict, reason = "no", "no grep hits"

        icon = ICONS[verdict]
        print(f"  [{i+1:3}/{len(specs)}] {icon}  {entry.title[:65]}")
        if reason and verdict != "yes":
            print(f"           {reason}")

        results.append({"title": entry.title, "verdict": verdict,
                        "reason": reason, "files": files})

    counts = {v: sum(1 for r in results if r["verdict"] == v)
              for v in ("yes", "partial", "no", "unknown")}
    print(f"\n{'─'*55}")
    print(f"✅ {counts['yes']}  ⚠️  {counts['partial']}  "
          f"❌ {counts['no']}  ❓ {counts['unknown']}  (total {len(results)})")

    report = render_report(results, args.tag)

    if args.save:
        out = store.vein_dir / "lore" / f"lode-gap-{date.today().isoformat()}.md"
        out.write_text(report, encoding="utf-8")
        print(f"\nSaved: {out.relative_to(store.root)}")
    else:
        print("\n" + "─"*55)
        print(report)
        print("\nTip: re-run with --save to persist to .vein/lore/")


if __name__ == "__main__":
    main()
