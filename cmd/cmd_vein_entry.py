#!/usr/bin/env python3
"""
cmd_vein_entry.py — vein 開發指令快速選單。

使用方式：
  python cmd/cmd_vein_entry.py              # 列出所有指令
  python cmd/cmd_vein_entry.py 3            # 執行第 3 筆
  python cmd/cmd_vein_entry.py 1 2 3        # 依序執行 1 → 2 → 3
  python cmd/cmd_vein_entry.py 1,2,3        # 同上

格式：CSV（cmd, cmd_queue, desc）
  - cmd 以 shell: 開頭 → bash -lc 執行（cwd = 專案根目錄）
  - cmd_queue 以分號分隔，任一失敗中斷該鏈
  - # 開頭整行略過（支援 # key=value 變數宣告）
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
import shlex
import string
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CSV_PATH = SCRIPT_DIR / "cmd_vein_entry.csv"
LOG_PATH = SCRIPT_DIR / "cmd_vein_entry.log"

_COMMA_RE = re.compile(r"[,，]")
_VAR_DEF_RE = re.compile(r"^#\s*([A-Za-z_]\w*)=(\S.*?)\s*$")


# ──────────────────────────── logging ────────────────────────────

def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("CmdVeinEntry")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                             datefmt="%H:%M:%S")
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ──────────────────────────── CSV parsing ────────────────────────────

def _scan_vars(lines: list[str]) -> dict[str, str]:
    vars_: dict[str, str] = {}
    for line in lines:
        s = line.lstrip()
        if s.startswith("###"):
            continue
        if not s.startswith("#"):
            continue
        m = _VAR_DEF_RE.match(s)
        if m:
            vars_[m.group(1)] = m.group(2)
    return vars_


def _subst(text: str, vars_: dict[str, str]) -> str:
    if not vars_ or "$" not in text:
        return text
    return string.Template(text).safe_substitute(vars_)


def _load_entries(vars_: dict[str, str]) -> list[dict]:
    """Read CSV, skip comments/blanks, return list of {cmd, queue_steps, desc}."""
    raw = CSV_PATH.read_text(encoding="utf-8")
    lines = raw.splitlines()
    entries: list[dict] = []
    reader = csv.reader(io.StringIO(raw))
    for row in reader:
        if not row:
            continue
        first = row[0].strip()
        if not first or first.startswith("#"):
            continue
        if first.lower() == "cmd":
            continue  # header row
        cmd = _subst(first, vars_)
        queue_raw = row[1].strip() if len(row) > 1 else ""
        desc = row[2].strip() if len(row) > 2 else ""
        queue_steps = [_subst(s.strip(), vars_)
                       for s in queue_raw.split(";") if s.strip()] if queue_raw else []
        entries.append({"cmd": cmd, "queue": queue_steps, "desc": desc})
    return entries


# ──────────────────────────── execution ────────────────────────────

def _run_shell(shell_line: str, log: logging.Logger) -> bool:
    """Run a shell: prefixed command via bash -lc, cwd = PROJECT_ROOT."""
    cmd_str = shell_line.removeprefix("shell:").strip()
    log.info("▶ shell: %s", cmd_str)
    result = subprocess.run(
        ["bash", "-lc", cmd_str],
        cwd=str(PROJECT_ROOT),
        capture_output=False,          # let stdout/stderr flow to terminal
    )
    if result.returncode != 0:
        log.error("✗ exit %d: %s", result.returncode, cmd_str)
        return False
    log.info("✓ ok: %s", cmd_str[:80])
    return True


def _run_python(cmd_str: str, log: logging.Logger) -> bool:
    """Run a .py script with sys.executable, cwd = PROJECT_ROOT."""
    parts = shlex.split(cmd_str)
    script = PROJECT_ROOT / parts[0]
    args = parts[1:]
    log.info("▶ python: %s %s", script.name, " ".join(args))
    result = subprocess.run(
        [sys.executable, str(script)] + args,
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        log.error("✗ exit %d: %s", result.returncode, cmd_str)
        return False
    log.info("✓ ok: %s", script.name)
    return True


def _run_step(step: str, log: logging.Logger) -> bool:
    if step.startswith("shell:"):
        return _run_shell(step, log)
    return _run_python(step, log)


def _run_entry(entry: dict, log: logging.Logger) -> bool:
    """Run cmd, then each queue step in order. Break on first failure."""
    if not _run_step(entry["cmd"], log):
        return False
    for step in entry["queue"]:
        if not _run_step(step, log):
            return False
    return True


# ──────────────────────────── menu ────────────────────────────

def _print_menu(entries: list[dict]) -> None:
    print(f"\n{'─' * 60}")
    print("  Vein development commands")
    print(f"{'─' * 60}")
    section = ""
    for i, e in enumerate(entries, 1):
        # desc 開頭 【xxx】 用作 section header
        m = re.match(r"【(\w+)】", e["desc"])
        if m and m.group(1) != section:
            section = m.group(1)
            print(f"\n  [{section}]")
        label = re.sub(r"^【\w+】", "", e["desc"]).strip() or e["cmd"][:60]
        print(f"  {i:>2}. {label}")
    print(f"\n{'─' * 60}")
    print("  Usage: python cmd/cmd_vein_entry.py <N> [N2 N3 ...]")
    print(f"{'─' * 60}\n")


# ──────────────────────────── arg parsing ────────────────────────────

def _parse_nums(argv: list[str]) -> list[int]:
    nums: list[int] = []
    for token in argv:
        token = _COMMA_RE.sub(",", token).rstrip(",")
        for part in token.split(","):
            part = part.strip()
            if part.isdigit():
                nums.append(int(part))
    return nums


# ──────────────────────────── main ────────────────────────────

def main(argv: list[str]) -> int:
    log = _setup_logger()
    log.info("📄 log: %s", LOG_PATH)

    raw_lines = CSV_PATH.read_text(encoding="utf-8").splitlines()
    vars_ = _scan_vars(raw_lines)
    entries = _load_entries(vars_)

    args = argv[1:]
    if not args:
        _print_menu(entries)
        return 0

    nums = _parse_nums(args)
    if not nums:
        print(f"Usage: python {argv[0]} <number> [number ...]", file=sys.stderr)
        return 1

    failures: list[str] = []
    for n in nums:
        if n < 1 or n > len(entries):
            log.error("編號 %d 超出範圍（1~%d）", n, len(entries))
            failures.append(f"#{n} out of range")
            continue
        entry = entries[n - 1]
        log.info("── 執行 #%d: %s", n, entry["desc"] or entry["cmd"][:60])
        ok = _run_entry(entry, log)
        if not ok:
            failures.append(f"#{n}: {entry['desc'] or entry['cmd'][:60]}")

    if failures:
        log.error("─── FAILED ───")
        for f in failures:
            log.error("  %s", f)
        return 1

    log.info("─── ALL OK ───")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
