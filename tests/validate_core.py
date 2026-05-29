#!/usr/bin/env python3
"""
validate_core.py — end-to-end validation for all vein core commands.

Usage:
    python tests/validate_core.py
    python tests/validate_core.py 2>&1 | tee validate_core.log

Covers:
  - Entry model (new_id, roundtrip, body_section)
  - VeinStore (init, write, read, list, grep, open_index)
  - CLI: vein init / log / status / list / ask / recall / brief / reindex / import
  - vein pipe (stdin triage)
  - triage.py extract_error_terms

No pytest required. No ollama required. All tests run offline in temp dirs.
"""

import subprocess
import sys
import tempfile
import textwrap
import traceback
from pathlib import Path

# ── helpers ───────────────────────────────────────────────────────

VEIN_CMD = [sys.executable, "-m", "vein"]
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

_results: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    """Run fn(); record PASS/FAIL."""
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
        cwd=cwd or str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        input=input_text,
    )
    if expect_ok and r.returncode != 0:
        raise AssertionError(
            f"exit {r.returncode}\n"
            f"stdout: {r.stdout[-300:]}\n"
            f"stderr: {r.stderr[-300:]}"
        )
    return r


def section(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ── Section 1: Entry model ─────────────────────────────────────────

section("1. Entry model")

def t_new_id_format():
    import re
    from vein.core.models import Entry
    eid = Entry.new_id()
    assert re.match(r"^\d{8}-\d{6}-[0-9a-f]{4}$", eid), f"bad id: {eid}"

def t_new_id_unique():
    from vein.core.models import Entry
    ids = {Entry.new_id() for _ in range(30)}
    assert len(ids) == 30

def t_roundtrip_basic():
    from vein.core.models import Entry
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        e = Entry(id=Entry.new_id(), type="decision",
                  title="Use WAL mode not journal",
                  tags=["sqlite", "wal"],
                  body="**Why:** concurrent writes\n\n**Trade-off:** slightly larger DB file")
        p = Path(tmp) / f"{e.id}.md"
        p.write_text(e.to_file_content(), encoding="utf-8")
        loaded = Entry.from_file(p)
        assert loaded.id == e.id
        assert loaded.type == e.type
        assert loaded.title == e.title
        assert loaded.tags == e.tags
        assert "concurrent writes" in loaded.body

def t_roundtrip_unicode():
    from vein.core.models import Entry
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        e = Entry(id=Entry.new_id(), type="lore",
                  title="DMA 中斷 callback — 不 polling",
                  tags=[], body="**Observation:** 測試\n\n**Context:** 正式環境")
        p = Path(tmp) / f"{e.id}.md"
        p.write_text(e.to_file_content(), encoding="utf-8")
        loaded = Entry.from_file(p)
        assert loaded.title == "DMA 中斷 callback — 不 polling"

def t_roundtrip_all_types():
    from vein.core.models import Entry
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        for etype in ("decision", "lore", "pitfall", "reference"):
            e = Entry(id=Entry.new_id(), type=etype,
                      title=f"Test {etype}", tags=[], body="body")
            p = Path(tmp) / f"{e.id}.md"
            p.write_text(e.to_file_content(), encoding="utf-8")
            loaded = Entry.from_file(p)
            assert loaded.type == etype, f"got {loaded.type}"

def t_body_section():
    from vein.core.models import Entry
    e = Entry(id=Entry.new_id(), type="decision", title="T", tags=[],
              body="**Why:** event-driven\n\n**Trade-off:** ISR discipline")
    assert "event-driven" in e.body_section("Why")
    assert e.body_section("Missing") == ""

def t_date_str():
    from vein.core.models import Entry
    from datetime import datetime, timezone
    e = Entry(id=Entry.new_id(), type="lore", title="T", tags=[],
              body="", date=datetime(2026, 5, 29, 0, 0, tzinfo=timezone.utc))
    assert e.date_str.startswith("2026-05-29")

check("new_id format", t_new_id_format)
check("new_id unique (×30)", t_new_id_unique)
check("roundtrip basic", t_roundtrip_basic)
check("roundtrip unicode title", t_roundtrip_unicode)
check("roundtrip all 4 types", t_roundtrip_all_types)
check("body_section extract", t_body_section)
check("date_str format", t_date_str)


# ── Section 2: VeinStore ──────────────────────────────────────────

section("2. VeinStore")

def t_store_init():
    from vein.core.store import VeinStore
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        created = s.init(name="test")
        assert created is True
        assert (Path(tmp) / ".vein" / "decisions").is_dir()
        assert (Path(tmp) / ".vein" / "config.yaml").is_file()

def t_store_init_idempotent():
    from vein.core.store import VeinStore
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        assert s.init(name="test") is False

def t_store_write_read():
    from vein.core.store import VeinStore
    from vein.core.models import Entry
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        e = Entry(id=Entry.new_id(), type="decision",
                  title="Test write-read", tags=["x"], body="**Why:** a\n\n**Trade-off:** b")
        s.write_entry(e, auto_index=False)
        loaded = s.read_entry(e.id)
        assert loaded.title == e.title

def t_store_read_prefix():
    from vein.core.store import VeinStore
    from vein.core.models import Entry
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        e = Entry(id=Entry.new_id(), type="lore",
                  title="Prefix read test", tags=[], body="**Observation:** ok\n\n**Context:** none")
        s.write_entry(e, auto_index=False)
        loaded = s.read_entry(e.id[:8])
        assert loaded.id == e.id

def t_store_not_found():
    from vein.core.store import VeinStore
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        try:
            s.read_entry("nonexistent-id-00000000")
            raise AssertionError("should have raised KeyError")
        except KeyError:
            pass

def t_store_list_filter():
    from vein.core.store import VeinStore
    from vein.core.models import Entry
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        s.write_entry(Entry(id=Entry.new_id(), type="decision",
                            title="D1", tags=[], body="**Why:** a\n\n**Trade-off:** b"), auto_index=False)
        s.write_entry(Entry(id=Entry.new_id(), type="pitfall",
                            title="P1", tags=[], body="**Symptom:** x\n\n**Root cause:** y\n\n**Fix:** z"), auto_index=False)
        decisions = s.list_entries(type_filter="decision")
        assert all(e.type == "decision" for e in decisions)
        assert len(decisions) == 1

def t_store_grep():
    from vein.core.store import VeinStore
    from vein.core.models import Entry
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        s.write_entry(Entry(id=Entry.new_id(), type="pitfall",
                            title="UART baud mismatch causes framing error",
                            tags=["uart"], body="**Symptom:** garbled\n\n**Root cause:** baud\n\n**Fix:** match baud"), auto_index=False)
        results = s.grep_entries("UART", limit=5)
        assert len(results) == 1
        results_lower = s.grep_entries("uart", limit=5)
        assert len(results_lower) == 1

def t_store_stats():
    from vein.core.store import VeinStore
    from vein.core.models import Entry
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        s.write_entry(Entry(id=Entry.new_id(), type="decision",
                            title="D", tags=[], body="**Why:** a\n\n**Trade-off:** b"), auto_index=False)
        s.write_entry(Entry(id=Entry.new_id(), type="lore",
                            title="L", tags=[], body="**Observation:** a\n\n**Context:** b"), auto_index=False)
        st = s.stats()
        assert st["decision"] == 1
        assert st["lore"] == 1
        assert st["pitfall"] == 0

def t_store_brief_invalidate():
    from vein.core.store import VeinStore
    from vein.core.models import Entry
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        s.write_brief("cached content")
        assert (s.vein_dir / "BRIEF.md").exists()
        s.write_entry(Entry(id=Entry.new_id(), type="lore",
                            title="L", tags=[], body="**Observation:** a\n\n**Context:** b"), auto_index=False)
        assert not (s.vein_dir / "BRIEF.md").exists()

def t_store_open_index():
    from vein.core.store import VeinStore
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        idx = s.open_index()
        assert idx is not None
        idx.close()
        assert (s.vein_dir / "index" / "vein.db").exists()

def t_store_find_from_subdir():
    from vein.core.store import VeinStore
    with tempfile.TemporaryDirectory() as tmp:
        # .resolve() handles macOS /private/var symlink
        root = Path(tmp).resolve()
        s = VeinStore(root)
        s.init(name="test")
        subdir = root / "src" / "deep" / "nested"
        subdir.mkdir(parents=True)
        found = VeinStore.find(subdir)
        assert found is not None, "VeinStore.find() returned None"
        assert found.root.resolve() == root, f"{found.root!r} != {root!r}"

check("store init creates structure", t_store_init)
check("store init idempotent", t_store_init_idempotent)
check("store write + read", t_store_write_read)
check("store read by id prefix", t_store_read_prefix)
check("store read not found → KeyError", t_store_not_found)
check("store list with type filter", t_store_list_filter)
check("store grep (case-insensitive)", t_store_grep)
check("store stats", t_store_stats)
check("store brief invalidated on write", t_store_brief_invalidate)
check("store open_index creates vein.db", t_store_open_index)
check("store find from deep subdir", t_store_find_from_subdir)


# ── Section 3: Index (FTS + embed offline) ────────────────────────

section("3. VeinIndex (FTS5 + cosine — offline)")

def t_index_upsert_fts():
    from vein.core.store import VeinStore
    from vein.core.models import Entry
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        e = Entry(id=Entry.new_id(), type="pitfall",
                  title="SQLite write lock under concurrent writers",
                  tags=["sqlite", "concurrency"],
                  body="**Symptom:** locked\n\n**Root cause:** journal mode\n\n**Fix:** WAL")
        idx = s.open_index()
        idx.upsert(e, base_url="http://localhost:11434")  # embedding will fail silently
        hits = idx.fts_search("SQLite concurrent", k=5)
        idx.close()
        assert e.id in hits

def t_index_fts_fallback_like():
    from vein.core.store import VeinStore
    from vein.core.models import Entry
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        e = Entry(id=Entry.new_id(), type="lore",
                  title="nomic-embed-text returns 768-dim vector",
                  tags=["embedding"],
                  body="**Observation:** 768\n\n**Context:** nomic model")
        idx = s.open_index()
        idx.upsert(e, base_url="http://localhost:11434")
        # LIKE fallback triggered by special chars
        hits = idx.fts_search("nomic embed", k=5)
        idx.close()
        assert e.id in hits

def t_index_reindex_all():
    from vein.core.store import VeinStore
    from vein.core.models import Entry
    with tempfile.TemporaryDirectory() as tmp:
        s = VeinStore(Path(tmp))
        s.init(name="test")
        entries = [
            Entry(id=Entry.new_id(), type="decision", title=f"D{i}",
                  tags=[], body="**Why:** a\n\n**Trade-off:** b")
            for i in range(5)
        ]
        for e in entries:
            s.write_entry(e, auto_index=False)
        idx = s.open_index()
        embedded, skipped = idx.reindex_all(entries, base_url="http://localhost:11434")
        idx.close()
        # ollama likely offline → all skipped, but FTS still indexed
        assert embedded + skipped == 5

def t_cosine_sim():
    from vein.core.embed import cosine_sim
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert abs(cosine_sim(a, b) - 1.0) < 1e-9
    c = [0.0, 1.0, 0.0]
    assert abs(cosine_sim(a, c) - 0.0) < 1e-9

def t_top_k_similar():
    from vein.core.embed import top_k_similar
    qvec = [1.0, 0.0]
    candidates = [
        ("id_a", [1.0, 0.0]),   # cosine = 1.0
        ("id_b", [0.0, 1.0]),   # cosine = 0.0
        ("id_c", [0.7, 0.7]),   # cosine ~ 0.707
    ]
    results = top_k_similar(qvec, candidates, k=2, min_score=0.5)
    assert len(results) == 2
    assert results[0][0] == "id_a"
    assert results[1][0] == "id_c"

check("index upsert → FTS search hits", t_index_upsert_fts)
check("index FTS LIKE fallback", t_index_fts_fallback_like)
check("index reindex_all (5 entries, embed may skip)", t_index_reindex_all)
check("cosine_sim: identical=1, orthogonal=0", t_cosine_sim)
check("top_k_similar ordering + min_score filter", t_top_k_similar)


# ── Section 4: triage.py ──────────────────────────────────────────

section("4. triage.extract_error_terms")

def t_triage_rust():
    from vein.core.triage import extract_error_terms
    log = textwrap.dedent("""\
        Compiling mylib v0.1.0
        Checking mylib v0.1.0
        error[E0308]: mismatched types
         --> src/main.rs:10:5
        note: expected type `i32`
        warning: unused variable
    """)
    out = extract_error_terms(log)
    assert "E0308" in out or "mismatched" in out, f"got: {out!r}"

def t_triage_python():
    from vein.core.triage import extract_error_terms
    log = textwrap.dedent("""\
        Traceback (most recent call last):
          File "test.py", line 5
        AttributeError: NoneType has no attribute split
    """)
    out = extract_error_terms(log)
    assert "AttributeError" in out, f"got: {out!r}"

def t_triage_pytest():
    from vein.core.triage import extract_error_terms
    log = "FAILED tests/test_store.py::test_read_not_found - KeyError: nonexistent\n1 failed"
    out = extract_error_terms(log)
    assert "FAILED" in out or "KeyError" in out, f"got: {out!r}"

def t_triage_noise_filtered():
    from vein.core.triage import extract_error_terms
    log = "Compiling\nResolving\nUpdating\nDownloading\nInstalling\nBuilding\n"
    out = extract_error_terms(log)
    # all noise → falls back to last non-empty lines (short), but nothing alarming
    assert len(out) < 200

check("triage: Rust error[E0308] extracted", t_triage_rust)
check("triage: Python AttributeError extracted", t_triage_python)
check("triage: pytest FAILED extracted", t_triage_pytest)
check("triage: pure noise → short output", t_triage_noise_filtered)


# ── Section 5: CLI — vein init / log / status ──────────────────────

section("5. CLI: init / log / status / list / ask / brief")

def t_cli_init():
    with tempfile.TemporaryDirectory() as tmp:
        r = cli("init", "test-project", cwd=tmp)
        assert "Initialized" in r.stdout
        assert (Path(tmp) / ".vein" / "config.yaml").exists()

def t_cli_log_decision():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        r = cli("log", "decision", "Use WAL not journal mode for SQLite",
                "--no-polish", "--yes", cwd=tmp)
        assert "Saved" in r.stdout
        entries = list((Path(tmp) / ".vein" / "decisions").glob("*.md"))
        assert len(entries) == 1

def t_cli_log_shorthand():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        r = cli("log", "p", "HAL timer not re-entrant",
                "--no-polish", "--yes", cwd=tmp)
        assert "Saved" in r.stdout
        pitfalls = list((Path(tmp) / ".vein" / "pitfalls").glob("*.md"))
        assert len(pitfalls) == 1

def t_cli_log_all_types():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        for type_, flag in [("d", "decisions"), ("l", "lore"),
                            ("p", "pitfalls"), ("r", "references")]:
            cli("log", type_, f"Test {type_} entry", "--no-polish", "--yes", cwd=tmp)
        for d in ("decisions", "lore", "pitfalls", "references"):
            assert len(list((Path(tmp) / ".vein" / d).glob("*.md"))) == 1, f"missing {d}"

def t_cli_status():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        cli("log", "d", "Decision A", "--no-polish", "--yes", cwd=tmp)
        cli("log", "p", "Pitfall B", "--no-polish", "--yes", cwd=tmp)
        r = cli("status", cwd=tmp)
        assert "decision" in r.stdout
        assert "pitfall" in r.stdout

def t_cli_list():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        cli("log", "d", "Alpha decision", "--no-polish", "--yes", cwd=tmp)
        cli("log", "l", "Beta lore entry", "--no-polish", "--yes", cwd=tmp)
        r = cli("list", cwd=tmp)
        assert "decision" in r.stdout
        assert "lore" in r.stdout

def t_cli_list_type_filter():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        cli("log", "d", "Decision A", "--no-polish", "--yes", cwd=tmp)
        cli("log", "p", "Pitfall B", "--no-polish", "--yes", cwd=tmp)
        r = cli("list", "--type", "pitfall", cwd=tmp)
        assert "pitfall" in r.stdout
        assert "decision" not in r.stdout

def t_cli_ask():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        cli("log", "p", "UART baud rate mismatch causes framing error",
            "--no-polish", "--yes", cwd=tmp)
        r = cli("ask", "UART baud", cwd=tmp)
        assert "UART" in r.stdout or "baud" in r.stdout.lower()

def t_cli_brief():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        cli("log", "d", "Decision for brief test", "--no-polish", "--yes", cwd=tmp)
        r = cli("brief", "--raw", cwd=tmp)
        assert len(r.stdout.strip()) > 0

def t_cli_recall_fts():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        cli("log", "l", "nomic-embed-text is 768-dim vector model",
            "--no-polish", "--yes", cwd=tmp)
        cli("reindex", cwd=tmp)
        r = cli("recall", "nomic embed", "--fts-only", cwd=tmp)
        assert "nomic" in r.stdout.lower() or "768" in r.stdout

check("cli: vein init", t_cli_init)
check("cli: vein log decision --no-polish --yes", t_cli_log_decision)
check("cli: vein log p (shorthand)", t_cli_log_shorthand)
check("cli: vein log all 4 types (d/l/p/r)", t_cli_log_all_types)
check("cli: vein status shows counts", t_cli_status)
check("cli: vein list", t_cli_list)
check("cli: vein list --type pitfall filters", t_cli_list_type_filter)
check("cli: vein ask keyword search", t_cli_ask)
check("cli: vein brief --raw", t_cli_brief)
check("cli: vein recall --fts-only after reindex", t_cli_recall_fts)


# ── Section 6: vein import ────────────────────────────────────────

section("6. CLI: vein import")

_DECISIONS_MD = textwrap.dedent("""\
    # Decisions

    ### D-001 — Use Python not Rust for Phase 0

    **Date:** 2026-05-26

    Speed of iteration matters more than runtime perf at this stage.

    ---

    ### D-002 — Embed with nomic-embed-text

    **Date:** 2026-05-27

    768-dim, runs fully local via ollama.

    ---
""")

def t_import_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        dm = Path(tmp) / "decisions.md"
        dm.write_text(_DECISIONS_MD, encoding="utf-8")
        r = cli("import", "decisions.md", "--dry-run", cwd=tmp)
        assert "D-001" in r.stdout or "Python" in r.stdout or "2 entries" in r.stdout

def t_import_real():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        dm = Path(tmp) / "decisions.md"
        dm.write_text(_DECISIONS_MD, encoding="utf-8")
        r = cli("import", "decisions.md", "--no-index", cwd=tmp)
        assert "Imported" in r.stdout
        all_d = list((Path(tmp) / ".vein" / "decisions").glob("*.md"))
        all_l = list((Path(tmp) / ".vein" / "lore").glob("*.md"))
        total = len(all_d) + len(all_l)
        assert total == 2, f"expected 2 entries, got {total}"

def t_import_plain_md():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        note = Path(tmp) / "notes.md"
        note.write_text("# Architecture notes\nWe use SQLite for the index.\n", encoding="utf-8")
        r = cli("import", "notes.md", "--type", "lore", "--no-index", cwd=tmp)
        assert "Imported" in r.stdout or "1" in r.stdout

check("import: decisions.md --dry-run (2 D-xxx blocks)", t_import_dry_run)
check("import: decisions.md --no-index (writes 2 entries)", t_import_real)
check("import: plain .md → single lore entry", t_import_plain_md)


# ── Section 7: vein pipe ──────────────────────────────────────────

section("7. CLI: vein pipe (stdin triage)")

def t_pipe_no_crash_on_error():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        error_input = "error[E0308]: mismatched types\nnote: expected i32"
        r = subprocess.run(
            VEIN_CMD + ["pipe", "--cmd", "cargo check"],
            cwd=tmp,
            input=error_input,
            capture_output=True,
            text=True,
        )
        # should not crash (exit 0 or 1 both OK — just not 2/exception)
        assert r.returncode in (0, 1), f"unexpected exit {r.returncode}"
        combined = r.stdout + r.stderr
        assert "vein triage" in combined or "triage" in combined.lower() or "No matching" in combined

def t_pipe_empty_stdin():
    with tempfile.TemporaryDirectory() as tmp:
        cli("init", "test", cwd=tmp)
        r = subprocess.run(
            VEIN_CMD + ["pipe"],
            cwd=tmp, input="", capture_output=True, text=True,
        )
        assert "no input" in r.stdout.lower() or r.returncode == 0

check("pipe: error input → triage output (no crash)", t_pipe_no_crash_on_error)
check("pipe: empty stdin → graceful message", t_pipe_empty_stdin)


# ── Summary ───────────────────────────────────────────────────────

total   = len(_results)
passed  = sum(1 for _, ok, _ in _results if ok)
failed  = total - passed

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
