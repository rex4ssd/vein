"""workflow.py — sunnywalker multi-agent workflow state machine.

Each workflow is a list of Steps. vein walk runs them in order,
persists state in .vein/WALKER.json, and routes on pass/fail.

Design principle: the workflow runner is dumb — it just runs scripts and
reads exit codes. The "AI" is in the scripts themselves (ollama calls, etc.).
Vein's role is shared memory between steps.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

WALKER_STATE_FILE = "WALKER.json"


# ── step definition ───────────────────────────────────────────────

OnFail = Literal["stop", "skip", "retry", "goto", "ai_decide"]
OnPass = Literal["next", "done", "goto"]


@dataclass
class StepDef:
    id: str
    name: str
    run: str | None = None          # script path (relative to project root)
    human_step: bool = False        # pause and wait for human/AI to signal done
    on_pass: str = "next"           # "next" | "done" | "goto:<step_id>"
    on_fail: str = "stop"           # "stop" | "skip" | "retry:<n>" | "goto:<step_id>" | "ai_decide"
    max_retries: int = 1
    timeout: int = 300              # seconds
    env: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "StepDef":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── run history entry ─────────────────────────────────────────────

@dataclass
class StepRun:
    step_id: str
    status: Literal["pass", "fail", "skip", "waiting"]
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    exit_code: int = 0
    output_tail: str = ""           # last 500 chars of stdout+stderr
    retry_count: int = 0


# ── walker state (persisted to .vein/WALKER.json) ─────────────────

@dataclass
class WalkerState:
    workflow_name: str
    cycle: int = 0
    current_step_id: str = ""
    status: Literal["running", "done", "failed", "waiting"] = "running"
    history: list[dict] = field(default_factory=list)

    def append(self, run: StepRun) -> None:
        self.history.append(asdict(run))

    def retries_for(self, step_id: str) -> int:
        """Count consecutive retries of step_id at end of history."""
        count = 0
        for r in reversed(self.history):
            if r["step_id"] == step_id:
                count += 1
            else:
                break
        return count

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "WalkerState":
        d = json.loads(text)
        obj = cls(workflow_name=d["workflow_name"])
        obj.__dict__.update(d)
        return obj


# ── workflow definition loader ────────────────────────────────────

def load_workflow(path: Path) -> tuple[str, list[StepDef]]:
    """Load sunnywalker.yaml. Returns (name, [StepDef, ...])."""
    import yaml
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    name = raw.get("name", path.stem)
    steps = [StepDef.from_dict(s) for s in raw.get("steps", [])]
    return name, steps


# ── runner ────────────────────────────────────────────────────────

class WorkflowRunner:
    def __init__(
        self,
        steps: list[StepDef],
        state: WalkerState,
        project_root: Path,
        vein_dir: Path,
        *,
        dry_run: bool = False,
        console=None,
    ):
        self.steps = steps
        self.step_map = {s.id: s for s in steps}
        self.state = state
        self.root = project_root
        self.vein_dir = vein_dir
        self.dry_run = dry_run
        self.console = console
        self._state_path = vein_dir / WALKER_STATE_FILE

    def _save_state(self) -> None:
        self._state_path.write_text(self.state.to_json(), encoding="utf-8")

    def _step_index(self, step_id: str) -> int:
        for i, s in enumerate(self.steps):
            if s.id == step_id:
                return i
        raise KeyError(f"Unknown step: {step_id}")

    def _current_index(self) -> int:
        if not self.state.current_step_id:
            return 0
        try:
            return self._step_index(self.state.current_step_id)
        except KeyError:
            return 0

    def _run_script(self, step: StepDef) -> tuple[int, str]:
        """Run the step script. Returns (exit_code, output_tail)."""
        if not step.run:
            return 0, ""

        script_path = self.root / step.run
        if not script_path.exists():
            return 2, f"script not found: {script_path}"

        # determine runner
        if step.run.endswith(".sh"):
            cmd = ["bash", str(script_path)]
        elif step.run.endswith(".py"):
            cmd = [sys.executable, str(script_path)]
        else:
            cmd = [str(script_path)]

        env = {
            **__import__("os").environ,
            "VEIN_WALKER_STEP": step.id,
            "VEIN_WALKER_CYCLE": str(self.state.cycle),
            "VEIN_PROJECT_ROOT": str(self.root),
            **step.env,
        }

        if self.dry_run:
            return 0, f"[dry-run] would run: {' '.join(cmd)}"

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.root),
                env=env,
                capture_output=False,   # let output stream to terminal
                timeout=step.timeout,
            )
            # re-capture tail for state log
            result2 = subprocess.run(
                cmd, cwd=str(self.root), env=env,
                capture_output=True, text=True, timeout=step.timeout,
            )
            tail = (result2.stdout + result2.stderr)[-500:]
            return result.returncode, tail
        except subprocess.TimeoutExpired:
            return 1, f"timeout after {step.timeout}s"
        except Exception as e:
            return 1, str(e)

    def _resolve_on_fail(self, step: StepDef, output_tail: str) -> str | None:
        """
        Resolve on_fail directive.
        Returns next step_id, or None = stop.
        """
        directive = step.on_fail  # e.g. "stop" | "skip" | "retry:3" | "goto:code" | "ai_decide"

        if directive == "stop":
            return None

        if directive == "skip":
            idx = self._step_index(step.id)
            if idx + 1 < len(self.steps):
                return self.steps[idx + 1].id
            return None

        if directive.startswith("retry"):
            max_r = int(directive.split(":")[1]) if ":" in directive else step.max_retries
            done = self.state.retries_for(step.id)
            if done < max_r:
                return step.id   # retry same step
            return None          # exhausted retries → stop

        if directive.startswith("goto:"):
            return directive.split(":", 1)[1]

        if directive == "ai_decide":
            return self._ai_decide(step, output_tail)

        return None

    def _ai_decide(self, failed_step: StepDef, output_tail: str) -> str | None:
        """Call ollama to decide which step to retry after a failure."""
        from .triage import call_ollama_triage

        step_list = "\n".join(f"  - {s.id}: {s.name}" for s in self.steps)
        prompt = (
            f"Workflow step '{failed_step.id}' ({failed_step.name}) failed.\n\n"
            f"Error tail:\n```\n{output_tail[-400:]}\n```\n\n"
            f"Available steps:\n{step_list}\n\n"
            f"Which step should we retry? Reply with ONLY the step id (one word). "
            f"If the workflow should stop entirely, reply 'stop'."
        )

        result = call_ollama_triage(
            cmd=f"workflow step: {failed_step.id}",
            error_digest=output_tail[-400:],
            lore_context=prompt,
        )
        if not result:
            return None

        # parse first word
        word = result.strip().splitlines()[0].strip().lower().split()[0]
        if word == "stop":
            return None
        if word in self.step_map:
            return word
        return None

    def run(self, start_from: str | None = None) -> bool:
        """
        Run the workflow from start_from (or current state).
        Returns True if completed successfully.
        """
        self.state.cycle += 1
        self.state.status = "running"

        start_idx = 0
        if start_from:
            try:
                start_idx = self._step_index(start_from)
            except KeyError:
                pass
        elif self.state.current_step_id:
            try:
                start_idx = self._current_index()
            except KeyError:
                pass

        idx = start_idx

        while idx < len(self.steps):
            step = self.steps[idx]
            self.state.current_step_id = step.id
            self._save_state()

            self._print(f"\n[bold cyan]▶ [{idx+1}/{len(self.steps)}][/]  "
                        f"[bold]{step.name}[/]  [dim]({step.id})[/]")

            # human step: pause and wait
            if step.human_step:
                self._print(
                    f"[yellow]⏸  Human/AI step — do the work, then press Enter to continue[/]"
                    f"  [dim](or type 'skip' to skip, 'fail' to mark failed)[/]"
                )
                if not self.dry_run:
                    ans = input().strip().lower()
                    if ans == "skip":
                        self.state.append(StepRun(step_id=step.id, status="skip"))
                        idx += 1
                        continue
                    elif ans == "fail":
                        self.state.append(StepRun(step_id=step.id, status="fail"))
                        next_id = self._resolve_on_fail(step, "")
                        if next_id is None:
                            self.state.status = "failed"
                            self._save_state()
                            return False
                        try:
                            idx = self._step_index(next_id)
                        except KeyError:
                            self.state.status = "failed"
                            self._save_state()
                            return False
                        continue
                self.state.append(StepRun(step_id=step.id, status="pass"))
                self._print(f"[green]✓ done[/]")
                idx += 1
                continue

            # script step
            if step.run:
                exit_code, output_tail = self._run_script(step)
            else:
                exit_code, output_tail = 0, ""

            if exit_code == 0:
                self.state.append(StepRun(
                    step_id=step.id, status="pass",
                    exit_code=exit_code, output_tail=output_tail,
                ))
                self._print(f"[green]✓ passed[/]")

                # on_pass routing
                on_pass = step.on_pass
                if on_pass == "done" or on_pass.startswith("goto:done"):
                    self.state.status = "done"
                    self._save_state()
                    return True
                elif on_pass.startswith("goto:"):
                    next_id = on_pass.split(":", 1)[1]
                    try:
                        idx = self._step_index(next_id)
                    except KeyError:
                        idx += 1
                else:
                    idx += 1  # "next"
            else:
                self.state.append(StepRun(
                    step_id=step.id, status="fail",
                    exit_code=exit_code, output_tail=output_tail,
                ))
                self._print(f"[red]✗ failed (exit {exit_code})[/]")

                next_id = self._resolve_on_fail(step, output_tail)
                if next_id is None:
                    self.state.status = "failed"
                    self._save_state()
                    return False
                elif next_id == step.id:
                    self._print(f"[yellow]↻ retrying {step.id}[/]")
                    # idx stays same
                else:
                    self._print(f"[yellow]↩ goto {next_id}[/]")
                    try:
                        idx = self._step_index(next_id)
                    except KeyError:
                        self.state.status = "failed"
                        self._save_state()
                        return False
                continue

        self.state.status = "done"
        self._save_state()
        return True

    def _print(self, msg: str) -> None:
        if self.console:
            self.console.print(msg)
        else:
            print(msg)
