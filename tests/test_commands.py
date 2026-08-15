"""Regression tests for the command-layer review pass.

Theme, again: commands that reported success while doing nothing, or filtered
in the wrong order and reported "no results" over a store full of matches.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from click.testing import CliRunner

from vein.commands.gc import cmd_gc
from vein.commands.hooks import _find_git_dir
from vein.commands.list_cmd import cmd_list
from vein.core.models import Entry
from vein.core.store import VeinStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = VeinStore(tmp_path)
    s.init("test-project")
    monkeypatch.chdir(tmp_path)
    return s


def _add(store, type_="lore", title="t", tags=None, **fm):
    e = Entry.make(type=type_, title=title, tags=tags or [])
    for k, v in fm.items():
        setattr(e, k, v)
    store.write_entry(e, auto_index=False)
    return e


# ── list: filter before limit ─────────────────────────────────────

def test_list_tag_filter_is_not_capped_by_the_limit(store):
    """`limit` used to be applied inside list_entries, so --tag showed only the
    tagged entries that happened to fall in the newest N overall."""
    for i in range(8):
        _add(store, title=f"untagged {i}")
    for i in range(3):
        _add(store, title=f"tagged {i}", tags=["dma"])

    r = CliRunner().invoke(cmd_list, ["--tag", "dma", "--limit", "5", "--ids-only"])
    assert r.exit_code == 0
    assert len([ln for ln in r.output.splitlines() if ln.strip()]) == 3


def test_list_status_choices_match_the_real_statuses(store):
    """--status archived was offered but never written by anything; --status
    resolved was a real status missing from the choices."""
    _add(store, title="done", status="resolved")
    r = CliRunner().invoke(cmd_list, ["--status", "resolved", "--ids-only"])
    assert r.exit_code == 0 and "done" not in r.output  # ids-only prints ids
    assert r.output.strip()

    assert CliRunner().invoke(cmd_list, ["--status", "archived"]).exit_code != 0


# ── gc ────────────────────────────────────────────────────────────

def test_gc_accepts_type_as_a_standalone_filter(store):
    """`vein gc --type reference` told the user to pass the flag they passed."""
    _add(store, type_="reference", title="r")
    r = CliRunner().invoke(cmd_gc, ["--type", "reference", "--dry-run"])
    assert "Nothing to do" not in r.output


def test_gc_older_than_respects_verified_at(store):
    """effective_date is `verified_at or date`. Filtering on raw capture time
    deleted entries the user re-verified last week."""
    old = datetime.now(timezone.utc) - timedelta(days=400)
    _add(store, title="old but re-verified", date=old,
         verified_at=datetime.now(timezone.utc))
    _add(store, title="genuinely old", date=old)

    r = CliRunner().invoke(cmd_gc, ["--older-than", "90", "--dry-run"])
    assert "genuinely old" in r.output
    assert "old but re-verified" not in r.output


# ── hooks ─────────────────────────────────────────────────────────

def test_find_git_dir_follows_a_gitdir_file(tmp_path):
    """Worktrees, submodules and --separate-git-dir put a *file* at .git.
    Requiring a directory walked past them into the enclosing superproject."""
    real = tmp_path / "real.git"
    real.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    (work / ".git").write_text(f"gitdir: {real}\n", encoding="utf-8")
    assert _find_git_dir(work) == real


def test_find_git_dir_handles_relative_gitdir(tmp_path):
    real = tmp_path / "real.git"
    real.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    (work / ".git").write_text("gitdir: ../real.git\n", encoding="utf-8")
    assert _find_git_dir(work) == real.resolve()


# ── debrief: stdin must not shadow the git fallback ───────────────

def test_debrief_falls_back_to_git_when_stdin_is_empty(store, monkeypatch):
    """Git runs hooks with stdin on /dev/null, so isatty() is False and the
    old if/else read "" and returned — the installed post-commit hook has
    never captured anything, silently, on every commit."""
    import io

    from vein.commands import debrief as mod

    monkeypatch.setattr("sys.stdin", io.StringIO(""))   # not a tty, no content
    called = {}
    monkeypatch.setattr(mod, "_get_diff", lambda since: called.setdefault("since", since) or "")

    CliRunner().invoke(mod.cmd_debrief, ["--since", "HEAD~3"])
    assert called.get("since") == "HEAD~3"


def test_debrief_prefers_piped_stdin(store, monkeypatch):
    """`git diff | vein debrief` must still win over the git fallback."""
    from vein.commands import debrief as mod

    monkeypatch.setattr(
        mod, "_get_diff", lambda since: pytest.fail("should not have reached git")
    )
    seen = {}
    monkeypatch.setattr(
        mod, "_call_ollama_debrief",
        lambda diff, **k: seen.setdefault("diff", diff) and None,
    )
    r = CliRunner().invoke(mod.cmd_debrief, [], input="diff --git a/x b/x\n+real\n")
    assert r.exit_code == 0
    assert "+real" in seen["diff"]
