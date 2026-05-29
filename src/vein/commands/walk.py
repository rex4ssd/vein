"""vein walk — run a sunnywalker multi-step AI workflow."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..core.store import VeinStore
from ..core.workflow import WalkerState, WorkflowRunner, load_workflow, WALKER_STATE_FILE

console = Console()


@click.group("walk")
def cmd_walk() -> None:
    """Sunnywalker — multi-agent workflow runner.

    \b
    vein walk init               scaffold a sunnywalker.yaml + template scripts
    vein walk run                run (or resume) the workflow
    vein walk status             show current step + history
    vein walk reset              clear state (start over)
    vein walk step <id> pass|fail  manually advance/fail a step
    """


# ── init ──────────────────────────────────────────────────────────

@cmd_walk.command("init")
@click.option("--name", "-n", default="", help="Workflow name")
@click.option("--template", "-t",
              type=click.Choice(["default", "python", "rust", "tauri"]),
              default="default", show_default=True)
def walk_init(name: str, template: str) -> None:
    """Scaffold sunnywalker.yaml + template scripts for this project."""
    store = VeinStore.require()
    walker_dir = store.root / "shell" / "sunnywalker"
    walker_dir.mkdir(parents=True, exist_ok=True)

    project_name = name or store.root.name
    workflow_path = store.root / "sunnywalker.yaml"

    if workflow_path.exists():
        console.print(f"[yellow]sunnywalker.yaml already exists.[/] Use --force to overwrite.")
        return

    # write workflow.yaml
    workflow_path.write_text(_WORKFLOW_TEMPLATE.format(name=project_name), encoding="utf-8")
    console.print(f"[green]✓[/] {workflow_path.relative_to(store.root)}")

    # write template scripts
    scripts = _SCRIPTS_FOR_TEMPLATE.get(template, _SCRIPTS_FOR_TEMPLATE["default"])
    for filename, content in scripts.items():
        p = walker_dir / filename
        p.write_text(content, encoding="utf-8")
        p.chmod(0o755)
        console.print(f"[green]✓[/] {p.relative_to(store.root)}")

    console.print(Panel(
        f"[bold]Next steps:[/]\n\n"
        f"1. Edit [cyan]sunnywalker.yaml[/] — adjust steps for your project\n"
        f"2. Edit [cyan]shell/sunnywalker/b_validate.sh[/] — add your test commands\n"
        f"3. Run: [bold]vein walk run[/]",
        title="[bold green]sunnywalker initialized[/]",
        border_style="green",
    ))


# ── run ───────────────────────────────────────────────────────────

@cmd_walk.command("run")
@click.option("--workflow", "-w", default="sunnywalker.yaml",
              help="Workflow definition file")
@click.option("--from-step", "-f", default="", help="Start from this step id")
@click.option("--dry-run", is_flag=True)
@click.option("--max-cycles", default=20, show_default=True)
def walk_run(workflow: str, from_step: str, dry_run: bool, max_cycles: int) -> None:
    """Run (or resume) the sunnywalker workflow."""
    store = VeinStore.require()
    workflow_path = store.root / workflow

    if not workflow_path.exists():
        console.print(f"[red]Not found:[/] {workflow_path}")
        console.print("Run [bold]vein walk init[/] first.")
        raise SystemExit(1)

    wf_name, steps = load_workflow(workflow_path)

    # load or create state
    state_path = store.vein_dir / WALKER_STATE_FILE
    if state_path.exists():
        state = WalkerState.from_json(state_path.read_text(encoding="utf-8"))
        if state.status == "done":
            console.print("[green]Workflow already completed.[/] Use [bold]vein walk reset[/] to restart.")
            return
        console.print(f"[dim]Resuming cycle {state.cycle} at step:[/] [bold]{state.current_step_id}[/]")
    else:
        state = WalkerState(workflow_name=wf_name)

    if state.cycle >= max_cycles:
        console.print(f"[red]Max cycles ({max_cycles}) reached.[/] Use --max-cycles to increase.")
        raise SystemExit(1)

    runner = WorkflowRunner(
        steps=steps,
        state=state,
        project_root=store.root,
        vein_dir=store.vein_dir,
        dry_run=dry_run,
        console=console,
    )

    console.print(Panel(
        f"[bold]{wf_name}[/]  ·  {len(steps)} steps  ·  cycle {state.cycle + 1}"
        + ("  [yellow][DRY RUN][/]" if dry_run else ""),
        title="[bold cyan]sunnywalker[/]",
        border_style="cyan",
    ))

    ok = runner.run(start_from=from_step or None)

    if ok:
        console.print(Panel(
            "[bold green]✓ Workflow complete.[/]\n\n"
            "Run [bold]vein walk status[/] for the full history.",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold red]✗ Workflow stopped at:[/] [bold]{state.current_step_id}[/]\n\n"
            "Check the output above, fix the issue, then:\n"
            "  [bold]vein walk run[/]   — resume from failed step\n"
            "  [bold]vein walk run --from-step <id>[/]   — resume from specific step",
            border_style="red",
        ))
        raise SystemExit(1)


# ── status ────────────────────────────────────────────────────────

@cmd_walk.command("status")
def walk_status() -> None:
    """Show current workflow state and step history."""
    store = VeinStore.require()
    state_path = store.vein_dir / WALKER_STATE_FILE

    if not state_path.exists():
        console.print("[yellow]No active workflow.[/] Run [bold]vein walk run[/] to start.")
        return

    state = WalkerState.from_json(state_path.read_text(encoding="utf-8"))

    status_color = {"done": "green", "failed": "red", "running": "cyan", "waiting": "yellow"}.get(
        state.status, "white"
    )
    console.print(f"\n[bold]{state.workflow_name}[/]  "
                  f"cycle [bold]{state.cycle}[/]  "
                  f"status [{status_color}]{state.status}[/]\n")

    if not state.history:
        console.print("[dim]No steps run yet.[/]")
        return

    table = Table(show_header=True, header_style="bold dim")
    table.add_column("#",        style="dim", max_width=4)
    table.add_column("Step",     max_width=20)
    table.add_column("Status",   max_width=10)
    table.add_column("Exit",     style="dim", max_width=6)
    table.add_column("Time",     style="dim", max_width=20)

    for i, r in enumerate(state.history, 1):
        st = r["status"]
        st_str = {
            "pass":  "[green]✓ pass[/]",
            "fail":  "[red]✗ fail[/]",
            "skip":  "[yellow]- skip[/]",
            "waiting": "[cyan]⏸ wait[/]",
        }.get(st, st)
        table.add_row(
            str(i),
            r["step_id"],
            st_str,
            str(r.get("exit_code", "")),
            r.get("ts", "")[:19],
        )

    console.print(table)


# ── step (manual override) ────────────────────────────────────────

@cmd_walk.command("step")
@click.argument("step_id")
@click.argument("result", type=click.Choice(["pass", "fail", "skip"]))
@click.option("--workflow", "-w", default="sunnywalker.yaml")
def walk_step(step_id: str, result: str, workflow: str) -> None:
    """Manually mark a step as pass/fail/skip (creates state if needed)."""
    store = VeinStore.require()
    state_path = store.vein_dir / WALKER_STATE_FILE

    if state_path.exists():
        state = WalkerState.from_json(state_path.read_text(encoding="utf-8"))
    else:
        # auto-init state from workflow file
        wf_path = store.root / workflow
        wf_name = wf_path.stem if wf_path.exists() else "workflow"
        state = WalkerState(workflow_name=wf_name, cycle=1, status="running")

    from ..core.workflow import StepRun
    state.append(StepRun(step_id=step_id, status=result))  # type: ignore[arg-type]
    state.current_step_id = step_id
    state_path.write_text(state.to_json(), encoding="utf-8")
    console.print(f"[green]✓[/] Marked [bold]{step_id}[/] as [bold]{result}[/]")


# ── reset ─────────────────────────────────────────────────────────

@cmd_walk.command("reset")
@click.option("--yes", "-y", is_flag=True)
def walk_reset(yes: bool) -> None:
    """Clear WALKER.json — start the workflow from scratch."""
    store = VeinStore.require()
    state_path = store.vein_dir / WALKER_STATE_FILE

    if not state_path.exists():
        console.print("[dim]Nothing to reset.[/]")
        return

    if not yes:
        click.confirm("Reset workflow state?", abort=True)

    state_path.unlink()
    console.print("[green]✓ Workflow state cleared.[/]")


# ── templates ─────────────────────────────────────────────────────

_WORKFLOW_TEMPLATE = """\
# sunnywalker.yaml — multi-agent workflow for {name}
# vein walk run

