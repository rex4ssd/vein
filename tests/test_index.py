"""Regression tests for the two search bugs that made recall useless.

Bug A — semantic search only ever saw the oldest ~100 rows. ``vector_search``
        pre-filtered candidates through FTS, and when FTS returned nothing it
        fell back to ``SELECT ... WHERE vector IS NOT NULL LIMIT 100`` with no
        ORDER BY — i.e. rowid order, the first rows ever inserted. Compounded
        by capture paths embedding with a different model than recall queried
        with, so the newer vectors were dimensionally incomparable anyway.

Bug B — FTS used stock unicode61, which treats a run of Han characters as one
        token. A CJK query matched only when the sought word happened to sit
        alone between two punctuation marks.
"""

from __future__ import annotations

import json

import pytest

from vein.core import cjk
from vein.core.index import VeinIndex, pack_vector, unpack_vector
from vein.core.models import Entry
from vein.core.store import VeinStore


@pytest.fixture
def store(tmp_path):
    s = VeinStore(tmp_path)
    s.init("test")
    return s


@pytest.fixture
def idx(tmp_path):
    return VeinIndex(tmp_path / "idx" / "vein.db")


def _entry(title, body="", tags=None, type="lore"):
    return Entry.make(type=type, title=title, body=body, tags=tags or [])


def _insert(idx, entry, vector=None):
    """Insert directly, bypassing the ollama call in upsert()."""
    idx.conn.execute(
        "INSERT INTO embeddings (entry_id, entry_type, title, tags, vector, indexed_at) "
        "VALUES (?, ?, ?, ?, ?, '2026-01-01T00:00:00+00:00')",
        (entry.id, entry.type, entry.title, " ".join(entry.tags),
         pack_vector(vector) if vector else None),
    )
    idx.conn.execute(
        "INSERT INTO fts (entry_id, title, body, tags) VALUES (?, ?, ?, ?)",
        (entry.id, cjk.segment(entry.title), cjk.segment(entry.body),
         cjk.segment(" ".join(entry.tags))),
    )
    idx.conn.commit()


# ── cjk tokenisation ──────────────────────────────────────────────

def test_segment_splits_han_not_latin():
    assert cjk.segment("索引").split() == ["索", "引"]
    assert cjk.segment("sqlite").strip() == "sqlite"


def test_segment_is_idempotent_for_tokens():
    once = cjk.segment("放棄索引")
    assert cjk.segment(once).split() == once.split()


def test_tokenize_mixed_script():
    assert cjk.tokenize("MCP伺服器") == ["MCP", "伺", "服", "器"]
    assert cjk.tokenize("sqlite-vec") == ["sqlite", "vec"]


def test_hangul_not_split():
    """Korean is space-delimited — splitting it would destroy word boundaries."""
    assert cjk.segment("데이터베이스") == "데이터베이스"


def test_build_match_quotes_fts5_operators():
    """Bare operators used to raise OperationalError and drop search to LIKE."""
    assert cjk.build_match("NEAR(a b)") == '"NEAR a" AND "b"'
    assert cjk.build_match("-x*") == '"x"'
    assert cjk.build_match("!!!") is None


def test_build_match_cjk_becomes_phrase():
    assert cjk.build_match("索引") == '"索 引"'
    assert cjk.build_match("為什麼 sqlite") == '"為 什 麼" AND "sqlite"'


def test_build_loose_match_uses_bigrams():
    assert cjk.build_loose_match("索引效能") == '"索 引" OR "引 效" OR "效 能"'
    assert cjk.build_loose_match("索引") == '"索 引"'          # already a bigram
    assert cjk.build_loose_match("為什麼用sqlite").endswith('OR "sqlite"')


# ── Bug B: CJK is findable mid-clause ─────────────────────────────

