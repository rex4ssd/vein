"""vein hooks — manage git hooks for a project.

Usage:
  vein hooks install          install post-commit hook in .git/hooks/
  vein hooks remove           remove the hook
  vein hooks status           show whether hook is installed
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import click
from rich.console import Console

console = Console()

# ── hook script written to .git/hooks/post-commit ───────────────────────────

_HOOK_SCRIPT = """\
#!/usr/bin/env bash
# vein post-commit hook — installed by `vein hooks install`
# Remove with: vein hooks remove
#
# Runs `vein debrief --silent` after every commit.
# Local AI (ollama) scans the diff and auto-logs decisions worth keeping.
# If ollama is unavailable or finds nothing, exits silently.

vein debrief --silent 2>&1 || true
"""

_VEIN_MARKER = "# vein post-commit hook"


def _find_git_dir(start: Path) -> Path | None:
    """Locate the real .git directory, including worktrees and submodules.

    ``.git`` is a *file* containing ``gitdir: <path>`` in linked worktrees,
    submodules, and ``--separate-git-dir`` checkouts. Requiring a directory
    walked past those and installed the hook into the enclosing superproject's
    .git instead — the wrong repo, silently.
    """
    for p in [start, *start.parents]:
        git = p / ".git"
        if git.is_dir():
            return git
        if git.is_file():
            try:
                text = git.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if text.startswith("gitdir:"):
                target = Path(text.split(":", 1)[1].strip())
                if not target.is_absolute():
                    target = (p / target).resolve()
                if target.is_dir():
                    return target
    return None


def _hooks_path_override() -> str | None:
    """``core.hooksPath`` if set — git then ignores ``.git/hooks/`` entirely.

    Husky, pre-commit and lefthook all set it, as do some corporate global
    configs. Without this check vein reports a hook installed and working while
    git never runs it.
    """
    import subprocess
    try:
        r = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = r.stdout.strip()
    return value or None


# ── subcommand group ─────────────────────────────────────────────────────────

@click.group("hooks")
def cmd_hooks() -> None:
    """Manage git hooks for vein lore capture.

    \b
    vein hooks install    add post-commit hook → prompts to log after each commit
    vein hooks remove     remove the hook
    vein hooks status     show hook state
    """


@cmd_hooks.command("install")
@click.option("--yes", "-y", is_flag=True, help="Overwrite existing hook without asking")
def hooks_install(yes: bool) -> None:
    """Install post-commit hook in the nearest .git/hooks/.

    After every `git commit`, local AI scans the diff and auto-logs anything
    worth keeping (`vein debrief --silent`). No ollama → exits silently.
    Requires `vein` on PATH (already true if you ran this command).
    """
    git_dir = _find_git_dir(Path.cwd())
    if not git_dir:
        console.print("[red]No .git/ found.[/] Run from inside a git repository.")
        raise SystemExit(1)

    override = _hooks_path_override()
    if override:
        console.print(
            f"[yellow]Warning:[/] this repo sets [bold]core.hooksPath = {override}[/], "
            f"so git will not run anything in .git/hooks/.\n"
            f"[dim]Add `vein debrief --silent 2>&1 || true` to "
            f"{override}/post-commit instead.[/]\n"
        )

    hook_path = git_dir / "hooks" / "post-commit"
    hook_path.parent.mkdir(exist_ok=True)

    if hook_path.exists():
        existing = hook_path.read_text(encoding="utf-8")
        if _VEIN_MARKER in existing:
            console.print(f"[yellow]Already installed:[/] {hook_path}")
            return
        # foreign hook exists
        if not yes:
            click.confirm(
                f"A post-commit hook already exists at {hook_path}.\n"
                "Append vein block to it?",
                abort=True,
            )
        # append
        with hook_path.open("a", encoding="utf-8") as f:
            f.write("\n" + _HOOK_SCRIPT)
        console.print(f"[green]✓ Appended[/] vein hook to existing {hook_path}")
    else:
        hook_path.write_text(_HOOK_SCRIPT, encoding="utf-8")
        console.print(f"[green]✓ Installed[/] {hook_path}")

    # make executable
    current = hook_path.stat().st_mode
    hook_path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    proj_root = git_dir.parent
    console.print(
        f"\n  Project: [cyan]{proj_root}[/]\n"
        f"  After each commit: [dim]vein debrief --silent[/] runs automatically"
    )


@cmd_hooks.command("remove")
def hooks_remove() -> None:
    """Remove the vein post-commit hook (or vein block from a shared hook)."""
    git_dir = _find_git_dir(Path.cwd())
    if not git_dir:
        console.print("[red]No .git/ found.[/]")
        raise SystemExit(1)

    hook_path = git_dir / "hooks" / "post-commit"
    if not hook_path.exists():
        console.print("[dim]No post-commit hook found.[/]")
        return

    content = hook_path.read_text(encoding="utf-8")
    if _VEIN_MARKER not in content:
        console.print("[yellow]No vein block found in hook.[/] Nothing removed.")
        return

    # Exact-match replace only works if the block is byte-identical to the
    # current _HOOK_SCRIPT. Edit one line, check out with CRLF, or install with
    # an older vein, and both replaces are no-ops — the old code then wrote the
    # unchanged text back and still printed "✓ Removed". Drop from the marker
    # line to the end of the vein block instead, and verify afterwards.
    cleaned = content.replace("\n" + _HOOK_SCRIPT, "").replace(_HOOK_SCRIPT, "")
    if _VEIN_MARKER in cleaned:
        kept, dropping = [], False
        for line in cleaned.splitlines():
            if _VEIN_MARKER in line:
                dropping = True
                if kept and kept[-1].startswith("#!"):
                    pass  # keep a shebang that preceded our block
                continue
            if dropping:
                # The block is our comment header plus the vein command line;
                # stop dropping once past it.
                if line.strip().startswith("vein "):
                    dropping = False
                    continue
                if line.strip() and not line.lstrip().startswith("#"):
                    dropping = False
                    kept.append(line)
                continue
            kept.append(line)
        cleaned = "\n".join(kept)

    cleaned = cleaned.rstrip("\n") + "\n"

    if _VEIN_MARKER in cleaned or "vein debrief" in cleaned:
        console.print(
            f"[yellow]Could not cleanly remove the vein block[/] from {hook_path}.\n"
            f"[dim]It looks hand-edited — delete the vein lines yourself.[/]"
        )
        return

    remaining = cleaned.strip()
    if remaining in ("", "#!/usr/bin/env bash"):
        hook_path.unlink()
        console.print(f"[green]✓ Removed[/] {hook_path}")
    else:
        hook_path.write_text(cleaned, encoding="utf-8")
        console.print(f"[green]✓ Removed vein block[/] from {hook_path}")


@cmd_hooks.command("status")
def hooks_status() -> None:
    """Show whether the vein post-commit hook is installed."""
    git_dir = _find_git_dir(Path.cwd())
    if not git_dir:
        console.print("[red]No .git/ found.[/]")
        return

    hook_path = git_dir / "hooks" / "post-commit"
    if not hook_path.exists():
        console.print("[dim]post-commit hook:[/] not installed")
        return

    content = hook_path.read_text(encoding="utf-8")
    executable = os.access(hook_path, os.X_OK)

    if _VEIN_MARKER in content:
        console.print(f"[green]✓ vein hook installed[/]  {hook_path}")
        if not executable:
            console.print("[yellow]  ⚠ not executable — run: chmod +x[/] " + str(hook_path))
        override = _hooks_path_override()
        if override:
            console.print(
                f"[yellow]  ⚠ core.hooksPath = {override} — git will not run this hook.[/]"
            )
    else:
        console.print(f"[yellow]post-commit exists but has no vein block[/]  {hook_path}")
        console.print("  Run [bold]vein hooks install[/] to append.")