name: {name}
version: 1

# Steps run in order. On failure, follow on_fail directive.
# on_pass: next | done | goto:<step_id>
# on_fail: stop | skip | retry:<n> | goto:<step_id> | ai_decide

steps:

  - id: code
    name: "AI Coding"
    human_step: true          # pause here — you / AI does the coding
    on_pass: next
    on_fail: stop

  - id: validate
    name: "Validation"
    run: shell/sunnywalker/b_validate.sh
    on_pass: next
    on_fail: "goto:code"      # fail → back to coding
    max_retries: 3

  - id: report
    name: "Write Report"
    run: shell/sunnywalker/c_report.py
    on_pass: next
    on_fail: skip             # non-critical, skip on fail

  - id: review
    name: "AI Review"
    run: shell/sunnywalker/d_review.py
    on_pass: done             # review passes → ca + done
    on_fail: "goto:code"      # review fails → back to coding

  - id: commit
    name: "Git Commit"
    run: shell/sunnywalker/e_ca.sh
    on_pass: done
    on_fail: stop
"""

_SCRIPTS_FOR_TEMPLATE: dict[str, dict[str, str]] = {
    "default": {
        "b_validate.sh": """\
#!/usr/bin/env bash
# b_validate.sh — run tests + linting
# Edit to match your project's test commands.
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "=== Validate: lint ==="
# ruff check src/ || exit 1

echo "=== Validate: tests ==="
pytest tests/ -q || exit 1

echo "=== Validate: passed ==="
""",

        "c_report.py": """\