def test_cjk_query_matches_inside_a_clause(idx):
    """The exact case unicode61 fails: sought word not delimited by punctuation."""
    e = _entry("SQLite 雷", body="有 ESCAPE 就整個放棄索引效能")
    _insert(idx, e)
    assert idx.fts_search("索引") == [e.id]
    assert idx.fts_search("放棄") == [e.id]
    assert idx.fts_search("整個放棄索引") == [e.id]


def test_cjk_phrase_does_not_match_across_a_gap(idx):
    """Per-character tokens must still form a phrase, or precision collapses."""
    _insert(idx, _entry("索然無味的引數"))
    assert idx.fts_search("索引") == []


def test_spaceless_cjk_query_matches_separate_words(idx):
    """Chinese has no inter-word spaces, so a real query arrives as one chunk.

    As a single phrase ``索引效能`` demands that exact substring and finds
    nothing; the bigram tier lets it reach documents about 索引 and 效能.
    """
    a = _entry("SQLite 索引雷")
    b = _entry("啟動效能優化")
    _insert(idx, a)
    _insert(idx, b)
    assert set(idx.fts_search("索引效能")) == {a.id, b.id}


def test_precise_tier_wins_over_bigram_tier(idx):
    """The loose tier must not dilute a query the phrase tier can answer."""
    exact = _entry("跨專案付費策略")
    partial = _entry("付費牆設計")
    _insert(idx, exact)
    _insert(idx, partial)
    assert idx.fts_search("跨專案付費策略") == [exact.id]


def test_multi_term_cjk_query_falls_back_to_or(idx):
    """AND-of-all-terms returns nothing; OR still surfaces the best match."""
    hit = _entry("MCP 伺服器設定")
    _insert(idx, hit)
    assert idx.fts_search("MCP 伺服器設定 完全不存在的詞") == [hit.id]


def test_fts_survives_syntax_characters(idx):
    e = _entry("sqlite-vec 評估")
    _insert(idx, e)
    assert idx.fts_search("sqlite-vec") == [e.id]
    assert idx.fts_search('a AND b OR "c') == []  # no exception


def test_empty_query_returns_nothing_not_everything(idx):
    """A tokenless query must not reach the LIKE fallback as '%%'."""
    for i in range(3):
        _insert(idx, _entry(f"entry {i}"))
    assert idx.fts_search("!!! ???") == []
    assert idx.fts_search("") == []


# ── Bug A: semantic search sees the whole corpus ──────────────────

def test_vector_search_is_not_capped_at_insertion_order(idx):
    """The regression: 200 old rows inserted first must not hide row 201.

    Pre-fix this returned only rows from the first 100 inserted, because the
    no-FTS-hit branch was ``LIMIT 100`` over rowid order.
    """
    for i in range(200):
        _insert(idx, _entry(f"old entry {i}"), vector=[1.0, 0.0, 0.0])
    target = _entry("the newest entry")
    _insert(idx, target, vector=[0.0, 1.0, 0.0])

    hits = idx.similar_to_vector([0.0, 1.0, 0.0], k=1, min_score=0.5)
    assert [h[0] for h in hits] == [target.id]


def test_similar_to_vector_ranks_by_cosine(idx):
    near, far = _entry("near"), _entry("far")
    _insert(idx, near, vector=[1.0, 0.1, 0.0])
    _insert(idx, far, vector=[0.0, 0.0, 1.0])
    hits = idx.similar_to_vector([1.0, 0.0, 0.0], k=2, min_score=0.0)
    assert [h[0] for h in hits] == [near.id, far.id]
    assert hits[0][1] > hits[1][1]


def test_mismatched_dimensions_are_skipped_not_truncated(idx):
    """Vectors from another embed model must be excluded, not silently zipped.

    ``cosine_sim`` used ``zip``, which truncates to the shorter operand — a
    768-dim entry scored against a 2560-dim query produced a plausible-looking
    number computed from an arbitrary prefix.
    """
    wrong = _entry("embedded with another model")
    right = _entry("embedded with this model")
    _insert(idx, wrong, vector=[1.0, 0.0])
    _insert(idx, right, vector=[0.9, 0.1, 0.0])

    hits = idx.similar_to_vector([1.0, 0.0, 0.0], k=5, min_score=0.0)
    assert [h[0] for h in hits] == [right.id]
    assert idx.last_dim_mismatch == 1


