"""vein brief — print orientation digest."""

from __future__ import annotations

import click
from rich.console import Console
from rich.markdown import Markdown

from ..core.brief import generate_brief
from ..core.store import VeinStore

console = Console()


@click.command("brief")
@click.option("--regen", is_flag=True, help="Force regenerate (ignore TTL cache)")
@click.option("--raw", is_flag=True, help="Print raw markdown, no rich rendering")
def cmd_brief(regen: bool, raw: bool) -> None:
    """Print an orientation digest of this project's lore.

    Covers: top decisions, active pitfalls, recent lore, current focus.
    Cached in .vein/BRIEF.md (TTL = 1 hour, or until next vein log).
    """
    store = VeinStore.require()
    content = generate_brief(store, regen=regen)

    if raw:
        click.echo(content)
    else:
        console.print(Markdown(content))