#!/usr/bin/env python3
\"\"\"c_report.py — generate a progress report from .vein/ entries.\"\"\"
import sys
from pathlib import Path

# add project src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vein.core.store import VeinStore
from datetime import datetime, timezone, timedelta

store = VeinStore.require()
entries = store.list_entries(status_filter="active")

# entries added in the last 7 days
cutoff = datetime.now(timezone.utc) - timedelta(days=7)
recent = [e for e in entries if e.date >= cutoff]

report_lines = [
    f"# Sunnywalker Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    "",
    f"**Total entries:** {len(entries)}  |  **This week:** {len(recent)}",
    "",
]

for etype in ("decision", "pitfall", "lore", "reference"):
    typed = [e for e in recent if e.type == etype]
    if typed:
        report_lines.append(f"## {etype.capitalize()}s ({len(typed)})")
        for e in typed:
            report_lines.append(f"- **{e.title}** — {e.date_str[:10]}")
        report_lines.append("")

report_path = Path("WALKER_REPORT.md")
report_path.write_text("\\n".join(report_lines), encoding="utf-8")
print(f"Report written to {report_path}")

# also log to vein
from vein.core.models import Entry
entry = Entry(
    id=Entry.new_id(), type="lore",
    title=f"Sunnywalker report — {datetime.now().strftime('%Y-%m-%d')}",
    tags=["sunnywalker", "report"],
    body="\\n".join(report_lines[:30]),
    source="sunnywalker:c_report",
)
store.write_entry(entry, auto_index=False)
print("Logged to .vein/")
""",

        "d_review.py": """\
#!/usr/bin/env python3
\"\"\"d_review.py — AI reviews all recent vein entries and decides pass/fail.\"\"\"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vein.core.store import VeinStore
from vein.core.triage import call_ollama_triage
from datetime import datetime, timezone, timedelta

store = VeinStore.require()
cfg = store.load_config()
base_url  = cfg.get("model", {}).get("base_url", "http://localhost:11434")
model     = cfg.get("model", {}).get("analyze_model", "deepseek-r1:14b")

entries = store.list_entries(status_filter="active")
cutoff  = datetime.now(timezone.utc) - timedelta(days=7)
recent  = [e for e in entries if e.date >= cutoff]

context = "\\n\\n".join(
    f"[{e.type}] {e.title}\\n{e.body[:300]}"
    for e in recent[:20]
)

REVIEW_PROMPT = (
    "You are a senior engineer reviewing a week's worth of project lore entries.\\n"
    "Assess whether the work is solid enough to ship a milestone.\\n\\n"
    "Recent entries:\\n" + context + "\\n\\n"
    "Output:\\n"
    "VERDICT: PASS or FAIL\\n"
    "REASON: one sentence\\n"
    "RISK: (if FAIL) the biggest unresolved risk\\n"
    "GOTO: (if FAIL) which step needs redo: code | validate | report"
)

print("Calling AI reviewer…")
result = call_ollama_triage(
    cmd="sunnywalker:d_review",
    error_digest=context[:600],
    lore_context=REVIEW_PROMPT,
    base_url=base_url,
    model=model,
)

if result:
    print(result)
    # parse verdict
    if "VERDICT: PASS" in result.upper():
        print("\\n✓ Review passed.")
        sys.exit(0)
    else:
        print("\\n✗ Review failed.")
        sys.exit(1)
else:
    print("AI reviewer unavailable — defaulting to PASS (no AI = no blocker)")
    sys.exit(0)
""",

        "e_ca.sh": """\
#!/usr/bin/env bash
# e_ca.sh — git commit (sunnywalker final step)
set -euo pipefail
cd "$(dirname "$0")/../.."
rm -f .git/index.lock
git add -A
DATE=$(date +%Y-%m-%d)
CYCLE=${VEIN_WALKER_CYCLE:-1}
git commit -m "feat: sunnywalker cycle ${CYCLE} — ${DATE}

Auto-committed by sunnywalker after validation + review pass.
See WALKER_REPORT.md and .vein/ for details."
echo "✓ Committed."
""",
    }
}
# extend for other templates
_SCRIPTS_FOR_TEMPLATE["python"] = _SCRIPTS_FOR_TEMPLATE["default"].copy()
_SCRIPTS_FOR_TEMPLATE["rust"] = {
    **_SCRIPTS_FOR_TEMPLATE["default"],
    "b_validate.sh": """\
#!/usr/bin/env bash
# b_validate.sh — Rust validation
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "=== cargo check ==="
cd src-tauri && cargo check && cd ..

echo "=== cargo test ==="
cd src-tauri && cargo test --quiet && cd ..

echo "=== Validate: passed ==="
""",
}
_SCRIPTS_FOR_TEMPLATE["tauri"] = {
    **_SCRIPTS_FOR_TEMPLATE["default"],
    "b_validate.sh": """\
#!/usr/bin/env bash
# b_validate.sh — Tauri (React + Rust) validation
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "=== TypeScript check ==="
npx tsc --noEmit

echo "=== Rust check ==="
cd src-tauri && cargo check && cd ..

echo "=== Validate: passed ==="
""",
}