def test_numpy_and_pure_python_paths_agree(idx, monkeypatch):
    """numpy is an opportunistic speedup, not a dependency — both must match."""
    import vein.core.index as index_mod

    for i in range(20):
        _insert(idx, _entry(f"e{i}"), vector=[float(i), 1.0, float(20 - i)])
    query = [3.0, 1.0, 7.0]

    with_np = idx.similar_to_vector(query, k=5, min_score=0.0)
    monkeypatch.setattr(index_mod, "_np", None)
    without_np = idx.similar_to_vector(query, k=5, min_score=0.0)

    assert [e for e, _ in with_np] == [e for e, _ in without_np]
    assert [s for _, s in with_np] == pytest.approx([s for _, s in without_np], abs=1e-6)


def test_pack_unpack_roundtrip_normalises():
    vec = [3.0, 4.0]
    out = list(unpack_vector(pack_vector(vec)))
    assert out == pytest.approx([0.6, 0.8], abs=1e-6)


def test_pack_vector_rejects_zero_vector():
    assert pack_vector([0.0, 0.0]) is None


# ── hybrid fusion ─────────────────────────────────────────────────

def test_hybrid_fuses_keyword_and_vector_ranks(idx, monkeypatch):
    kw = _entry("exact keyword hit", body="postgres")
    vec = _entry("semantic neighbour")
    _insert(idx, kw, vector=[0.0, 1.0])
    _insert(idx, vec, vector=[1.0, 0.0])
    monkeypatch.setattr("vein.core.index.embed_text", lambda *a, **k: [1.0, 0.0])

    ids, mode = idx.hybrid_search("postgres", k=5, min_score=0.0)
    assert mode == "hybrid"
    assert set(ids) == {kw.id, vec.id}


def test_hybrid_degrades_to_fts_without_ollama(idx, monkeypatch):
    e = _entry("keyword only", body="postgres")
    _insert(idx, e)
    monkeypatch.setattr("vein.core.index.embed_text", lambda *a, **k: None)
    ids, mode = idx.hybrid_search("postgres", k=5)
    assert (ids, mode) == ([e.id], "fts")


# ── v1 → v2 migration ─────────────────────────────────────────────

