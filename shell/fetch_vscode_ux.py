#!/usr/bin/env python3
"""
fetch_vscode_ux.py — Fetch VS Code source → extract GUI behavior specs → store in .vein/

Usage (run from vein project root):
  python3 shell/fetch_vscode_ux.py
  python3 shell/fetch_vscode_ux.py --area explorer,search
  python3 shell/fetch_vscode_ux.py --dry-run
  python3 shell/fetch_vscode_ux.py --no-ollama          # rule-based only
  python3 shell/fetch_vscode_ux.py --platform macos     # macOS-specific keybindings

What it does:
  1. Fetches specific VS Code .ts files from GitHub raw
  2. Extracts Action2 registrations + keybindings via regex (no ollama needed)
  3. If ollama is available: enriches each behavior with natural language desc
  4. Writes each behavior as a .vein/references/ entry (tagged project:lode, gui, vscode)

Output:
  .vein/references/<id>.md  per behavior
  vein recall "vscode rename"  → finds it instantly
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
from typing import Iterator

# ── Vein API ──────────────────────────────────────────────────────────────────
# Import from local src/ so this works without vein installed system-wide
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from vein.core.models import Entry
from vein.core.store import VeinStore

# ── Config ────────────────────────────────────────────────────────────────────

GITHUB_RAW = "https://raw.githubusercontent.com/microsoft/vscode/main"

# Source files per area — ordered by signal density (most behavior-rich first)
AREAS: dict[str, list[str]] = {
    "explorer": [
        "src/vs/workbench/contrib/files/browser/fileActions.ts",
        "src/vs/workbench/contrib/files/browser/fileActions.contribution.ts",
    ],
    "search": [
        "src/vs/workbench/contrib/search/browser/searchActionsNav.ts",
        "src/vs/workbench/contrib/search/browser/searchActionsRemoveReplace.ts",
        "src/vs/workbench/contrib/search/browser/searchActionsTopBar.ts",
        "src/vs/workbench/contrib/search/browser/searchActionsFind.ts",
    ],
    "tabs": [
        "src/vs/workbench/browser/parts/editor/editorTabsControl.ts",
        "src/vs/workbench/browser/parts/editor/editorActions.ts",
    ],
}

# Tags added to every entry
BASE_TAGS = ["project:lode", "gui", "vscode", "ux-spec"]

# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_raw(path: str, retries: int = 3) -> str | None:
    """Fetch a raw file from VS Code GitHub. Returns None on failure."""
    url = f"{GITHUB_RAW}/{path}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vein-fetch-script/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  [skip] 404: {path}")
                return None
            if e.code == 429 and attempt < retries - 1:
                wait = 2 ** attempt
                print(f"  [rate-limit] retrying in {wait}s…")
                time.sleep(wait)
                continue
            print(f"  [error] HTTP {e.code}: {path}")
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            print(f"  [error] {e}: {path}")
            return None
    return None

# ── Extraction ────────────────────────────────────────────────────────────────

# Matches registerAction2 blocks — captures the class body up to the next `registerAction2`
_ACTION2_BLOCK = re.compile(
    r"registerAction2\(class\s+(\w+)\s+extends\s+Action2\s*\{(.*?)(?=registerAction2|\Z)",
    re.DOTALL,
)

# Extract title string from nls.localize2('key', 'Human readable title')
_TITLE_RE = re.compile(r"nls\.localize2\s*\([^,]+,\s*['\"]([^'\"]+)['\"]")

# Extract keybinding primary key combos (with or without modifier)
_PRIMARY_KEY_RE = re.compile(r"primary:\s*((?:KeyMod\.\w+\s*\|\s*)*KeyCode\.[A-Za-z0-9]+)")

# macOS-specific keybinding
_MAC_KEY_RE = re.compile(r"mac:\s*\{[^}]*primary:\s*(KeyMod\.[A-Za-z|. |+]+KeyCode\.[A-Za-z0-9]+)")

# context condition
_WHEN_RE = re.compile(r"when:\s*(.{10,120}?)(?:,\s*\n|\})")


def _keymod_to_str(raw: str, platform: str = "all") -> str:
    """Convert KeyMod.CtrlCmd | KeyCode.Enter → Ctrl+Enter / Cmd+Enter."""
    raw = raw.strip()
    parts = [p.strip() for p in re.split(r"\s*\|\s*", raw)]
    keys = []
    for p in parts:
        if "CtrlCmd" in p:
            keys.append("Ctrl/Cmd")
        elif "WinCtrl" in p:
            keys.append("Ctrl" if platform == "macos" else "Win+Ctrl")
        elif "Shift" in p:
            keys.append("Shift")
        elif "Alt" in p:
            keys.append("Alt/Opt")
        elif "KeyCode." in p:
            code = p.split("KeyCode.")[-1].strip()
            # common mappings
            code = code.replace("KeyJ", "J").replace("KeyH", "H").replace("KeyL", "L")
            code = code.replace("UpArrow", "↑").replace("DownArrow", "↓")
            code = code.replace("LeftArrow", "←").replace("RightArrow", "→")
            code = code.replace("Enter", "Enter").replace("Escape", "Esc")
            keys.append(code)
    return "+".join(keys) if keys else raw


def extract_behaviors(source: str, area: str, platform: str = "all") -> list[dict]:
    """
    Rule-based extraction of Action2 registrations from VS Code TypeScript source.
    Returns list of behavior dicts: {title, keybinding, when, class_name, area}
    """
    behaviors = []

    for m in _ACTION2_BLOCK.finditer(source):
        class_name = m.group(1)
        block = m.group(2)

        # title
        tm = _TITLE_RE.search(block)
        if not tm:
            continue  # no human-readable title = skip
        title = tm.group(1).strip()
        if len(title) < 4:
            continue

        # keybinding
        keybinding = ""
        km = _PRIMARY_KEY_RE.search(block)
        if km:
            keybinding = _keymod_to_str(km.group(1), platform)
        # macOS override
        if platform == "macos":
            mm = _MAC_KEY_RE.search(block)
            if mm:
                keybinding = _keymod_to_str(mm.group(1), platform)

        # when condition (abbreviated)
        when = ""
        wm = _WHEN_RE.search(block)
        if wm:
            raw_when = wm.group(1).strip()
            # simplify: remove long ContextKeyExpr chains
            when = re.sub(r"ContextKeyExpr\.\w+\(", "", raw_when)
            when = re.sub(r"Constants\.\w+\.\w+", lambda x: x.group().split(".")[-1], when)
            when = when[:100]

        behaviors.append({
            "class_name": class_name,
            "title": title,
            "keybinding": keybinding,
            "when": when,
            "area": area,
        })

    return behaviors


# ── Ollama enrichment ─────────────────────────────────────────────────────────

def ollama_available(base_url: str) -> bool:
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", headers={"User-Agent": "vein/1.0"})
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def ollama_describe(behavior: dict, base_url: str, model: str) -> str:
    """Ask ollama to write a concise behavior spec for one VS Code action."""
    prompt = (
        f"You are writing a GUI behavior spec for developers building a VS Code-like app.\n"
        f"Describe this VS Code action as a 2-3 sentence user-facing behavior spec.\n"
        f"Be concrete: what triggers it, what the user sees, any edge cases.\n\n"
        f"Action: {behavior['title']}\n"
        f"Area: {behavior['area']}\n"
        f"Keyboard shortcut: {behavior['keybinding'] or 'none'}\n"
        f"Active when: {behavior['when'] or 'always'}\n\n"
        f"Output only the behavior spec, no preamble."
    )
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    try:
        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception as e:
        return ""


# ── Entry builder ─────────────────────────────────────────────────────────────

def behavior_to_entry(b: dict, description: str = "") -> Entry:
    """Convert an extracted behavior dict to a Vein Entry."""
    title = f"VSCode / {b['area']} / {b['title']}"

    lines = [f"## {b['title']}", ""]
    lines.append(f"**Area:** {b['area']}")
    if b["keybinding"]:
        lines.append(f"**Keybinding:** `{b['keybinding']}`")
    if b["when"]:
        lines.append(f"**Active when:** {b['when']}")
    lines.append(f"**Source class:** `{b['class_name']}`")
    lines.append("")

    if description:
        lines.append("## Summary")
        lines.append("")
        lines.append(description)
    else:
        lines.append("## Summary")
        lines.append("")
        lines.append(f"VS Code action: {b['title']}.")
        if b["keybinding"]:
            lines.append(f"Triggered via {b['keybinding']}.")

    body = "\n".join(lines)

    tags = BASE_TAGS + [b["area"], f"area:{b['area']}"]

    return Entry.make(
        type="reference",
        title=title,
        body=body,
        tags=tags,
        source="fetch_vscode_ux",
        source_url=f"https://github.com/microsoft/vscode/search?q={b['class_name']}",
        source_title=f"microsoft/vscode — {b['class_name']}",
        volatility="external-fact",  # VS Code APIs can change
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--area", default="all",
                   help="Comma-separated areas: explorer,search,tabs (default: all)")
    p.add_argument("--platform", default="all", choices=["all", "macos", "windows"],
                   help="Platform for keybinding display (default: all)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print behaviors, don't write to .vein/")
    p.add_argument("--no-ollama", action="store_true",
                   help="Skip ollama enrichment, use rule-based descriptions only")
    p.add_argument("--limit", type=int, default=0,
                   help="Max entries per area (0 = unlimited, useful for testing)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # resolve areas
    if args.area == "all":
        selected_areas = list(AREAS.keys())
    else:
        selected_areas = [a.strip() for a in args.area.split(",") if a.strip() in AREAS]
        unknown = [a for a in args.area.split(",") if a.strip() not in AREAS]
        if unknown:
            print(f"[warn] unknown areas: {unknown}. Valid: {list(AREAS.keys())}")

    if not selected_areas:
        print("[error] no valid areas selected.")
        sys.exit(1)

    # load vein store
    store = VeinStore.require()
    cfg = store.load_config()
    base_url = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    embed_model = cfg.get("model", {}).get("embed_model", "nomic-embed-text")
    digest_model = cfg.get("model", {}).get("digest_model", "llama3.2:3b")

    # ollama check
    use_ollama = not args.no_ollama and ollama_available(base_url)
    if use_ollama:
        print(f"✓ ollama available ({base_url}) — will enrich with {digest_model}")
    else:
        print(f"  ollama not available — rule-based descriptions only")

    total_written = 0
    total_skipped = 0

    for area in selected_areas:
        print(f"\n── {area.upper()} ──────────────────────────────")
        all_behaviors: list[dict] = []

        for src_path in AREAS[area]:
            print(f"  fetch: {src_path.split('/')[-1]} …", end=" ", flush=True)
            content = fetch_raw(src_path)
            if not content:
                print("✗ skipped")
                continue
            print(f"✓ ({len(content)//1024}KB)")

            behaviors = extract_behaviors(content, area, args.platform)
            print(f"  extracted {len(behaviors)} behaviors")
            all_behaviors.extend(behaviors)

        # deduplicate by title
        seen_titles: set[str] = set()
        unique: list[dict] = []
        for b in all_behaviors:
            key = b["title"].lower()
            if key not in seen_titles:
                seen_titles.add(key)
                unique.append(b)
        all_behaviors = unique

        if args.limit:
            all_behaviors = all_behaviors[: args.limit]

        print(f"  total unique: {len(all_behaviors)}")

        if args.dry_run:
            for b in all_behaviors:
                kb = f"  [{b['keybinding']}]" if b["keybinding"] else ""
                print(f"    • {b['title']}{kb}")
            continue

        # write entries
        for i, b in enumerate(all_behaviors):
            desc = ""
            if use_ollama:
                desc = ollama_describe(b, base_url, digest_model)

            entry = behavior_to_entry(b, desc)
            try:
                path = store.write_entry(entry, auto_index=True,
                                         base_url=base_url, embed_model=embed_model)
                total_written += 1
                kb = f" [{b['keybinding']}]" if b["keybinding"] else ""
                print(f"  [{i+1}/{len(all_behaviors)}] ✓ {b['title'][:60]}{kb}")
            except Exception as e:
                print(f"  [{i+1}/{len(all_behaviors)}] ✗ {b['title'][:60]} — {e}")
                total_skipped += 1

    print(f"\n{'─'*50}")
    if not args.dry_run:
        print(f"Written: {total_written}  Skipped: {total_skipped}")
        print(f"\nTry: vein recall \"vscode explorer rename\"")
        print(f"     vein recall \"vscode tab dirty\"")
        print(f"     vein recall \"vscode search f4\"")
    else:
        print("Dry run — nothing written.")


if __name__ == "__main__":
    main()
