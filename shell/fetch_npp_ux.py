#!/usr/bin/env python3
"""
fetch_npp_ux.py — Fetch Notepad++ GUI behavior specs → .vein/references/

Sources (in priority order):
  1. npp-user-manual.org — official user manual HTML pages
  2. GitHub raw — PowerEditor C++ shortcut/menu source (regex extraction)

Usage (run from vein project root):
  python3 shell/fetch_npp_ux.py
  python3 shell/fetch_npp_ux.py --area editing,search,tabs
  python3 shell/fetch_npp_ux.py --dry-run
  python3 shell/fetch_npp_ux.py --force       # overwrite existing npp entries
  python3 shell/fetch_npp_ux.py --no-ollama   # rule-based only

After running:
  vein recall "npp tab"
  vein recall "npp find replace"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from vein.core.models import Entry
from vein.core.store import VeinStore

# ── Config ────────────────────────────────────────────────────────────────────

SOURCE_TAG = "source:npp-userguide"
BASE_TAGS  = ["project:lode", "gui", "npp", "ux-spec", SOURCE_TAG]

# User manual sections to fetch
MANUAL_AREAS: dict[str, str] = {
    "editing":    "https://npp-user-manual.org/docs/editing/",
    "search":     "https://npp-user-manual.org/docs/searching/",
    "tabs":       "https://npp-user-manual.org/docs/other-resources/",
    "session":    "https://npp-user-manual.org/docs/session/",
    "files":      "https://npp-user-manual.org/docs/files/",
    "preferences":"https://npp-user-manual.org/docs/preferences/",
}

# GitHub raw fallback — keyboard shortcut / command source files
GITHUB_RAW = "https://raw.githubusercontent.com/notepad-plus-plus/notepad-plus-plus/master"
GITHUB_SOURCES: dict[str, list[str]] = {
    "editing": [
        "PowerEditor/src/ScintillaComponent/ScintillaEditView.cpp",
    ],
    "search": [
        "PowerEditor/src/FindReplaceDlg.cpp",
    ],
    "tabs": [
        "PowerEditor/src/tabBar.cpp",
    ],
}

# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _fetch(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vein-fetch/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError:
                    return raw.decode("latin-1")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
        except Exception:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                return None
    return None


def _strip_html(html: str) -> str:
    """Very basic HTML → text. Keeps structure for ollama."""
    # remove scripts, styles, nav
    html = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.I)
    # headings → markdown-style
    html = re.sub(r"<h([1-4])[^>]*>(.*?)</h\1>", lambda m: "\n" + "#" * int(m.group(1)) + " " + m.group(2) + "\n", html, flags=re.I | re.DOTALL)
    # list items
    html = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", html, flags=re.I | re.DOTALL)
    # paragraphs and divs → newlines
    html = re.sub(r"<(p|div|br)[^>]*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</(p|div)>", "\n", html, flags=re.I)
    # strip remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # decode common entities
    for ent, ch in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&nbsp;", " "), ("&#39;", "'"), ("&quot;", '"')]:
        html = html.replace(ent, ch)
    # collapse whitespace
    html = re.sub(r"\n{3,}", "\n\n", html)
    html = re.sub(r"[ \t]+", " ", html)
    return html.strip()


# ── Rule-based extraction from C++ ───────────────────────────────────────────

# Win32 WM_COMMAND / menu ID patterns
_CMD_RE = re.compile(
    r'case\s+(IDM_\w+|ID_\w+)[^:]*:\s*\n'
    r'(?:.*\n){0,5}?.*?(?:SendMsg|SendMessage|doCommand)\s*\('
    , re.MULTILINE
)

# Keyboard shortcut table entries: {VK_XXX, Ctrl, shift, alt, "description"}
_SC_RE = re.compile(
    r'\{VK_([A-Z0-9]+)\s*,\s*(TRUE|FALSE)\s*,\s*(TRUE|FALSE)\s*,\s*(TRUE|FALSE)'
    r'[^}]*"([^"]{5,80})"'
)


def _extract_cpp_behaviors(source: str, area: str) -> list[dict]:
    behaviors = []

    # shortcut table entries
    for m in _SC_RE.finditer(source):
        key, ctrl, shift, alt, desc = m.groups()
        parts = []
        if ctrl  == "TRUE": parts.append("Ctrl")
        if shift == "TRUE": parts.append("Shift")
        if alt   == "TRUE": parts.append("Alt")
        parts.append(key.replace("_", "").title() if len(key) > 1 else key)
        kb = "+".join(parts)
        behaviors.append({"title": desc.strip(), "keybinding": kb, "area": area, "source": "shortcut-table"})

    return behaviors[:30]  # cap per file


# ── Ollama helpers ────────────────────────────────────────────────────────────

def _ollama_ok(base_url: str) -> bool:
    try:
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


_EXTRACT_PROMPT = """\
You are writing GUI behavior specs for developers building a desktop text editor.
Read this Notepad++ documentation section and extract discrete user-visible behaviors.

