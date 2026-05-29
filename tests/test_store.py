"""Tests for vein.core.store — VeinStore I/O."""

from __future__ import annotations

from pathlib import Path

import pytest

from vein.core.models import Entry
from vein.core.store import VeinStore


# ── fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path) -> VeinStore:
    s = VeinStore(tmp_path)
    s.init(name="test-project")
    return s


def _entry(type_="decision", title="Test entry", **kwargs) -> Entry:
    return Entry(
        id=Entry.new_id(),
        type=type_,
        title=title,
        tags=["test"],
        body="**Why:** testing\n\n**Trade-off:** none",
        **kwargs,
    )


# ── init ──────────────────────────────────────────────────────────

def test_init_creates_structure(tmp_path):
    s = VeinStore(tmp_path)
    created = s.init(name="myproject")
    assert created is True
    assert (tmp_path / ".vein").is_dir()
    assert (tmp_path / ".vein" / "decisions").is_dir()
    assert (tmp_path / ".vein" / "lore").is_dir()
    assert (tmp_path / ".vein" / "pitfalls").is_dir()
    assert (tmp_path / ".vein" / "references").is_dir()
    assert (tmp_path / ".vein" / "index").is_dir()
    assert (tmp_path / ".vein" / "config.yaml").is_file()
    assert (tmp_path / ".vein" / "STATUS.md").is_file()
    assert (tmp_path / ".vein" / ".gitignore").is_file()


def test_init_idempotent(tmp_path):
    s = VeinStore(tmp_path)
    s.init(name="p")
    result = s.init(name="p")
    assert result is False  # already exists, force=False


def test_init_force(tmp_path):
    s = VeinStore(tmp_path)
    s.init(name="p")
    result = s.init(name="p", force=True)
    assert result is True


# ── write / read ──────────────────────────────────────────────────

def test_write_read_roundtrip(store):
    e = _entry()
    path = store.write_entry(e, auto_index=False)
    assert path.exists()

    loaded = store.read_entry(e.id)
    assert loaded.id == e.id
    assert loaded.title == e.title


def test_write_all_types(store):
    for t in ("decision", "lore", "pitfall", "reference"):
        e = _entry(type_=t)
        store.write_entry(e, auto_index=False)

    all_entries = store.list_entries(status_filter=None)
    types_found = {e.type for e in all_entries}
    assert types_found == {"decision", "lore", "pitfall", "reference"}


def test_read_by_prefix(store):
    e = _entry()
    store.write_entry(e, auto_index=False)
    # read by first 8 chars of ID (date prefix)
    loaded = store.read_entry(e.id[:8])
    assert loaded.id == e.id


def test_read_not_found_raises(store):
    with pytest.raises(KeyError):
        store.read_entry("nonexistent-id-00000000")


# ── iter / list ───────────────────────────────────────────────────

def test_list_entries_type_filter(store):
    store.write_entry(_entry(type_="decision"), auto_index=False)
    store.write_entry(_entry(type_="pitfall"), auto_index=False)
    store.write_entry(_entry(type_="lore"), auto_index=False)

    decisions = store.list_entries(type_filter="decision")
    assert all(e.type == "decision" for e in decisions)
    assert len(decisions) == 1


def test_list_entries_status_filter(store):
    store.write_entry(_entry(status="active"), auto_index=False)
    store.write_entry(_entry(status="superseded"), auto_index=False)

    active = store.list_entries(status_filter="active")
    assert all(e.status == "active" for e in active)

    all_e = store.list_entries(status_filter=None)
    assert len(all_e) == 2


def test_list_entries_limit(store):
    for _ in range(5):
        store.write_entry(_entry(), auto_index=False)
    limited = store.list_entries(limit=3)
    assert len(limited) == 3


# ── stats ─────────────────────────────────────────────────────────

def test_stats(store):
    store.write_entry(_entry(type_="decision"), auto_index=False)
    store.write_entry(_entry(type_="pitfall"),  auto_index=False)

    s = store.stats()
    assert s["decision"] == 1
    assert s["pitfall"]  == 1
    assert s["lore"]     == 0
    assert s["reference"] == 0


# ── brief invalidation ────────────────────────────────────────────

def test_brief_invalidated_on_write(store):
    store.write_brief("cached content")
    assert (store.vein_dir / "BRIEF.md").exists()

    store.write_entry(_entry(), auto_index=False)
    assert not (store.vein_dir / "BRIEF.md").exists()


# ── grep_entries ──────────────────────────────────────────────────

def test_grep_returns_matches(store):
    e = _entry(title="DMA timeout pitfall")
    store.write_entry(e, auto_index=False)

    results = store.grep_entries("DMA")
    assert len(results) == 1
    assert results[0][0].id == e.id


def test_grep_case_insensitive(store):
    e = _entry(title="UART baud rate")
    store.write_entry(e, auto_index=False)
    results = store.grep_entries("uart")
    assert len(results) == 1


def test_grep_no_match(store):
    store.write_entry(_entry(title="memory leak"), auto_index=False)
    assert store.grep_entries("DMA") == []


# ── open_index ────────────────────────────────────────────────────

def test_open_index_creates_db(store):
    idx = store.open_index()
    assert idx is not None
    idx.close()
    assert (store.vein_dir / "index" / "vein.db").exists()


def test_fallback_index_path_is_deterministic_and_per_repo(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    s1 = VeinStore(tmp_path / "a")
    s1.init(name="a")
    s2 = VeinStore(tmp_path / "b")
    s2.init(name="b")
    assert s1._fallback_index_path() == s1._fallback_index_path()  # stable
    assert s1._fallback_index_path() != s2._fallback_index_path()  # per-repo
    assert s1._fallback_index_path().name == "vein.db"


def test_open_index_relocates_on_disk_io_error(store, monkeypatch):
    """Filesystems that can't host SQLite (network/FUSE/synced) must not crash
    reindex — open_index relocates the generated, gitignored index."""
    import sqlite3

    import vein.core.index as index_mod

    real_init = index_mod.VeinIndex.__init__
    repo_index_dir = store.vein_dir / "index"

    def fake_init(self, db_path):
        # Simulate fcntl-lock failure only for the in-repo path.
        if repo_index_dir in db_path.parents:
            raise sqlite3.OperationalError("disk I/O error")
        real_init(self, db_path)

    monkeypatch.setattr(index_mod.VeinIndex, "__init__", fake_init)

    idx = store.open_index()
    assert idx.relocated_to is not None
    assert repo_index_dir not in idx.relocated_to.parents
    assert idx.relocated_to.exists()
    idx.close()


# ── find / require ────────────────────────────────────────────────

def test_find_from_subdir(tmp_path):
    s = VeinStore(tmp_path)
    s.init(name="p")
    subdir = tmp_path / "src" / "deep"
    subdir.mkdir(parents=True)
    found = VeinStore.find(subdir)
    assert found is not None
    assert found.root == tmp_path


def test_find_returns_none_when_missing(tmp_path):
    assert VeinStore.find(tmp_path) is None


def test_require_raises_when_missing(tmp_path):
    with pytest.raises(RuntimeError, match="vein init"):
        VeinStore.require(tmp_path)
