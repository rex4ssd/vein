"""vein — CLI entry point."""

from __future__ import annotations

import click

from . import __version__
from .commands.ask import cmd_ask
from .commands.brief import cmd_brief
from .commands.import_cmd import cmd_import
from .commands.init import cmd_init
from .commands.list_cmd import cmd_list
from .commands.log import cmd_log
from .commands.pipe import cmd_pipe
from .commands.recall import cmd_recall
from .commands.walk import cmd_walk
from .commands.reindex import cmd_reindex
from .commands.run import cmd_run
from .commands.debrief import cmd_debrief
from .commands.fetch import cmd_fetch
from .commands.gc import cmd_gc
from .commands.harvest import cmd_night_harvest, cmd_morning
from .commands.study import cmd_study
from .commands.hooks import cmd_hooks
from .commands.mcp_server import cmd_mcp
from .commands.status import cmd_status

# ── advanced command metadata (shown by `vein more`) ─────────────────────────
_ADVANCED = [
    ("ask",           "Keyword search (no index needed)"),
    ("list",          "List entries with filters"),
    ("reindex",       "Rebuild FTS5 + embedding index"),
    ("import",        "Bulk-import decisions.md or any .md"),
    ("debrief",       "AI diff scan → auto-log decisions from git commits"),
    ("hooks",         "Manage git post-commit hook (auto-runs debrief)"),
    ("fetch",         "Fetch a GitHub repo → extract lore → .vein/references/"),
    ("study",         "Batch-fetch repos, compare, manage watchlists"),
    ("night-harvest", "Nightly pipeline: watchlist + debrief + morning brief"),
    ("morning",       "Print today's morning brief"),
    ("gc",            "Garbage-collect stale or unwanted entries"),
    ("run",           "Run a command; auto-triage on failure"),
    ("pipe",          "Pipe error output → search lore + AI triage"),
    ("mcp",           "Start MCP server for Claude Desktop"),
    ("walk",          "Multi-agent workflow runner"),
]


@click.group()
@click.version_option(__version__, prog_name="vein")
def main() -> None:
    """Vein — Decision & debug lore archive for AI-assisted development.

    \b
    Essentials:
      vein init                        initialize .vein/ in current project
      vein log d "why X not Y"         capture a decision  (d/l/p/r)
      vein recall "query"              search lore (semantic + FTS + grep)
      vein brief                       orientation digest for AI sessions
      vein status                      project overview

    \b
    Advanced: run `vein more` to list all commands.
    Lode finds the code. Vein remembers the why.
    """


@main.command("more", hidden=False)
def cmd_more() -> None:
    """List all advanced commands."""
    click.echo("\nAdvanced commands:\n")
    for name, desc in _ADVANCED:
        click.echo(f"  vein {name:<16} {desc}")
    click.echo("\nRun `vein COMMAND --help` for details.\n")


# ── core (always visible) ─────────────────────────────────────────────────────
main.add_command(cmd_init,   name="init")
main.add_command(cmd_log,    name="log")
main.add_command(cmd_recall, name="recall")
main.add_command(cmd_brief,  name="brief")
main.add_command(cmd_status, name="status")

# ── advanced (hidden from --help, fully functional) ───────────────────────────
_HIDDEN = [
    (cmd_ask,           "ask"),
    (cmd_list,          "list"),
    (cmd_reindex,       "reindex"),
    (cmd_import,        "import"),
    (cmd_debrief,       "debrief"),
    (cmd_hooks,         "hooks"),
    (cmd_fetch,         "fetch"),
    (cmd_study,         "study"),
    (cmd_night_harvest, "night-harvest"),
    (cmd_morning,       "morning"),
    (cmd_gc,            "gc"),
    (cmd_run,           "run"),
    (cmd_pipe,          "pipe"),
    (cmd_mcp,           "mcp"),
    (cmd_walk,          "walk"),
]
for _cmd, _name in _HIDDEN:
    _cmd.hidden = True
    main.add_command(_cmd, name=_name)
