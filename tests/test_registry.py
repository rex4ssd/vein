"""Tests for vein.core.registry + cross-project search."""

from __future__ import annotations

import pytest

from vein.core import registry
from vein.core.models import Entry
from vein.core.store import VeinStore, cross_project_search


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Point the registry at a throwaway dir so tests never touch the real one."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    yield


def _mkrepo(base, name) -> VeinStore:
    base.mkdir(parents=True, exist_ok=True)
    s = VeinStore(base)
    s.init(name=name)
    return s


def _pitfall(title, body="**Symptom:** x\n\n**Root cause:** y\n\n**Fix:** z", tags=None):
    return Entry(id=Entry.new_id(), type="pitfall", title=title,
                 tags=tags or ["test"], body=body)


# ── registry basics ───────────────────────────────────────────────

def test_register_and_roots(tmp_path):
    s = _mkrepo(tmp_path / "alpha", "alpha")
    registry.register(s.root)
    roots = registry.roots()
    assert s.root.resolve() in roots


def test_register_idempotent(tmp_path):
    s = _mkrepo(tmp_path / "alpha", "alpha")
    assert registry.register(s.root) is True
    assert registry.register(s.root) is False
    assert len(registry.roots()) == 1


def test_roots_drops_missing_vein(tmp_path):
    s = _mkrepo(tmp_path / "alpha", "alpha")
    registry.register(s.root)
    # register a path that has no .vein/
    registry.register(tmp_path / "ghost")
    roots = registry.roots()
    assert s.root.resolve() in roots
    assert (tmp_path / "ghost").resolve() not in roots


def test_init_auto_registers(tmp_path, monkeypatch):
    repo = tmp_path / "beta"
    repo.mkdir()
    monkeypatch.chdir(repo)
    from click.testing import CliRunner

    from vein.commands.init import cmd_init
    res = CliRunner().invoke(cmd_init, [])
    assert res.exit_code == 0
    assert repo.resolve() in registry.roots()


# ── cross-project search ──────────────────────────────────────────

def test_cross_project_finds_other_repo_lore(tmp_path):
    lode = _mkrepo(tmp_path / "lode", "lode")
    lode.write_entry(
        _pitfall("App Store rejects PNG with alpha channel", tags=["appstore", "cert"]),
        auto_index=False,
    )
    sunny = _mkrepo(tmp_path / "sunny", "sunnywalker")
    registry.register(lode.root)
    registry.register(sunny.root)

    # From sunny's perspective, search excludes sunny, finds lode's lore.
    hits = cross_project_search("app store alpha", exclude_root=sunny.root)
    assert len(hits) == 1
    project, entry, score = hits[0]
    assert project == "lode"
    assert "alpha channel" in entry.title.lower()


def test_cross_project_excludes_self(tmp_path):
    lode = _mkrepo(tmp_path / "lode", "lode")
    lode.write_entry(_pitfall("quarantine xattr reject"), auto_index=False)
    registry.register(lode.root)

    hits = cross_project_search("quarantine", exclude_root=lode.root)
    assert hits == []  # only repo is excluded → nothing
