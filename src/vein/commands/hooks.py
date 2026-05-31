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
    """Walk up to find .git/"""
    for p in [start, *start.parents]:
        git = p / ".git"
        if git.is_dir():
            return git
    return None


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

    After every `git commit`, the hook asks:
      d = decision  l = lore  p = pitfall  Enter = skip

    The prompt is non-blocking — Enter skips in under a second.
    Requires `vein` on PATH (already true if you ran this command).
    """
    git_dir = _find_git_dir(Path.cwd())
    if not git_dir:
        console.print("[red]No .git/ found.[/] Run from inside a git repository.")
        raise SystemExit(1)

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
        f"  Next commit will prompt: [dim]d / l / p / Enter=skip[/]"
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

    # strip vein block
    lines = content.splitlines(keepends=True)
    out, skip = [], False
    for line in lines:
        if _VEIN_MARKER in line:
            skip = True
        if not skip:
            out.append(line)
        # stop skipping after the empty line following esac
        if skip and line.strip() == "":
            pass  # keep skipping until we hit next non-vein content

    cleaned = "".join(out).rstrip("\n") + "\n"

    if cleaned.strip() in ("#!/usr/bin/env bash", ""):
        # nothing left but the shebang — delete the file
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
    else:
        console.print(f"[yellow]post-commit exists but has no vein block[/]  {hook_path}")
        console.print("  Run [bold]vein hooks install[/] to append.")
