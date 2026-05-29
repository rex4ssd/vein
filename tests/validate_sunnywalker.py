#!/usr/bin/env python3
"""
validate_sunnywalker.py — end-to-end validation for sunnywalker workflow engine.

Usage:
    python tests/validate_sunnywalker.py
    python tests/validate_sunnywalker.py 2>&1 | tee validate_sunnywalker.log

Covers:
  - WorkflowRunner: pass/fail routing, goto, retry, skip
  - WalkerState: persistence, retries_for
  - StepDef: from_dict
  - CLI: vein walk init / status / step / reset / run --dry-run

No pytest required. No ollama required.
"""

import subprocess
import sys
import tempfile
import textwrap
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

VEIN_CMD = [sys.executable, "-m", "vein"]

_results: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    try:
        fn()
        _results.append((name, True, ""))
        print(f"  [ PASS ]  {name}")
    except Exception as e:
        lines = str(e).splitlines()
        msg = (lines[0] if lines else repr(e))[:120]
        _results.append((name, False, msg))
        print(f"  [ FAIL ]  {name}")
        print(f"            {msg}")


def cli(*args, cwd=None, input_text=None, expect_ok=True) -> subprocess.CompletedProcess:
    r = subprocess.run(
        VEIN_CMD + list(args),
        cwd=cwd, capture_output=True, text=True, input=input_text,
    )
    if expect_ok and r.returncode != 0:
        raise AssertionError(
            f"exit {r.returncode}\nstdout: {r.stdout[-300:]}\nstderr: {r.stderr[-300:]}"
        )
    return r


