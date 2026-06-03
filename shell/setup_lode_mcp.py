#!/usr/bin/env python3
"""
setup_lode_mcp.py — Wire Lode's Cowork/Claude Code session to Vein via MCP.

Replaces the lossy `export_lore_to_lode.py` snapshot path (Option A).
After this, the Lode session calls vein_recall / vein_brief LIVE against
Vein's central .vein/ store — full fidelity, always fresh, no mount/copy.

What it does:
  1. Locates the `vein` CLI (PATH, then `python3 -m vein` fallback).
  2. Verifies the Vein store works (`vein status` at VEIN_ROOT).
  3. Merges a `vein-vein` server into Lode's project-level `.mcp.json`
     (idempotent — safe to re-run; won't clobber other servers).
  4. Prints the next step + how to confirm vein_status in the session.

Usage:
  python3 shell/setup_lode_mcp.py
  python3 shell/setup_lode_mcp.py --lode /path/to/lode --vein /path/to/vein
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

VEIN_DEFAULT = Path("/Users/lion/Documents/vein")
LODE_DEFAULT = Path("/Users/lion/Documents/lode")
SERVER_NAME = "vein-vein"


def resolve_vein_cli() -> list[str]:
    """Return the argv prefix that invokes the vein CLI."""
    exe = shutil.which("vein")
    if exe:
        return [exe]
    # fallback: module invocation
    try:
        subprocess.run(
            [sys.executable, "-m", "vein", "--help"],
            capture_output=True, check=True,
        )
        return [sys.executable, "-m", "vein"]
    except Exception:
        print("[error] `vein` CLI not found on PATH and `python3 -m vein` "
              "failed.\n        → pip install lode-vein  (or: pip install -e "
              f"{VEIN_DEFAULT})")
        sys.exit(1)


def verify_store(vein_argv: list[str], vein_root: Path) -> None:
    """Run `vein status` at vein_root — the same backend the MCP server serves."""
    print(f"[1/3] Verifying Vein store at {vein_root} ...")
    r = subprocess.run(
        vein_argv + ["status"],
        cwd=str(vein_root), capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("[error] `vein status` failed — store not usable:\n"
              + (r.stderr or r.stdout))
        sys.exit(1)
    print("        OK:", (r.stdout or "").strip().splitlines()[0]
          if r.stdout.strip() else "(no output)")


def merge_mcp_config(lode_root: Path, vein_argv: list[str],
                     vein_root: Path) -> Path:
    """Idempotently add the vein-vein server to Lode's .mcp.json."""
    cfg_path = lode_root / ".mcp.json"
    print(f"[2/3] Merging '{SERVER_NAME}' into {cfg_path} ...")

    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[error] {cfg_path} is not valid JSON: {e}")
            sys.exit(1)
    else:
        cfg = {}

    servers = cfg.setdefault("mcpServers", {})
    # `command`/`args`: prefer a bare `vein` for portability; fall back to the
    # resolved module invocation only when no `vein` shim exists on PATH.
    if shutil.which("vein"):
        command, args = "vein", ["mcp"]
    else:
        command, args = vein_argv[0], vein_argv[1:] + ["mcp"]

    servers[SERVER_NAME] = {
        "command": command,
        "args": args,
        "cwd": str(vein_root),
    }
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"        Wrote {SERVER_NAME} → cwd={vein_root}")
    print(f"        Other servers preserved: "
          f"{[k for k in servers if k != SERVER_NAME] or 'none'}")
    return cfg_path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--lode", default=str(LODE_DEFAULT))
    p.add_argument("--vein", default=str(VEIN_DEFAULT))
    args = p.parse_args()

    lode_root = Path(args.lode).expanduser().resolve()
    vein_root = Path(args.vein).expanduser().resolve()

    if not (vein_root / ".vein").exists():
        print(f"[error] no .vein/ under {vein_root} — run `vein init` there first")
        sys.exit(1)
    if not lode_root.exists():
        print(f"[error] {lode_root} not found")
        sys.exit(1)

    vein_argv = resolve_vein_cli()
    verify_store(vein_argv, vein_root)
    cfg_path = merge_mcp_config(lode_root, vein_argv, vein_root)

    print("[3/3] Done.\n")
    print("Next:")
    print(f"  • Restart / reopen the Lode session so it loads {cfg_path.name}.")
    print("  • In the Lode session, confirm it's live with:  call vein_status")
    print("    Expect e.g.:  lode (Phase 0) — N lore entries: ...")
    print("\nThe lossy snapshot (docs/vein_lore.md + export_lore_to_lode.py) is "
          "now redundant; you can delete it once vein_status returns in Lode.")


if __name__ == "__main__":
    main()
