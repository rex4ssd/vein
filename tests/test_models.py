"""Tests for vein.core.models."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from vein.core.models import Entry, EntryType


# ── Entry.new_id ──────────────────────────────────────────────────

def test_new_id_format():
    eid = Entry.new_id()
    assert re.match(r"^\d{8}-\d{6}-[0-9a-f]{4}$", eid), f"bad id: {eid}"


def test_new_id_unique():
    ids = {Entry.new_id() for _ in range(20)}
    assert len(ids) == 20  # all unique


# ── Entry.to_file_content / from_file roundtrip ───────────────────

def _make_entry(**kwargs) -> Entry:
    defaults = dict(
        id=Entry.new_id(),
        type="decision",
        title="Use callback not polling",
        tags=["dma", "hal", "systemc"],
        body="**Why:** event-driven model\n\n**Trade-off:** ISR discipline needed",
    )
    defaults.update(kwargs)
    return Entry(**defaults)


def test_roundtrip_basic(tmp_path):
    entry = _make_entry()
    path = tmp_path / f"{entry.id}.md"
    path.write_text(entry.to_file_content(), encoding="utf-8")

    loaded = Entry.from_file(path)
    assert loaded.id    == entry.id
    assert loaded.type  == entry.type
    assert loaded.title == entry.title
    assert loaded.tags  == entry.tags
    assert loaded.body.strip() == entry.body.strip()


def test_roundtrip_all_types(tmp_path):
    for etype in ("decision", "lore", "pitfall", "reference"):
        entry = _make_entry(type=etype, id=Entry.new_id())
        path = tmp_path / f"{entry.id}.md"
        path.write_text(entry.to_file_content(), encoding="utf-8")
        loaded = Entry.from_file(path)
        assert loaded.type == etype


def test_roundtrip_empty_tags(tmp_path):
    entry = _make_entry(tags=[])
    path = tmp_path / f"{entry.id}.md"
    path.write_text(entry.to_file_content(), encoding="utf-8")
    loaded = Entry.from_file(path)
    assert loaded.tags == []


def test_roundtrip_unicode_title(tmp_path):
    entry = _make_entry(title="DMA 中斷 callback — 不 polling")
    path = tmp_path / f"{entry.id}.md"
    path.write_text(entry.to_file_content(), encoding="utf-8")
    loaded = Entry.from_file(path)
    assert loaded.title == "DMA 中斷 callback — 不 polling"


def test_roundtrip_related(tmp_path):
    entry = _make_entry(related=["20260101-000000-abcd", "20260102-000000-ef01"])
    path = tmp_path / f"{entry.id}.md"
    path.write_text(entry.to_file_content(), encoding="utf-8")
    loaded = Entry.from_file(path)
    assert "20260101-000000-abcd" in loaded.related


def test_roundtrip_status_superseded(tmp_path):
    entry = _make_entry(status="superseded", superseded_by="20260601-000000-aabb")
    path = tmp_path / f"{entry.id}.md"
    path.write_text(entry.to_file_content(), encoding="utf-8")
    loaded = Entry.from_file(path)
    assert loaded.status == "superseded"
    assert loaded.superseded_by == "20260601-000000-aabb"


# ── body_section ──────────────────────────────────────────────────

def test_body_section_found():
    entry = _make_entry(body="**Why:** event-driven\n\n**Trade-off:** ISR discipline")
    assert "event-driven" in entry.body_section("Why")


def test_body_section_missing():
    entry = _make_entry(body="**Why:** event-driven")
    assert entry.body_section("NonExistent") == ""


# ── date_str ──────────────────────────────────────────────────────

def test_date_str_format():
    from datetime import datetime, timezone
    entry = _make_entry(date=datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc))
    assert entry.date_str.startswith("2026-05-28")


# ── D-026: volatility / verified_at / staleness ───────────────────

from datetime import timedelta


def _aged(days: int, **kwargs) -> Entry:
    """Entry whose effective_date is `days` in the past."""
    old = datetime.now(timezone.utc) - timedelta(days=days)
    return _make_entry(date=old, **kwargs)


def test_volatility_default_is_unknown():
    assert _make_entry().volatility == "unknown"


def test_roundtrip_volatility_and_verified_at(tmp_path):
    v = datetime(2026, 5, 1, tzinfo=timezone.utc)
    entry = _make_entry(volatility="external-fact", verified_at=v)
    path = tmp_path / f"{entry.id}.md"
    path.write_text(entry.to_file_content(), encoding="utf-8")
    loaded = Entry.from_file(path)
    assert loaded.volatility == "external-fact"
    assert loaded.verified_at == v


def test_unknown_volatility_not_serialized(tmp_path):
    # default volatility stays out of the frontmatter (backward-compatible files)
    entry = _make_entry()
    assert "volatility" not in entry.to_file_content()


def test_legacy_entry_without_volatility_loads(tmp_path):
    # a file written before D-026 has no volatility/verified_at keys
    p = tmp_path / "legacy.md"
    p.write_text(
        "---\nid: 20260101-000000-aaaa\ntype: pitfall\n"
        "title: old one\ntags: [x]\ndate: 2026-01-01T00:00:00+00:00\n---\n\n"
        "**Symptom:** s\n\n**Root cause:** r\n\n**Fix:** f\n",
        encoding="utf-8",
    )
    e = Entry.from_file(p)
    assert e.volatility == "unknown"
    assert e.verified_at is None


def test_external_fact_goes_stale_faster_than_invariant():
    age = 300  # days: past external-fact TTL (180) but under invariant TTL (1095)
    assert _aged(age, volatility="external-fact").is_stale is True
    assert _aged(age, volatility="internal-invariant").is_stale is False


def test_fresh_entry_not_stale():
    assert _aged(10, volatility="external-fact").is_stale is False


def test_verified_at_resets_the_clock():
    # captured long ago, but re-verified recently → not stale
    old = datetime.now(timezone.utc) - timedelta(days=900)
    recent = datetime.now(timezone.utc) - timedelta(days=5)
    e = _make_entry(date=old, verified_at=recent, volatility="external-fact")
    assert e.is_stale is False


def test_superseded_never_flagged_stale_but_demoted():
    e = _aged(900, status="superseded", volatility="external-fact")
    assert e.is_stale is False        # only active entries are "stale"
    assert e.recall_demotion == 1     # but they sink in recall


def test_active_entry_demotion_is_zero():
    assert _make_entry().recall_demotion == 0
