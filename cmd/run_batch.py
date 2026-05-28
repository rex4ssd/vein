#!/usr/bin/env python3
"""
run_batch.py — folder-based sequential command runner with full .log

Given a folder, finds all .sh and .py files, sorts them naturally
(01_xxx.sh before 02_xxx.py), then executes in order.
On failure: logs error + breaks. Writes complete timestamped .log.

Usage:
  python cmd/run_batch.py <folder>                    # run all scripts
  python cmd/run_batch.py <folder> --dry-run          # list only, no execute
  python cmd/run_batch.py <folder> --log <path>       # custom log file path
  python cmd/run_batch.py <folder> --no-break         # continue on failure (warn, don't stop)
  python cmd/run_batch.py <folder> --ext .sh .py .zsh # filter extensions (default: .sh .py)

Exit code:
  0 — all steps passed (or dry-run)
  1 — one or more steps failed
  2 — folder not found or no scripts found

Log file location (default):
  <folder>/logs/run_YYYYMMDD_HHMMSS.log
  Also symlinked to: <folder>/logs/run_latest.log
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ──────────────────────────── natural sort ────────────────────────────

def _natural_key(path: Path) -> list:
    """Sort key: split numeric and alpha tokens so 02 < 10."""
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def _collect_scripts(folder: Path, extensions: list[str]) -> list[Path]:
    exts = {e if e.startswith(".") else f".{e}" for e in extensions}
    scripts = [p for p in folder.iterdir()
               if p.is_file() and p.suffix.lower() in exts and not p.name.startswith("_")]
    return sorted(scripts, key=_natural_key)


# ──────────────────────────── logging ────────────────────────────

def _setup_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("RunBatch")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)-7s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def _symlink_latest(log_path: Path) -> None:
    latest = log_path.parent / "run_latest.log"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(log_path.name)
    except Exception:
        pass  # non-fatal


# ──────────────────────────── step execution ────────────────────────────

class StepResult:
    def __init__(self, script: Path, ok: bool, rc: int, elapsed_ms: int,
                 stdout: str, stderr: str):
        self.script = script
        self.ok = ok
        self.rc = rc
        self.elapsed_ms = elapsed_ms
        self.stdout = stdout
        self.stderr = stderr

    @property
    def label(self) -> str:
        return self.script.name


def _run_step(script: Path, log: logging.Logger, env: dict) -> StepResult:
    """Execute one script. Returns StepResult with full stdout/stderr captured."""
    import time

    if script.suffix.lower() == ".py":
        cmd = [sys.executable, str(script)]
    else:
        cmd = ["bash", str(script)]

    log.info("┌─ START: %s", script.name)
    log.debug("   cmd: %s", " ".join(cmd))
    log.debug("   cwd: %s", str(PROJECT_ROOT))

    t0 = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    ok = proc.returncode == 0

    # always log stdout/stderr to file (DEBUG), summary to console
    if proc.stdout.strip():
        for line in proc.stdout.strip().splitlines():
            log.debug("   stdout │ %s", line)
    if proc.stderr.strip():
        for line in proc.stderr.strip().splitlines():
            log.debug("   stderr │ %s", line)

    status = "✓ OK" if ok else f"✗ FAIL (exit {proc.returncode})"
    log.info("└─ %s  [%dms]  %s", status, elapsed_ms, script.name)

    return StepResult(script, ok, proc.returncode, elapsed_ms,
                      proc.stdout, proc.stderr)


# ──────────────────────────── main runner ────────────────────────────

def run_batch(
    folder: Path,
    *,
    dry_run: bool = False,
    log_path: Path | None = None,
    no_break: bool = False,
    extensions: list[str] | None = None,
) -> int:
    """
    Returns:
      0 — all OK (or dry-run)
      1 — at least one step failed
      2 — bad args / no scripts
    """
    if not folder.is_dir():
        print(f"ERROR: not a directory: {folder}", file=sys.stderr)
        return 2

    exts = extensions or [".sh", ".py"]
    scripts = _collect_scripts(folder, exts)

    if not scripts:
        print(f"No scripts found in {folder} (extensions: {exts})", file=sys.stderr)
        return 2

    # default log path
    if log_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = folder / "logs" / f"run_{ts}.log"

    log = _setup_logger(log_path)
    _symlink_latest(log_path)

    # ── header ──
    log.info("═" * 60)
    log.info("  run_batch.py  —  %s", datetime.now().isoformat())
    log.info("  folder   : %s", folder)
    log.info("  scripts  : %d found", len(scripts))
    log.info("  dry-run  : %s", dry_run)
    log.info("  break    : %s", not no_break)
    log.info("  log      : %s", log_path)
    log.info("═" * 60)

    # ── dry-run: just list ──
    if dry_run:
        for i, s in enumerate(scripts, 1):
            log.info("  [%02d] %s", i, s.name)
        log.info("dry-run complete — nothing executed")
        return 0

    # ── execute ──
    results: list[StepResult] = []
    env = {**os.environ, "VEIN_BATCH": "1",
           "VEIN_PROJECT_ROOT": str(PROJECT_ROOT)}

    for i, script in enumerate(scripts, 1):
        log.info("")
        log.info("[Step %d/%d]", i, len(scripts))
        r = _run_step(script, log, env)
        results.append(r)

        if not r.ok:
            if no_break:
                log.warning("  step failed — continuing (--no-break)")
            else:
                log.error("  step failed — stopping (use --no-break to continue)")
                # log remaining as SKIPPED
                for j, skipped in enumerate(scripts[i:], i + 1):
                    log.info("[Step %d/%d] SKIPPED: %s", j, len(scripts), skipped.name)
                break

    # ── summary ──
    passed = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    skipped_count = len(scripts) - len(results)
    total_ms = sum(r.elapsed_ms for r in results)

    log.info("")
    log.info("═" * 60)
    log.info("  SUMMARY")
    log.info("  ✓ passed : %d", len(passed))
    log.info("  ✗ failed : %d", len(failed))
    log.info("  ○ skipped: %d", skipped_count)
    log.info("  ⏱ total  : %dms", total_ms)

    if failed:
        log.info("")
        log.error("  FAILED STEPS:")
        for r in failed:
            log.error("    ✗ %s (exit %d, %dms)", r.label, r.rc, r.elapsed_ms)
            # print last 5 lines of stderr to log for quick diagnosis
            if r.stderr.strip():
                tail = r.stderr.strip().splitlines()[-5:]
                for line in tail:
                    log.error("      stderr: %s", line)

    log.info("═" * 60)
    log.info("  log saved: %s", log_path)

    return 1 if failed else 0


# ──────────────────────────── CLI ────────────────────────────

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="run_batch.py",
        description="Run all scripts in a folder in natural order. Break on failure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("folder", type=Path,
                   help="Folder containing scripts to run (e.g. cmd/batch/)")
    p.add_argument("--dry-run", action="store_true",
                   help="List scripts without executing")
    p.add_argument("--log", type=Path, default=None, metavar="PATH",
                   help="Custom log file path (default: <folder>/logs/run_TIMESTAMP.log)")
    p.add_argument("--no-break", action="store_true",
                   help="Continue to next step even if current step fails")
    p.add_argument("--ext", nargs="+", default=[".sh", ".py"], metavar="EXT",
                   help="File extensions to include (default: .sh .py)")
    return p.parse_args(argv[1:])


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    return run_batch(
        args.folder.resolve(),
        dry_run=args.dry_run,
        log_path=args.log,
        no_break=args.no_break,
        extensions=args.ext,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv))