For each behavior output a JSON object:
{{"title": "short action name (<60 chars)", "keybinding": "Ctrl+F or empty", "body": "2-3 sentence spec describing trigger, result, edge cases"}}

Output a JSON array of 5-15 behaviors. Focus on: keyboard shortcuts, mouse interactions, dialog behaviors, edit operations.
Section ({area}):
{content}
"""


def _ollama_extract(text: str, area: str, base_url: str, model: str) -> list[dict]:
    prompt = _EXTRACT_PROMPT.format(area=area, content=text[:6000])
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False,
                          "format": "json"}).encode()
    try:
        req = urllib.request.Request(
            f"{base_url}/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            raw = result.get("response", "").strip()
            # strip ```json fences
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"): raw = raw[4:]
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for k in ("behaviors", "entries", "items", "results"):
                    if isinstance(parsed.get(k), list):
                        parsed = parsed[k]; break
                else:
                    return []
            if not isinstance(parsed, list):
                return []
            return [b for b in parsed if isinstance(b, dict) and b.get("title")][:15]
    except Exception:
        return []


# ── Entry builder ─────────────────────────────────────────────────────────────

def _make_entry(b: dict, area: str) -> Entry:
    title = f"NPP / {area} / {b['title']}"
    kb    = b.get("keybinding", "")
    body_lines = [f"## {b['title']}", ""]
    body_lines.append(f"**Area:** {area}")
    if kb:
        body_lines.append(f"**Keybinding:** `{kb}`")
    body_lines += ["", "## Summary", "", b.get("body", b["title"] + ".")]
    return Entry.make(
        type="reference",
        title=title,
        body="\n".join(body_lines),
        tags=BASE_TAGS + [area, f"area:{area}"],
        source="fetch_npp_ux",
        source_url="https://npp-user-manual.org/",
        source_title="Notepad++ User Manual",
        volatility="external-fact",
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--area", default="all",
                   help=f"Comma-separated: {','.join(MANUAL_AREAS)} (default: all)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print behaviors, don't write to .vein/")
    p.add_argument("--force", action="store_true",
                   help="Delete existing npp entries and re-fetch")
    p.add_argument("--no-ollama", action="store_true",
                   help="Skip ollama, use rule-based C++ extraction only")
    p.add_argument("--limit", type=int, default=0,
                   help="Max entries per area (0 = unlimited)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # resolve areas
    if args.area == "all":
        selected = list(MANUAL_AREAS.keys())
    else:
        selected = [a.strip() for a in args.area.split(",") if a.strip() in MANUAL_AREAS]
        bad = [a for a in args.area.split(",") if a.strip() not in MANUAL_AREAS]
        if bad:
            print(f"[warn] unknown areas: {bad}. Valid: {list(MANUAL_AREAS.keys())}")

    store = VeinStore.require()
    cfg   = store.load_config()
    base_url    = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    embed_model = cfg.get("model", {}).get("embed_model", "nomic-embed-text")
    digest_model= cfg.get("model", {}).get("digest_model", "llama3.2:3b")

    # dedup / force
    existing = [e for e in store.iter_entries() if SOURCE_TAG in e.tags]
    if existing and not args.force and not args.dry_run:
        print(f"Already fetched: {len(existing)} NPP entries in .vein/")
        print("  Re-run with --force to overwrite, or --dry-run to preview.")
        sys.exit(0)

    if existing and args.force and not args.dry_run:
        deleted = 0
        for e in existing:
            if e._path and e._path.exists():
                e._path.unlink()
                deleted += 1
        print(f"--force: removed {deleted} existing NPP entries")

    use_ollama = not args.no_ollama and _ollama_ok(base_url)
    print(f"ollama: {'✓ ' + digest_model if use_ollama else 'unavailable — C++ rule-based fallback'}")

    total_written = 0

    for area in selected:
        print(f"\n── {area.upper()} ──────────────────────────────")

        behaviors: list[dict] = []

        # ── try user manual HTML ───────────────────────────────────────────
        url = MANUAL_AREAS[area]
        print(f"  fetch {url} …", end=" ", flush=True)
        html = _fetch(url)

        if html:
            text = _strip_html(html)
            print(f"✓ ({len(text)//1024}KB text)")

            if use_ollama:
                extracted = _ollama_extract(text, area, base_url, digest_model)
                print(f"  ollama extracted {len(extracted)} behaviors")
                behaviors.extend(extracted)
            else:
                # rule-based: look for keyboard shortcut patterns in text
                for m in re.finditer(
                    r'`?(Ctrl|Alt|Shift)[+\-][A-Za-z0-9+\-]+`?\s*[:\-–]\s*(.{10,100})', text
                ):
                    kb, desc = m.group(0).split(":", 1)[0].strip(), m.group(2).strip()
                    behaviors.append({"title": desc[:60], "keybinding": kb, "area": area, "body": desc})
                print(f"  rule-based: {len(behaviors)} keyboard shortcut patterns")
        else:
            print("✗ (manual unavailable)")

        # ── fallback: GitHub C++ source ────────────────────────────────────
        if not behaviors and area in GITHUB_SOURCES:
            for src_path in GITHUB_SOURCES[area]:
                raw_url = f"{GITHUB_RAW}/{src_path}"
                print(f"  fallback: {src_path.split('/')[-1]} …", end=" ", flush=True)
                content = _fetch(raw_url)
                if content:
                    print(f"✓ ({len(content)//1024}KB)")
                    cpp_behaviors = _extract_cpp_behaviors(content, area)
                    print(f"  extracted {len(cpp_behaviors)} shortcut entries")
                    behaviors.extend(cpp_behaviors)
                else:
                    print("✗")

        # dedup by title
        seen: set[str] = set()
        unique: list[dict] = []
        for b in behaviors:
            key = b["title"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(b)
        behaviors = unique

        if args.limit:
            behaviors = behaviors[:args.limit]

        if not behaviors:
            print("  nothing extracted")
            continue

        print(f"  total unique: {len(behaviors)}")

        if args.dry_run:
            for b in behaviors:
                kb = f"  [{b.get('keybinding','')}]" if b.get("keybinding") else ""
                print(f"    • {b['title'][:70]}{kb}")
            continue

        # write
        for i, b in enumerate(behaviors):
            b.setdefault("area", area)
            entry = _make_entry(b, area)
            try:
                store.write_entry(entry, auto_index=True,
                                  base_url=base_url, embed_model=embed_model)
                total_written += 1
                kb = f" [{b.get('keybinding','')}]" if b.get("keybinding") else ""
                print(f"  [{i+1}/{len(behaviors)}] ✓ {b['title'][:65]}{kb}")
            except Exception as exc:
                print(f"  [{i+1}/{len(behaviors)}] ✗ {b['title'][:65]} — {exc}")

    print(f"\n{'─'*50}")
    if not args.dry_run:
        print(f"Written: {total_written} NPP behavior entries")
        print("\nTry:")
        print("  vein recall \"npp find replace\"")
        print("  vein recall \"npp column edit\"")
        print("  vein recall \"npp tab\"")
    else:
        print("Dry run — nothing written.")


if __name__ == "__main__":
    main()
