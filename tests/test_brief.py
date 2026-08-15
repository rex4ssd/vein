"""Regression tests for the review pass over brief generation and Entry parsing.

Common thread: every bug here made vein quietly show the *wrong* thing rather
than fail. An entry vanished from all listings, a section rendered empty, or the
brief spent half its token budget printing each title twice.
"""

from __future__ import annotations

import pytest

from vein.core.brief import _current_focus, _detail, generate_brief
from vein.core.models import Entry
from vein.core.store import VeinStore


@pytest.fixture
def store(tmp_path):
    s = VeinStore(tmp_path)
    s.init("test-project")
    return s


def _write(store, type_, title, body="", **fm):
    e = Entry.make(type=type_, title=title, body=body)
    for k, v in fm.items():
        setattr(e, k, v)
    store.write_entry(e, auto_index=False)
    return e


# ── frontmatter parsing: entries that used to silently vanish ─────

def test_unquoted_date_does_not_hide_the_entry(store):
    """`date: 2026-01-01` (no quotes) is a datetime.date, which has no tzinfo.

    That raised inside from_file, iter_entries catches bare Exception and skips,
    so the entry disappeared from every listing, recall and count with no error.
    """
    (store.vein_dir / "lore" / "d1.md").write_text(
        "---\nid: d1\ntype: lore\ntitle: bare date\ndate: 2026-01-01\n---\n\nbody\n",
        encoding="utf-8",
    )
    got = store.list_entries(status_filter=None)
    assert [e.id for e in got] == ["d1"]
    assert got[0].date.tzinfo is not None


@pytest.mark.parametrize("value", ["not-a-date", "", "2026-13-45"])
def test_unparseable_date_falls_back_instead_of_raising(store, value):
    (store.vein_dir / "lore" / "d2.md").write_text(
        f"---\nid: d2\ntype: lore\ntitle: t\ndate: '{value}'\n---\n\nbody\n",
        encoding="utf-8",
    )
    assert [e.id for e in store.list_entries(status_filter=None)] == ["d2"]


def test_null_frontmatter_values_fall_back_to_defaults(store):
    """A key present but empty parses to None, and `.get(k, default)` only
    fires when the key is *absent* — so `status:` yielded None, which compares
    unequal to "active" and dropped the entry from every default listing."""
    (store.vein_dir / "lore" / "n1.md").write_text(
        "---\nid: n1\ntype:\ntitle:\nstatus:\nvolatility:\nsource:\n---\n\nbody\n",
        encoding="utf-8",
    )
    entries = store.list_entries()          # default status_filter="active"
    assert [e.id for e in entries] == ["n1"]
    e = entries[0]
    assert (e.type, e.status, e.volatility, e.source) == (
        "lore", "active", "unknown", "local",
    )


# ── body_section ──────────────────────────────────────────────────

def _body(text):
    return Entry(id="i", type="decision", title="t", body=text)


def test_body_section_does_not_match_a_longer_heading():
    """`[:*]*` allowed zero terminators, so "Why" matched the prefix of
    "**Why not:**" and the brief quoted the rejected alternative as the
    rationale."""
    e = _body("**Why not:** we rejected X\n\n**Why:** the real reason")
    assert e.body_section("Why") == "the real reason"
    assert _body("**Why not:** only this").body_section("Why") == ""


def test_body_section_is_case_insensitive():
    assert _body("**why:** lowercase").body_section("Why") == "lowercase"


def test_body_section_survives_inline_bold():
    e = _body("**Symptom:** see **note** here\nsecond line\n\n**Why:** x")
    assert e.body_section("Symptom") == "see **note** here\nsecond line"


def test_body_section_accepts_bold_style_heading():
    assert _body("**Root cause** the cause").body_section("Root cause") == "the cause"


# ── brief rendering ───────────────────────────────────────────────

def test_detail_drops_text_that_merely_repeats_the_title():
    title = "SQLite 索引雷：LIKE 有 ESCAPE 就整個放棄索引最佳化，改用兩參數形式"
    assert _detail(title, title) == ""            # MCP capture: body == title
    assert _detail("完全不同的說明文字", title) == "完全不同的說明文字"


def test_brief_does_not_print_each_title_twice(store):
    """MCP vein_log stores the raw message as `**Why:** <msg>` and truncates
    the same message into the title, so the brief rendered both."""
    msg = "選 sqlite 不選 postgres，因為 local-first 不要 daemon 也不要 server"
    _write(store, "decision", msg[:40] + "…", body=f"**Why:** {msg}")
    out = generate_brief(store, regen=True)
    assert out.count("選 sqlite 不選 postgres") == 1


def test_brief_keeps_a_genuinely_different_why(store):
    _write(store, "decision", "Use SQLite", body="**Why:** no daemon to run")
    assert "no daemon to run" in generate_brief(store, regen=True)


def test_brief_counts_match_what_it_lists(store):
    _write(store, "decision", "d")
    _write(store, "pitfall", "p")
    out = generate_brief(store, regen=True)
    assert "(2 total)" in out


def test_brief_excludes_superseded_decisions(store):
    _write(store, "decision", "current")
    _write(store, "decision", "replaced", status="superseded")
    out = generate_brief(store, regen=True)
    assert "current" in out and "replaced" not in out


# ── STATUS.md Current focus ───────────────────────────────────────

def test_current_focus_extracts_the_section():
    """The inline version tested for "Current focus" while emitting a
    "Current Focus" header, so this section shipped empty in every brief."""
    text = (
        "# Status\n\n## Overview\nignore me\n\n"
        "## Current focus\n- ship the index fix\n- then the docs\n- and a third line\n\n"
        "## Blocked\nignore me too\n"
    )
    assert _current_focus(text) == [
        "- ship the index fix", "- then the docs", "- and a third line",
    ]


def test_current_focus_survives_a_preceding_heading():
    """`break` on the first `## ` aborted before reaching Current focus, so
    any STATUS.md not starting with that section produced nothing."""
    assert _current_focus("## Other\nx\n\n## Current focus\nreal content\n") == [
        "real content"
    ]


def test_current_focus_absent_yields_nothing():
    assert _current_focus("# Status\n\n## Blocked\nnothing\n") == []


def test_brief_renders_current_focus(store):
    (store.vein_dir / "STATUS.md").write_text(
        "# Status\n\n## Current focus\n- the actual focus line\n", encoding="utf-8"
    )
    out = generate_brief(store, regen=True)
    assert "## Current Focus" in out
    assert "- the actual focus line" in out
