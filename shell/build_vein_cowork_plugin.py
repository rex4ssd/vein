#!/usr/bin/env python3
"""
build_vein_cowork_plugin.py — Package Vein's MCP server as a Cowork plugin.

WHY THIS (not lode/.mcp.json):
  Cowork desktop does NOT read a project-root `.mcp.json` or
  claude_desktop_config.json. The only way to give a Cowork session a LOCAL
  (stdio) MCP server is to bundle it inside a *plugin* and install that plugin
  via Customize → Plugins. (Custom *connectors* require a public URL reachable
  from Anthropic's servers — no good for a local-first tool like vein.)

  Ref: support.claude.com "Use plugins in Claude" — "Plugins may include local
  MCP servers that run on your computer."

WHAT IT BUILDS:
  dist/vein-lore-plugin/
    .claude-plugin/plugin.json   ← manifest
    .mcp.json                    ← the vein MCP server (abs path + --project)
    README.md
  dist/vein-lore-plugin.zip      ← upload this in Cowork

Run it INSIDE your venv (so the abs path to `vein` gets baked in correctly):
  cd /Users/lion/Documents/vein && python3 shell/build_vein_cowork_plugin.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

VEIN_DEFAULT = Path("/Users/lion/Documents/vein")
PLUGIN_NAME = "vein-lore-plugin"
SERVER_NAME = "vein"  # tools appear as vein_recall / vein_brief / vein_status / vein_log


def resolve_vein_exe() -> str:
    """Absolute path to the `vein` CLI. GUI-launched MCP has no venv activated,
    so a bare 'vein' won't resolve — we need the absolute path from THIS venv."""
    exe = shutil.which("vein")
    if exe:
        return str(Path(exe).resolve())
    print("[error] `vein` not on PATH. Activate your venv and re-run, or "
          f"`pip install -e {VEIN_DEFAULT}` first.")
    sys.exit(1)


def verify_store(vein_exe: str, vein_root: Path) -> str:
    print(f"[1/4] Verifying `vein status` at {vein_root} ...")
    r = subprocess.run([vein_exe, "status"], cwd=str(vein_root),
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("[error] vein status failed:\n" + (r.stderr or r.stdout))
        sys.exit(1)
    line = (r.stdout or "").strip().splitlines()
    msg = line[0] if line else "(ok)"
    print("        OK:", msg)
    return msg


def build_plugin(vein_root: Path, vein_exe: str) -> Path:
    dist = vein_root / "dist"
    pdir = dist / PLUGIN_NAME
    if pdir.exists():
        shutil.rmtree(pdir)
    (pdir / ".claude-plugin").mkdir(parents=True)

    print(f"[2/4] Writing plugin → {pdir}")

    # manifest
    (pdir / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": PLUGIN_NAME,
        "description": "Vein decision & debug lore — live MCP access to the "
                       "central .vein/ store (recall / brief / log / status).",
        "version": "0.1.0",
        "author": {"name": "rex4ssd"},
    }, indent=2) + "\n", encoding="utf-8")

    # MCP server: absolute exe + --project so it never depends on launch cwd
    (pdir / ".mcp.json").write_text(json.dumps({
        "mcpServers": {
            SERVER_NAME: {
                "command": vein_exe,
                "args": ["mcp", "--project", str(vein_root)],
            }
        }
    }, indent=2) + "\n", encoding="utf-8")

    (pdir / "README.md").write_text(
        f"# {PLUGIN_NAME}\n\n"
        "Bundles the `vein mcp` stdio server so any Cowork session (e.g. the "
        "Lode project) can call vein lore live:\n\n"
        "- `vein_brief()` — session primer\n"
        "- `vein_recall(query)` — search decisions / pitfalls / lore\n"
        "- `vein_log(type, message)` — capture new lore\n"
        "- `vein_status()` — entry counts\n\n"
        f"Points at the central store: `{vein_root}`\n", encoding="utf-8")

    return pdir


def zip_plugin(pdir: Path) -> Path:
    zpath = pdir.with_suffix(".zip")
    if zpath.exists():
        zpath.unlink()
    print(f"[3/4] Zipping → {zpath}")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in pdir.rglob("*"):
            if f.is_file():
                z.write(f, f"{pdir.name}/{f.relative_to(pdir)}")
    return zpath


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vein", default=str(VEIN_DEFAULT))
    args = ap.parse_args()

    vein_root = Path(args.vein).expanduser().resolve()
    if not (vein_root / ".vein").exists():
        print(f"[error] no .vein/ under {vein_root}")
        sys.exit(1)

    vein_exe = resolve_vein_exe()
    verify_store(vein_exe, vein_root)
    pdir = build_plugin(vein_root, vein_exe)
    zpath = zip_plugin(pdir)

    print("[4/4] Done.\n")
    print(f"Plugin dir : {pdir}")
    print(f"Plugin zip : {zpath}")
    print(f"vein exe   : {vein_exe}\n")
    print("Install in Cowork:")
    print("  1. Open the Cowork tab → Customize (left sidebar) → Plugins tab.")
    print("  2. Personal plugins → '+' → upload the .zip above.")
    print("  3. Reopen the Lode session, then in chat:  call vein_status")
    print("     Expect:  vein  Phase 0 ...  (or: lode (Phase 0) — N entries)\n")
    print("If a server-name clash appears, edit .mcp.json's key and re-zip.")


if __name__ == "__main__":
    main()
