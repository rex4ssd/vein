"""vein init — initialize .vein/ in the current project."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from ..core import registry
from ..core.store import VeinStore

console = Console()


@click.command("init")
@click.argument("name", required=False)
@click.option("--force", is_flag=True, help="Re-create even if .vein/ already exists")
def cmd_init(name: str | None, force: bool) -> None:
    """Initialize .vein/ in the current directory.

    NAME is the project name (defaults to current directory name).
    """
    cwd = Path.cwd()
    project_name = name or cwd.name

    store = VeinStore(cwd)

    if store.vein_dir.exists() and not force:
        console.print(f"[yellow]Already initialized:[/] {store.vein_dir}")
        # Re-register so an existing repo joins cross-project recall.
        if registry.register(cwd):
            console.print("[dim]Registered for cross-project recall.[/]")
        console.print("Use [bold]--force[/] to re-create.")
        return

    created = store.init(name=project_name, force=force)
    registry.register(cwd)

    if created:
        console.print(Panel(
            f"[bold green]✓ Initialized .vein/ for [cyan]{project_name}[/][/]\n\n"
            f"  [dim]{store.vein_dir}[/]\n\n"
            f"  Next steps:\n"
            f"    [bold]vein log decision[/] \"why we chose X over Y\"\n"
            f"    [bold]vein status[/]\n"
            f"    [bold]vein brief[/]",
            border_style="green",
            title="vein init",
        ))
    else:
        console.print(f"[yellow]Nothing to do.[/]")