def test_migration_converts_json_vectors_and_resegments_fts(tmp_path):
    """A v1 DB must become searchable on open, without ollama or file reads."""
    import sqlite3

    db = tmp_path / "vein.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE embeddings (entry_id TEXT PRIMARY KEY, entry_type TEXT NOT NULL,
            title TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '', vector TEXT,
            indexed_at TEXT NOT NULL);
        CREATE VIRTUAL TABLE fts USING fts5(entry_id UNINDEXED, title, body, tags,
            tokenize='unicode61');
    """)
    conn.execute(
        "INSERT INTO embeddings VALUES ('e1','lore','舊條目','', ?, '2026-06-02T00:00:00+00:00')",
        (json.dumps([3.0, 4.0]),),
    )
    conn.execute("INSERT INTO fts VALUES ('e1','舊條目','就整個放棄索引','')")
    conn.commit()
    conn.close()

    idx = VeinIndex(db)
    assert idx.meta_get("schema_version") == "2"
    assert idx.fts_search("索引") == ["e1"]          # was unreachable pre-migration
    hits = idx.similar_to_vector([3.0, 4.0], k=1, min_score=0.9)
    assert [h[0] for h in hits] == ["e1"]           # JSON → BLOB, still comparable


def test_stale_v1_writer_rows_healed_on_open(tmp_path):
    """Rows written into an already-migrated DB by a stale v1 process (e.g. a
    long-lived MCP server that imported vein before the upgrade) must be
    repaired on the next open — the one-shot migration never sees them."""
    import sqlite3

    db = tmp_path / "vein.db"
    VeinIndex(db).close()  # fresh v2 DB, marker set

    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO embeddings VALUES ('late','lore','舊程序寫入','', ?, "
        "'2026-08-02T00:00:00+00:00')",
        (json.dumps([3.0, 4.0]),),  # v1 format: JSON text, unnormalised
    )
    conn.execute("INSERT INTO fts VALUES ('late','舊程序寫入','就整個放棄索引','')")
    conn.commit()
    conn.close()

    idx = VeinIndex(db)
    assert idx.fts_search("索引") == ["late"]           # FTS re-segmented
    hits = idx.similar_to_vector([3.0, 4.0], k=1, min_score=0.9)
    assert [h[0] for h in hits] == ["late"]             # JSON → BLOB


def test_migration_is_idempotent(tmp_path):
    db = tmp_path / "vein.db"
    i1 = VeinIndex(db)
    _insert(i1, _entry("放棄索引"), vector=[1.0, 0.0])
    i1.conn.execute("DELETE FROM meta WHERE key='schema_version'")
    i1.conn.commit()
    i1.close()

    i2 = VeinIndex(db)  # re-runs the migration against already-v2 data
    assert i2.count_embedded() == 1
    assert len(i2.fts_search("索引")) == 1


# ── write path uses the configured model ──────────────────────────

def test_write_entry_defaults_to_configured_embed_model(store, monkeypatch):
    """Regression: capture paths hardcoded nomic while recall used the config.

    The vectors got written but were a different dimension than any query
    vector, so nothing captured this way was ever semantically reachable.
    """
    cfg = store.vein_dir / "config.yaml"
    cfg.write_text("model:\n  embed_model: qwen3-embedding:4b\n", encoding="utf-8")

    seen = {}
    monkeypatch.setattr(
        "vein.core.index.embed_text",
        lambda text, *, base_url, model, **k: seen.setdefault("model", model) and None,
    )
    store.write_entry(_entry("x"))
    assert seen["model"] == "qwen3-embedding:4b"


def test_write_entry_rerolls_on_cross_process_id_collision(store):
    """Two vein processes minting the same id in the same second must not
    silently overwrite each other's files."""
    victim = _entry("written by the other process")
    (store.vein_dir / "lore" / f"{victim.id}.md").write_text(
        victim.to_file_content(), encoding="utf-8"
    )

    imposter = Entry.make(type="lore", title="written by us")
    imposter.id = victim.id                      # simulate the suffix collision
    Entry._issued_ids.add(victim.id)             # id counts as freshly minted
    store.write_entry(imposter, auto_index=False)

    assert imposter.id != victim.id              # re-rolled, not overwritten
    on_disk = (store.vein_dir / "lore" / f"{victim.id}.md").read_text(encoding="utf-8")
    assert "written by the other process" in on_disk
    assert (store.vein_dir / "lore" / f"{imposter.id}.md").exists()


def test_write_entry_preserved_id_still_overwrites(store):
    """Migrate/import re-runs carry preserved ids and rely on idempotent
    overwrite — the collision guard must not apply to them."""
    first = Entry.make(type="lore", title="v1")
    first.id = "20200101-000000-cafe"            # old, not freshly minted
    Entry._issued_ids.discard(first.id)
    store.write_entry(first, auto_index=False)

    again = Entry.make(type="lore", title="v2")
    again.id = "20200101-000000-cafe"
    again._path = None
    store.write_entry(again, auto_index=False)

    assert again.id == first.id                  # same file, updated in place
    files = list((store.vein_dir / "lore").glob("20200101-*"))
    assert len(files) == 1
    assert "v2" in files[0].read_text(encoding="utf-8")


def test_read_entry_finds_superseded_entry(store):
    """Index hits may point at superseded entries; recall demotes, not hides."""
    e = _entry("gone stale")
    e.status = "superseded"
    store.write_entry(e, auto_index=False)
    assert store.read_entry(e.id).id == e.id
