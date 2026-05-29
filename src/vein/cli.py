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
from .commands.status import cmd_status


@click.group()
@click.version_option(__version__, prog_name="vein")
def main() -> None:
    """Vein — Decision & debug lore archive for AI-assisted development.

    \b
    Quick start:
      vein init                          initialize .vein/ in current project
      vein log decision "why X not Y"   capture a decision
      vein status                        show .vein/ stats
      vein brief                         print orientation digest
      vein ask "why callback?"           keyword search
      vein recall "DMA timeout"          semantic search (embed + FTS)
      vein list --type pitfall           list entries
      vein reindex                       rebuild search index
      vein import docs/decisions.md      bulk-import existing docs
      vein run cargo check               run + auto-triage on failure
      cargo check 2>&1 | vein pipe       pipe error → triage

    \b
    Lode finds the code. Vein remembers the why.
    """


main.add_command(cmd_init,    name="init")
main.add_command(cmd_log,     name="log")
main.add_command(cmd_status,  name="status")
main.add_command(cmd_brief,   name="brief")
main.add_command(cmd_ask,     name="ask")
main.add_command(cmd_recall,  name="recall")
main.add_command(cmd_list,    name="list")
main.add_command(cmd_reindex, name="reindex")
main.add_command(cmd_import,  name="import")
main.add_command(cmd_pipe,    name="pipe")
main.add_command(cmd_run,     name="run")
main.add_command(cmd_walk,    name="walk")