def section(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ── Section 1: StepDef + WalkerState ─────────────────────────────

section("1. StepDef + WalkerState")

def t_stepdef_from_dict():
    from vein.core.workflow import StepDef
    d = {"id": "code", "name": "Coding", "run": "shell/a.sh",
         "on_pass": "next", "on_fail": "stop", "max_retries": 2}
    s = StepDef.from_dict(d)
    assert s.id == "code"
    assert s.name == "Coding"
    assert s.max_retries == 2

def t_stepdef_defaults():
    from vein.core.workflow import StepDef
    s = StepDef(id="x", name="X")
    assert s.on_pass == "next"
    assert s.on_fail == "stop"
    assert s.human_step is False
    assert s.timeout == 300

def t_walkerstate_append_retries():
    from vein.core.workflow import WalkerState, StepRun
    state = WalkerState(workflow_name="test")
    state.append(StepRun(step_id="code", status="fail"))
    state.append(StepRun(step_id="code", status="fail"))
    state.append(StepRun(step_id="code", status="fail"))
    assert state.retries_for("code") == 3

def t_walkerstate_retries_reset_on_different_step():
    from vein.core.workflow import WalkerState, StepRun
    state = WalkerState(workflow_name="test")
    state.append(StepRun(step_id="code", status="fail"))
    state.append(StepRun(step_id="validate", status="fail"))
    # "code" retry streak at tail = 0 (validate is last)
    assert state.retries_for("code") == 0
    assert state.retries_for("validate") == 1

def t_walkerstate_json_roundtrip():
    from vein.core.workflow import WalkerState, StepRun
    state = WalkerState(workflow_name="myapp", cycle=3)
    state.append(StepRun(step_id="code", status="pass"))
    state.append(StepRun(step_id="validate", status="fail", exit_code=1))
    state.current_step_id = "validate"
    state.status = "running"
    j = state.to_json()
    loaded = WalkerState.from_json(j)
    assert loaded.workflow_name == "myapp"
    assert loaded.cycle == 3
    assert len(loaded.history) == 2
    assert loaded.history[1]["exit_code"] == 1

check("StepDef.from_dict", t_stepdef_from_dict)
check("StepDef defaults", t_stepdef_defaults)
check("WalkerState.retries_for counts tail streak", t_walkerstate_append_retries)
check("WalkerState.retries_for resets on different step", t_walkerstate_retries_reset_on_different_step)
check("WalkerState JSON roundtrip", t_walkerstate_json_roundtrip)


# ── Section 2: WorkflowRunner routing ────────────────────────────

section("2. WorkflowRunner routing logic")

def _make_scripts(tmp: Path, step_exits: dict[str, int]) -> dict[str, Path]:
    """Create tiny shell scripts that exit with configured codes."""
    scripts = {}
    for step_id, code in step_exits.items():
        p = tmp / f"{step_id}.sh"
        p.write_text(f"#!/bin/sh\nexit {code}\n", encoding="utf-8")
        p.chmod(0o755)
        scripts[step_id] = p
    return scripts


def _make_runner(tmp: Path, steps_yaml: list[dict], step_exits: dict[str, int]):
    from vein.core.workflow import StepDef, WalkerState, WorkflowRunner
    from vein.core.store import VeinStore

    scripts = _make_scripts(tmp, step_exits)
    # patch run paths to use tmp scripts
    for s in steps_yaml:
        if s.get("run") and s["id"] in step_exits:
            s["run"] = str(scripts[s["id"]])

    steps = [StepDef.from_dict(s) for s in steps_yaml]
    vein_dir = tmp / ".vein"
    vein_dir.mkdir(exist_ok=True)
    state = WalkerState(workflow_name="test")

    runner = WorkflowRunner(
        steps=steps,
        state=state,
        project_root=tmp,
        vein_dir=vein_dir,
        dry_run=False,
        console=None,
    )
    return runner, state


def t_runner_all_pass():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        runner, state = _make_runner(tmp, [
            {"id": "a", "name": "A", "run": "a.sh", "on_pass": "next", "on_fail": "stop"},
            {"id": "b", "name": "B", "run": "b.sh", "on_pass": "next", "on_fail": "stop"},
            {"id": "c", "name": "C", "run": "c.sh", "on_pass": "done", "on_fail": "stop"},
        ], {"a": 0, "b": 0, "c": 0})
        ok = runner.run()
        assert ok is True
        assert state.status == "done"
        statuses = [r["status"] for r in state.history]
        assert statuses == ["pass", "pass", "pass"]

def t_runner_on_fail_stop():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        runner, state = _make_runner(tmp, [
            {"id": "a", "name": "A", "run": "a.sh", "on_pass": "next", "on_fail": "stop"},
            {"id": "b", "name": "B", "run": "b.sh", "on_pass": "done", "on_fail": "stop"},
        ], {"a": 1, "b": 0})  # a fails
        ok = runner.run()
        assert ok is False
        assert state.status == "failed"

def t_runner_on_fail_skip():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        runner, state = _make_runner(tmp, [
            {"id": "a", "name": "A", "run": "a.sh", "on_pass": "next", "on_fail": "skip"},
            {"id": "b", "name": "B", "run": "b.sh", "on_pass": "done", "on_fail": "stop"},
        ], {"a": 1, "b": 0})  # a fails → skip → b runs
        ok = runner.run()
        assert ok is True
        statuses = [r["status"] for r in state.history]
        assert "fail" in statuses
        assert "pass" in statuses

def t_runner_on_fail_goto():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        # b fails first time → goto a → then both pass
        call_counts = {"a": 0, "b": 0}
        p_a = tmp / "a.sh"
        p_b = tmp / "b.sh"

        # a always passes; b fails on first call, passes on second
        p_a.write_text("#!/bin/sh\nexit 0\n"); p_a.chmod(0o755)
        # b: use a counter file
        counter = tmp / "b_counter.txt"
        counter.write_text("0")
        p_b.write_text(
            f"#!/bin/sh\n"
            f"n=$(cat {counter})\n"
            f"echo $((n+1)) > {counter}\n"
            f"[ $n -ge 1 ] && exit 0 || exit 1\n"
        )
        p_b.chmod(0o755)

        from vein.core.workflow import StepDef, WalkerState, WorkflowRunner
        steps = [
            StepDef(id="a", name="A", run=str(p_a), on_pass="next", on_fail="stop"),
            StepDef(id="b", name="B", run=str(p_b), on_pass="done", on_fail="goto:a",
                    max_retries=5),
        ]
        vein_dir = tmp / ".vein"; vein_dir.mkdir(exist_ok=True)
        state = WalkerState(workflow_name="test")
        runner = WorkflowRunner(steps=steps, state=state,
                                project_root=tmp, vein_dir=vein_dir)
        ok = runner.run()
        assert ok is True
        # history should have: a-pass, b-fail, a-pass, b-pass
        step_ids = [r["step_id"] for r in state.history]
        assert step_ids.count("b") >= 2
        assert step_ids[-1] == "b"
        assert state.history[-1]["status"] == "pass"

def t_runner_retry_exhausted():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        runner, state = _make_runner(tmp, [
            {"id": "a", "name": "A", "run": "a.sh",
             "on_pass": "done", "on_fail": "retry:2", "max_retries": 2},
        ], {"a": 1})  # always fails
        ok = runner.run()
        assert ok is False
        # should have tried: original + 2 retries = 3 total
        assert len([r for r in state.history if r["step_id"] == "a"]) >= 2

def t_runner_dry_run():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        # dry_run: human_step should auto-pass
        from vein.core.workflow import StepDef, WalkerState, WorkflowRunner
        steps = [
            StepDef(id="code", name="Code", human_step=True, on_pass="next", on_fail="stop"),
            StepDef(id="done_step", name="Done", on_pass="done", on_fail="stop"),
        ]
        vein_dir = tmp / ".vein"; vein_dir.mkdir(exist_ok=True)
        state = WalkerState(workflow_name="test")
        runner = WorkflowRunner(steps=steps, state=state,
                                project_root=tmp, vein_dir=vein_dir, dry_run=True)
        ok = runner.run()
        assert ok is True

check("runner: all pass → status=done", t_runner_all_pass)
check("runner: on_fail=stop → status=failed", t_runner_on_fail_stop)
check("runner: on_fail=skip → skips to next", t_runner_on_fail_skip)
check("runner: on_fail=goto → loops back", t_runner_on_fail_goto)
check("runner: retry exhausted → stop", t_runner_retry_exhausted)
check("runner: dry_run (human_step auto-pass)", t_runner_dry_run)


# ── Section 3: load_workflow (YAML parse) ─────────────────────────

section("3. load_workflow (YAML parse)")

_SAMPLE_YAML = textwrap.dedent("""\
    name: my-feature
    version: 1
    steps:
      - id: code
        name: "AI Coding"
        human_step: true
        on_pass: next
        on_fail: stop

      - id: validate
        name: "Validation"
        run: shell/sunnywalker/b_validate.sh
        on_pass: next
        on_fail: "goto:code"
        max_retries: 3

      - id: commit
        name: "Git Commit"
        run: shell/sunnywalker/e_ca.sh
        on_pass: done
        on_fail: stop
""")

def t_load_workflow_parses():
    from vein.core.workflow import load_workflow
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "sunnywalker.yaml"
        p.write_text(_SAMPLE_YAML, encoding="utf-8")
        name, steps = load_workflow(p)
        assert name == "my-feature"
        assert len(steps) == 3
        assert steps[0].id == "code"
        assert steps[0].human_step is True
        assert steps[1].id == "validate"
        assert steps[1].on_fail == "goto:code"
        assert steps[1].max_retries == 3
        assert steps[2].on_pass == "done"

def t_load_workflow_defaults_filled():
    from vein.core.workflow import load_workflow
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "sw.yaml"
        p.write_text("name: test\nsteps:\n  - id: a\n    name: A\n", encoding="utf-8")
        _, steps = load_workflow(p)
        assert steps[0].on_pass == "next"
        assert steps[0].on_fail == "stop"
        assert steps[0].timeout == 300

check("load_workflow: 3-step YAML parses correctly", t_load_workflow_parses)
check("load_workflow: missing fields get defaults", t_load_workflow_defaults_filled)


# ── Section 4: CLI vein walk ──────────────────────────────────────

section("4. CLI: vein walk init / status / step / reset / run --dry-run")

def t_walk_init():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        r = cli("walk", "init", "--name", "feature-x", cwd=tmp)
        assert "sunnywalker initialized" in r.stdout or "sunnywalker.yaml" in r.stdout
        assert (Path(tmp) / "sunnywalker.yaml").exists()
        assert (Path(tmp) / "shell" / "sunnywalker" / "b_validate.sh").exists()
        assert (Path(tmp) / "shell" / "sunnywalker" / "c_report.py").exists()
        assert (Path(tmp) / "shell" / "sunnywalker" / "d_review.py").exists()
        assert (Path(tmp) / "shell" / "sunnywalker" / "e_ca.sh").exists()

def t_walk_init_all_templates():
    for template in ("default", "python", "rust", "tauri"):
        with tempfile.TemporaryDirectory() as tmp:
            cli("init", "test", cwd=tmp)
            r = cli("walk", "init", "--template", template, cwd=tmp)
            assert (Path(tmp) / "sunnywalker.yaml").exists(), f"missing yaml for {template}"
            assert (Path(tmp) / "shell" / "sunnywalker" / "b_validate.sh").exists()

def t_walk_status_no_workflow():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        r = cli("walk", "status", cwd=tmp)
        assert "No active workflow" in r.stdout or "walk run" in r.stdout

def t_walk_step_manual():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        cli("walk", "init", cwd=tmp)
        # manually mark code as pass
        r = cli("walk", "step", "code", "pass", cwd=tmp)
        assert r.returncode == 0, f"exit {r.returncode}: {r.stderr}"
        # check state was written
        assert (Path(tmp) / ".vein" / "WALKER.json").exists(), "WALKER.json not created"

def t_walk_status_after_step():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        cli("walk", "init", cwd=tmp)
        cli("walk", "step", "code", "pass", cwd=tmp)
        r = cli("walk", "status", cwd=tmp)
        assert "code" in r.stdout
        assert "pass" in r.stdout

def t_walk_reset():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        cli("walk", "init", cwd=tmp)
        cli("walk", "step", "code", "pass", cwd=tmp)
        assert (Path(tmp) / ".vein" / "WALKER.json").exists()
        cli("walk", "reset", "--yes", cwd=tmp)
        assert not (Path(tmp) / ".vein" / "WALKER.json").exists()

def t_walk_run_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        cli("walk", "init", cwd=tmp)
        # dry-run: human_step auto-passes, scripts don't actually run
        r = subprocess.run(
            VEIN_CMD + ["walk", "run", "--dry-run"],
            cwd=tmp,
            capture_output=True,
            text=True,
            input="\n\n\n\n",    # answer Enter for human_step prompts
            timeout=15,
        )
        # dry-run may complete or stop at human_step
        combined = r.stdout + r.stderr
        assert "sunnywalker" in combined.lower() or "dry" in combined.lower() or "cycle" in combined.lower()

def t_walk_gitignore_has_walker():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        gitignore = Path(tmp) / ".vein" / ".gitignore"
        content = gitignore.read_text(encoding="utf-8")
        assert "WALKER.json" in content

check("walk init: creates yaml + 4 scripts", t_walk_init)
check("walk init: all 4 templates work", t_walk_init_all_templates)
check("walk status: no workflow → helpful message", t_walk_status_no_workflow)
check("walk step code pass → writes WALKER.json", t_walk_step_manual)
check("walk status: after step shows history", t_walk_status_after_step)
check("walk reset --yes → removes WALKER.json", t_walk_reset)
check("walk run --dry-run → no crash", t_walk_run_dry_run)
check("walk: .vein/.gitignore has WALKER.json", t_walk_gitignore_has_walker)


# ── Summary ───────────────────────────────────────────────────────

total  = len(_results)
passed = sum(1 for _, ok, _ in _results if ok)
failed = total - passed

print(f"\n{'═'*60}")
print(f"  Results: {passed} passed, {failed} failed  (total {total})")
print(f"{'═'*60}")

if failed:
    print("\nFailed items:")
    for name, ok, msg in _results:
        if not ok:
            print(f"  ✗  {name}")
            if msg:
                print(f"       {msg}")
    sys.exit(1)
else:
    print("\n  ✓ All validations passed.\n")
    sys.exit(0)
