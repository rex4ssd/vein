"""vein — CLI entry point."""

from __future__ import annotations

import click

from . import __version__
from .commands.ask import cmd_ask
from .commands.brief import cmd_brief
from .commands.init import cmd_init
from .commands.log import cmd_log
from .commands.recall import cmd_recall
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
      vein ask "why callback?"           search for an answer

    \b
    Lode finds the code. Vein remembers the why.
    """


main.add_command(cmd_init,   name="init")
main.add_command(cmd_log,    name="log")
main.add_command(cmd_status, name="status")
main.add_command(cmd_brief,  name="brief")
main.add_command(cmd_ask,    name="ask")
main.add_command(cmd_recall, name="recall")
