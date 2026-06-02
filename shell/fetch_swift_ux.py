#!/usr/bin/env python3
"""
fetch_swift_ux.py — Fetch Swift macOS app GUI behavior specs → .vein/references/

Extracts from GitHub source:
  NSMenuItem + keyEquivalent    keyboard shortcuts
  @IBAction / @objc func        user-triggered actions
  NSStatusItem                  menu bar item patterns
  SwiftUI .keyboardShortcut     SwiftUI shortcuts
  NSMenu addItem                menu structure

Usage (run from vein project root):
  python3 shell/fetch_swift_ux.py
  python3 shell/fetch_swift_ux.py --app iina,stats
  python3 shell/fetch_swift_ux.py --dry-run
  python3 shell/fetch_swift_ux.py --force

After running:
  vein recall "swift menu bar"
  vein recall "iina keyboard"
  python3 shell/validate_lode_vs_spec.py --tag swift-macos
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

GITHUB_RAW  = "https://raw.githubusercontent.com"
SOURCE_TAG  = "source:swift-ux"
BASE_TAGS   = ["project:lode", "gui", "swift-macos", "ux-spec", SOURCE_TAG]

# Apps and their key Swift source files
APPS: dict[str, dict] = {
    "iina": {
        "repo": "iina/iina",
        "branch": "develop",
        "files": [
            "iina/AppDelegate.swift",
            "iina/MainWindowController.swift",
            "iina/KeyBindingManager.swift",
            "iina/PrefKeyBindingViewController.swift",
        ],
        "desc": "macOS media player — keyboard shortcuts, playback controls, window management",
    },
    "stats": {
        "repo": "exelban/stats",
        "branch": "master",
        "files": [
            "Stats/AppDelegate.swift",
            "Stats/PopupWindow.swift",
            "Stats/SettingsWindow.swift",
        ],
        "desc": "macOS menu bar system monitor — NSStatusItem, popover, settings",
    },
    "monitorcontrol": {
        "repo": "MonitorControl/MonitorControl",
        "branch": "main",
        "files": [
            "MonitorControl/AppDelegate.swift",
            "MonitorControl/View Controllers/MainPreferencesViewController.swift",
        ],
        "desc": "macOS external display brightness/volume control — menu bar, slider",
    },
    "utm": {
        "repo": "utmapp/UTM",
        "branch": "main",
        "files": [
            "Platform/macOS/AppDelegate.swift",
            "Platform/macOS/VMData.swift",
        ],
        "desc": "macOS VM app — file open, window management, toolbar",
    },
}

# ── HTTP ──────────────────────────────────────────────────────────────────────

def _fetch(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vein-fetch/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt); continue
            return None
        except Exception:
            if attempt < retries - 1: time.sleep(1)
    return None

# ── Regex extractors ──────────────────────────────────────────────────────────

# NSMenuItem(title: "...", action: ..., keyEquivalent: "x")
_NS_MENU_ITEM = re.compile(
    r'NSMenuItem\s*\(\s*title:\s*"([^"]{3,80})"[^)]*keyEquivalent:\s*"([^"]*)"',
    re.DOTALL,
)

# NSMenuItem(title: "...") without shortcut
_NS_MENU_ITEM_NO_KB = re.compile(
    r'NSMenuItem\s*\(\s*title:\s*"([^"]{4,80})"',
)

# keyEquivalentModifierMask near a variable
_KB_MODIFIER = re.compile(
    r'(\w+)\.keyEquivalentModifierMask\s*=\s*\[([^\]]+)\]'
)

# @IBAction func name(
_IBACTION = re.compile(
    r'@IBAction\s+(?:@objc\s+)?func\s+(\w+)\s*\(',
)

# @objc func name( — for selector-based actions
_OBJC_FUNC = re.compile(
    r'@objc\s+func\s+(\w+)\s*\(\s*(?:_\s+\w+\s*:\s*\w+)?\s*\)',
)

# SwiftUI .keyboardShortcut("x", modifiers: .command)
_SWIFTUI_KB = re.compile(
    r'\.keyboardShortcut\s*\(\s*"([^"]+)"\s*(?:,\s*modifiers:\s*([^)]+))?\)',
)

# NSStatusItem creation
_STATUS_ITEM = re.compile(
    r'NSStatusBar\.system\.statusItem\s*\(|statusItem\s*=\s*NSStatusBar',
)

# menu.addItem / insertItem
_MENU_ADD = re.compile(
    r'(?:addItem|insertItem)\s*\(\s*NSMenuItem\s*\(\s*title:\s*"([^"]{4,80})"',
)


def _modifier_str(raw: str) -> str:
    """Convert [.command, .shift] → Cmd+Shift"""
    parts = []
    if ".command"  in raw: parts.append("Cmd")
    if ".shift"    in raw: parts.append("Shift")
    if ".option"   in raw: parts.append("Opt")
    if ".control"  in raw: parts.append("Ctrl")
    return "+".join(parts) if parts else raw.strip()[:30]


def extract_behaviors(source: str, app: str) -> list[dict]:
    behaviors: list[dict] = []
    seen: set[str] = set()

    def _add(title: str, kb: str = "", area: str = ""):
        key = title.lower()[:50]
        if key in seen or len(title) < 5:
            return
        seen.add(key)
        behaviors.append({"title": title, "keybinding": kb, "area": area or app})

    # NSMenuItem with keyboard shortcut
    for m in _NS_MENU_ITEM.finditer(source):
        title, kb = m.group(1).strip(), m.group(2).strip()
        if kb:
            _add(title, f"Cmd+{kb.upper()}" if kb else "", "menu")
        else:
            _add(title, "", "menu")

    # SwiftUI .keyboardShortcut
    for m in _SWIFTUI_KB.finditer(source):
        key = m.group(1)
        mods = _modifier_str(m.group(2) or ".command")
        _add(f"SwiftUI action: {key}", f"{mods}+{key.upper()}", "swiftui")

    # menu.addItem(NSMenuItem(title: ...))
    for m in _MENU_ADD.finditer(source):
        _add(m.group(1).strip(), "", "menu")

    # @IBAction
    for m in _IBACTION.finditer(source):
        name = m.group(1)
        # humanize camelCase → words
        human = re.sub(r"([A-Z])", r" \1", name).strip().lower()
        if len(human) > 3:
            _add(f"Action: {human}", "", "ibaction")

    # @objc func (only those that look like UI handlers)
    for m in _OBJC_FUNC.finditer(source):
        name = m.group(1)
        if any(kw in name.lower() for kw in
               ("click", "press", "toggle", "open", "close", "show", "hide",
                "menu", "window", "panel", "settings", "quit", "about")):
            human = re.sub(r"([A-Z])", r" \1", name).strip().lower()
            _add(f"Handler: {human}", "", "objc")

    # NSStatusItem
    if _STATUS_ITEM.search(source):
        _add("NSStatusItem — menu bar icon", "", "menubar")

    return behaviors[:40]  # cap per file

# ── Ollama ────────────────────────────────────────────────────────────────────

def _ollama_ok(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(
            urllib.request.Request(f"{base_url}/api/tags"), timeout=3
        ): return True
    except Exception:
        return False


_ENRICH_PROMPT = """\
You are writing a GUI behavior spec for macOS desktop app developers.
Given this Swift macOS app action, write a 2-sentence spec:
what triggers it, what the user sees, any important edge cases.

