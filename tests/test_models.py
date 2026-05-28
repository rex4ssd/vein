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