App: {app} ({desc})
Action: {title}
Keybinding: {kb}

Output only the spec text, no preamble.
"""


def _enrich(b: dict, app_info: dict, base_url: str, model: str) -> str:
    prompt = _ENRICH_PROMPT.format(
        app=app_info["repo"],
        desc=app_info["desc"],
        title=b["title"],
        kb=b.get("keybinding") or "none",
    )
    payload = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1},
    }).encode()
    try:
        req = urllib.request.Request(
            f"{base_url}/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read()).get("response", "").strip()
    except Exception:
        return ""

# ── Entry builder ─────────────────────────────────────────────────────────────

def _make_entry(b: dict, app: str, desc: str) -> Entry:
    title  = f"Swift/{app} / {b['title']}"
    lines  = [f"## {b['title']}", "",
              f"**App:** {app}  —  {desc}",
              f"**Area:** {b.get('area', app)}"]
    if b.get("keybinding"):
        lines.append(f"**Keybinding:** `{b['keybinding']}`")
    lines += ["", "## Summary", "", b.get("body") or b["title"] + "."]
    return Entry.make(
        type="reference",
        title=title,
        body="\n".join(lines),
        tags=BASE_TAGS + [app, f"app:{app}"],
        source="fetch_swift_ux",
        source_url=f"https://github.com/{APPS[app]['repo']}",
        source_title=APPS[app]["repo"],
        volatility="external-fact",
    )

# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--app", default="all",
                   help=f"Comma-separated: {','.join(APPS)} (default: all)")
    p.add_argument("--dry-run",  action="store_true")
    p.add_argument("--force",    action="store_true",
                   help="Overwrite existing entries")
    p.add_argument("--no-ollama", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args()


def main() -> None:
    args = parse_args()

    selected = list(APPS.keys()) if args.app == "all" else \
               [a.strip() for a in args.app.split(",") if a.strip() in APPS]
    if not selected:
        print(f"[error] unknown app(s). Valid: {list(APPS.keys())}"); sys.exit(1)

    store = VeinStore.require()
    cfg   = store.load_config()
    base_url    = cfg.get("model", {}).get("base_url", "http://localhost:11434")
    embed_model = cfg.get("model", {}).get("embed_model", "nomic-embed-text")
    digest_model= cfg.get("model", {}).get("digest_model", "llama3.2:3b")

    # dedup
    existing = [e for e in store.iter_entries() if SOURCE_TAG in e.tags]
    if existing and not args.force and not args.dry_run:
        print(f"Already fetched: {len(existing)} Swift UX entries.")
        print("  Use --force to overwrite.")
        sys.exit(0)
    if existing and args.force and not args.dry_run:
        for e in existing:
            if e._path and e._path.exists(): e._path.unlink()
        print(f"--force: removed {len(existing)} existing entries")

    use_ollama = not args.no_ollama and _ollama_ok(base_url)
    print(f"ollama: {'✓ ' + digest_model if use_ollama else 'off — rule-based only'}\n")

    total_written = 0

    for app in selected:
        info = APPS[app]
        print(f"── {app.upper()} ({info['repo']}) ──────────────────────")

        all_behaviors: list[dict] = []

        for rel_path in info["files"]:
            url = f"{GITHUB_RAW}/{info['repo']}/{info['branch']}/{rel_path}"
            fname = rel_path.split("/")[-1]
            print(f"  fetch {fname} …", end=" ", flush=True)
            src = _fetch(url)
            if not src:
                print("✗"); continue
            print(f"✓ ({len(src)//1024}KB)")
            behaviors = extract_behaviors(src, app)
            print(f"  extracted {len(behaviors)} behaviors")
            all_behaviors.extend(behaviors)

        # deduplicate by title
        seen: set[str] = set()
        unique = []
        for b in all_behaviors:
            k = b["title"].lower()
            if k not in seen:
                seen.add(k); unique.append(b)
        all_behaviors = unique

        if args.limit:
            all_behaviors = all_behaviors[:args.limit]

        print(f"  unique total: {len(all_behaviors)}")

        if args.dry_run:
            for b in all_behaviors:
                kb = f"  [{b['keybinding']}]" if b.get("keybinding") else ""
                print(f"    • {b['title'][:70]}{kb}")
            continue

        for i, b in enumerate(all_behaviors):
            if use_ollama:
                b["body"] = _enrich(b, info, base_url, digest_model)
            entry = _make_entry(b, app, info["desc"])
            try:
                store.write_entry(entry, auto_index=True,
                                  base_url=base_url, embed_model=embed_model)
                total_written += 1
                kb = f" [{b['keybinding']}]" if b.get("keybinding") else ""
                print(f"  [{i+1:3}/{len(all_behaviors)}] ✓ {b['title'][:65]}{kb}")
            except Exception as exc:
                print(f"  [{i+1:3}/{len(all_behaviors)}] ✗ {b['title'][:60]} — {exc}")

    print(f"\n{'─'*55}")
    if not args.dry_run:
        print(f"Written: {total_written} Swift UX behavior entries")
        print("\nNext:")
        print("  vein recall \"swift menu bar\"")
        print("  vein recall \"iina keyboard\"")
        print("  python3 shell/validate_lode_vs_spec.py --tag swift-macos --save")


if __name__ == "__main__":
    main()
