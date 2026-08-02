"""index.py — SQLite-backed embedding + FTS index for .vein/

Schema (v2):
  meta        (key PK, value)                 — schema version, embed model/dim
  embeddings  (entry_id PK, entry_type, title, tags, vector BLOB, indexed_at)
  fts5        (entry_id, title, body, tags)   — virtual FTS5 table, CJK-segmented

Vectors are stored **L2-normalised, little-endian float32** so cosine similarity
is a plain dot product and a full-corpus scan stays cheap (~15ms for 900×2560
with numpy, ~50ms without). Phase 1: sqlite-vec ANN once the corpus passes ~50K.

v1 databases are migrated in place on open — see ``_migrate_v1_to_v2``.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from array import array
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from . import cjk
from .embed import embed_entry_text, embed_text

if TYPE_CHECKING:
    from .models import Entry

try:  # optional: ~10x faster full-corpus scan, but never required
    import numpy as _np
except ImportError:  # pragma: no cover - numpy is not a declared dependency
    _np = None

SCHEMA_VERSION = 2

_DDL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS embeddings (
    entry_id   TEXT PRIMARY KEY,
    entry_type TEXT NOT NULL,
    title      TEXT NOT NULL,
    tags       TEXT NOT NULL DEFAULT '',
    vector     BLOB,           -- normalised float32, NULL if not embedded
    indexed_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
    entry_id UNINDEXED,
    title,
    body,
    tags,
    tokenize = 'unicode61'
);
"""


# ── vector (de)serialisation ──────────────────────────────────────────────────

def pack_vector(vec: list[float]) -> bytes | None:
    """L2-normalise and pack as little-endian float32. None if degenerate."""
    norm = math.sqrt(sum(x * x for x in vec))
    if not norm or not math.isfinite(norm):
        return None
    arr = array("f", [x / norm for x in vec])
    if sys.byteorder != "little":  # pragma: no cover - all supported hosts are LE
        arr.byteswap()
    return arr.tobytes()


def unpack_vector(blob: bytes) -> array:
    arr = array("f")
    arr.frombytes(blob)
    if sys.byteorder != "little":  # pragma: no cover
        arr.byteswap()
    return arr


class VeinIndex:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Set by VeinStore.open_index when the DB had to be relocated off an
        # unsupported filesystem (network/FUSE/synced). None = in-repo path.
        self.relocated_to: Path | None = None
        # Vectors skipped by the last scan because their dimension no longer
        # matches the query embedding (i.e. embed_model changed since indexing).
        self.last_dim_mismatch = 0
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._setup()

    def _setup(self) -> None:
        self.conn.executescript(_DDL)
        version = self.meta_get("schema_version")
        if version is None:
            # No marker: either a brand-new DB, or a v1 DB predating `meta`.
            # Check both tables — an FTS-only store still needs re-segmenting.
            has_data = (
                self.conn.execute("SELECT 1 FROM embeddings LIMIT 1").fetchone()
                or self.conn.execute("SELECT 1 FROM fts LIMIT 1").fetchone()
            )
            if has_data:
                self._migrate_v1_to_v2()
        # Only write the marker when it changes: search paths open the index
        # read-only in spirit, and an unconditional write here would take a
        # write lock on every open — needless contention when a capture
        # process and a recall process touch the DB at the same time.
        if version != str(SCHEMA_VERSION):
            self.meta_set("schema_version", str(SCHEMA_VERSION))
            self.conn.commit()
        self._heal_v1_rows()

    def close(self) -> None:
        self.conn.close()

    # ── meta ──────────────────────────────────────────────────────

    def meta_get(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def meta_set(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    # ── migration ─────────────────────────────────────────────────

    def _migrate_v1_to_v2(self) -> None:
        """Upgrade a v1 index in place — no ollama calls, no file re-reads.

        v1 stored vectors as JSON text and fed the FTS table raw text, which
        left every CJK clause as a single unsearchable token (see cjk.py).
        Both are recoverable from what's already in the DB.
        """
        # vectors: JSON text → normalised float32 BLOB
        rows = self.conn.execute(
            "SELECT entry_id, vector FROM embeddings WHERE vector IS NOT NULL"
        ).fetchall()
        for row in rows:
            raw = row["vector"]
            if not isinstance(raw, str):
                continue  # already a BLOB
            try:
                blob = pack_vector(json.loads(raw))
            except (json.JSONDecodeError, TypeError, ValueError):
                blob = None
            self.conn.execute(
                "UPDATE embeddings SET vector = ? WHERE entry_id = ?",
                (blob, row["entry_id"]),
            )

        # FTS: re-tokenise the stored text with CJK segmentation
        fts_rows = self.conn.execute(
            "SELECT entry_id, title, body, tags FROM fts"
        ).fetchall()
        if fts_rows:
            self.conn.execute("DELETE FROM fts")
            self.conn.executemany(
                "INSERT INTO fts (entry_id, title, body, tags) VALUES (?, ?, ?, ?)",
                [
                    (
                        r["entry_id"],
                        cjk.segment(r["title"] or ""),
                        cjk.segment(r["body"] or ""),
                        cjk.segment(r["tags"] or ""),
                    )
                    for r in fts_rows
                ],
            )
        self.conn.commit()

    def _heal_v1_rows(self) -> None:
        """Repair rows written into a v2 database by a stale v1 process.

        The one-shot migration can't be the whole story: a long-lived process
        that imported vein before an upgrade — an MCP server serving other
        sessions is the concrete case — keeps writing JSON-text vectors and
        unsegmented FTS text into the already-migrated DB. Its rows arrive
        *after* the schema marker is set, so only a check on every open
        catches them. The ``typeof()`` scan is a few ms and almost always
        empty; when it does fire, the vectors are converted in place and the
        same rows' FTS text is re-segmented (``cjk.segment`` is idempotent on
        token boundaries, so re-segmenting good rows would also be safe).

        Blind spot, accepted: a stale writer with ollama down leaves a NULL
        vector and unsegmented FTS with nothing to detect it by — incremental
        ``vein reindex`` sweeps NULL-vector rows anyway and rewrites both.
        """
        rows = self.conn.execute(
            "SELECT entry_id, vector FROM embeddings "
            "WHERE vector IS NOT NULL AND typeof(vector) = 'text'"
        ).fetchall()
        if not rows:
            return
        for row in rows:
            try:
                blob = pack_vector(json.loads(row["vector"]))
            except (json.JSONDecodeError, TypeError, ValueError):
                blob = None
            self.conn.execute(
                "UPDATE embeddings SET vector = ? WHERE entry_id = ?",
                (blob, row["entry_id"]),
            )
        ids = [r["entry_id"] for r in rows]
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            ph = ",".join("?" * len(chunk))
            fts_rows = self.conn.execute(
                f"SELECT entry_id, title, body, tags FROM fts WHERE entry_id IN ({ph})",
                chunk,
            ).fetchall()
            self.conn.execute(f"DELETE FROM fts WHERE entry_id IN ({ph})", chunk)
            self.conn.executemany(
                "INSERT INTO fts (entry_id, title, body, tags) VALUES (?, ?, ?, ?)",
                [
                    (r["entry_id"], cjk.segment(r["title"] or ""),
                     cjk.segment(r["body"] or ""), cjk.segment(r["tags"] or ""))
                    for r in fts_rows
                ],
            )
        self.conn.commit()

    # ── upsert ────────────────────────────────────────────────────

    def upsert(
        self,
        entry: "Entry",
        *,
        base_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
        silent: bool = False,
    ) -> bool:
        """
        Upsert entry into embeddings + FTS tables.
        Returns True if embedding was generated, False if unavailable/skipped.
        """
        now = datetime.now(timezone.utc).isoformat()
        tags_str = " ".join(entry.tags)

        # try embedding
        embed_text_val = embed_entry_text(entry)
        vector: list[float] | None = embed_text(
            embed_text_val, base_url=base_url, model=embed_model
        )
        blob = pack_vector(vector) if vector else None
        if blob is not None:
            self.meta_set("embed_model", embed_model)
            self.meta_set("embed_dim", str(len(vector)))

        self.conn.execute(
            """INSERT INTO embeddings (entry_id, entry_type, title, tags, vector, indexed_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(entry_id) DO UPDATE SET
                 entry_type=excluded.entry_type,
                 title=excluded.title,
                 tags=excluded.tags,
                 vector=excluded.vector,
                 indexed_at=excluded.indexed_at""",
            (entry.id, entry.type, entry.title, tags_str, blob, now),
        )

        # FTS upsert (delete + insert). Text is CJK-segmented so that Chinese /
        # Japanese queries match at all — see cjk.py.
        self.conn.execute("DELETE FROM fts WHERE entry_id = ?", (entry.id,))
        self.conn.execute(
            "INSERT INTO fts (entry_id, title, body, tags) VALUES (?, ?, ?, ?)",
            (
                entry.id,
                cjk.segment(entry.title),
                cjk.segment(entry.body[:2000]),
                cjk.segment(tags_str),
            ),
        )
        self.conn.commit()
        return blob is not None

    def remove(self, entry_id: str) -> None:
        self.conn.execute("DELETE FROM embeddings WHERE entry_id = ?", (entry_id,))
        self.conn.execute("DELETE FROM fts WHERE entry_id = ?", (entry_id,))
        self.conn.commit()

    # ── FTS search ────────────────────────────────────────────────

    def fts_search(self, query: str, k: int = 50) -> list[str]:
        """Return entry_ids ranked by BM25 (FTS5).

        The query is compiled by ``cjk.build_match`` into quoted phrases: CJK
        runs match character-by-character (so ``索引`` finds ``就整個放棄索引``)
        and FTS5 syntax characters are neutralised rather than raising.

        Three tiers, most precise first, stopping at the first that hits:
          1. every chunk as a phrase, AND-ed  — exact
          2. same phrases, OR-ed              — any chunk
          3. CJK chunks split into bigrams, OR-ed — for spaceless CJK queries
             like ``索引效能問題``, which as one phrase would demand that exact
             substring and so find nothing
        """
        if cjk.build_match(query) is None:
            return []  # no usable tokens — never fall through to LIKE '%%'

        candidates = [
            cjk.build_match(query, op="AND"),
            cjk.build_match(query, op="OR"),
            cjk.build_loose_match(query),
        ]
        for match in dict.fromkeys(c for c in candidates if c):
            try:
                rows = self.conn.execute(
                    "SELECT entry_id FROM fts WHERE fts MATCH ? ORDER BY rank LIMIT ?",
                    (match, k),
                ).fetchall()
            except sqlite3.OperationalError:
                break
            if rows:
                return [r["entry_id"] for r in rows]

        # Last resort: substring scan. The stored text is segmented, so the
        # pattern must be segmented too or CJK could never match.
        pattern = f"%{cjk.segment(query).strip()}%"
        rows = self.conn.execute(
            """SELECT entry_id FROM fts
               WHERE title LIKE ? OR body LIKE ? OR tags LIKE ?
               LIMIT ?""",
            (pattern, pattern, pattern, k),
        ).fetchall()
        return [r["entry_id"] for r in rows]

    # ── vector search ─────────────────────────────────────────────

    def vector_search(
        self,
        query: str,
        *,
        base_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
        k: int = 5,
        min_score: float = 0.30,
    ) -> list[tuple[str, float]]:
        """Cosine search over **every** embedded entry.

        Returns [(entry_id, score)] sorted by score desc, or [] if ollama is
        unavailable.

        Deliberately unfiltered: an earlier version pre-filtered candidates
        through FTS and, when FTS returned nothing (which for CJK queries was
        almost always — see cjk.py), fell back to
        ``SELECT ... WHERE vector IS NOT NULL LIMIT 100``. With no ORDER BY that
        is rowid order, i.e. the 100 oldest rows ever inserted, so semantic
        search silently answered every query out of the first import batch and
        nothing written afterwards was ever reachable.
        """
        qvec = embed_text(query, base_url=base_url, model=embed_model)
        if qvec is None:
            return []
        return self.similar_to_vector(qvec, k=k, min_score=min_score)

    def similar_to_vector(
        self,
        qvec: list[float],
        *,
        k: int = 5,
        min_score: float = 0.30,
    ) -> list[tuple[str, float]]:
        """Rank all stored vectors against ``qvec`` (dot product on unit vectors).

        Rows whose dimension differs from the query are skipped and counted in
        ``last_dim_mismatch`` — that means they were embedded with a different
        model, and zipping them against the query would yield silent nonsense.
        """
        self.last_dim_mismatch = 0
        dim = len(qvec)
        want = dim * 4  # float32
        qnorm = math.sqrt(sum(x * x for x in qvec))
        if not qnorm or not math.isfinite(qnorm) or dim == 0:
            return []
        q = [x / qnorm for x in qvec]

        rows = self.conn.execute(
            "SELECT entry_id, vector FROM embeddings WHERE vector IS NOT NULL"
        ).fetchall()

        ids: list[str] = []
        blobs: list[bytes] = []
        for row in rows:
            blob = row["vector"]
            if not isinstance(blob, (bytes, bytearray)):
                continue  # unmigrated v1 JSON row
            if len(blob) != want:
                self.last_dim_mismatch += 1
                continue
            ids.append(row["entry_id"])
            blobs.append(bytes(blob))

        if not ids:
            return []

        if _np is not None:
            mat = _np.frombuffer(b"".join(blobs), dtype="<f4").reshape(len(ids), dim)
            scores = mat @ _np.asarray(q, dtype="<f4")
            return [
                (ids[i], float(scores[i]))
                for i in _np.argsort(-scores)[:k]
                if scores[i] >= min_score
            ]

        pairs = [
            (eid, sum(a * b for a, b in zip(q, unpack_vector(blob))))
            for eid, blob in zip(ids, blobs)
        ]
        pairs = [p for p in pairs if p[1] >= min_score]
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[:k]

    # ── hybrid search ─────────────────────────────────────────────

    def hybrid_search(
        self,
        query: str,
        *,
        base_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
        k: int = 5,
        min_score: float = 0.30,
        rrf_k: int = 60,
    ) -> tuple[list[str], str]:
        """Fuse BM25 and cosine rankings with Reciprocal Rank Fusion.

        Returns ``(entry_ids, mode)`` where mode is one of
        ``hybrid`` / ``semantic`` / ``fts`` / ``none``.

        Fusing instead of cascading matters: the old code took vector hits when
        it had any and only consulted FTS when it had none, so an exact keyword
        match could be shadowed by a vaguely-similar embedding — and a CJK query
        that FTS couldn't answer went straight to the broken vector fallback.
        """
        pool = max(k * 4, 20)
        fts_ids = self.fts_search(query, k=pool)
        try:
            vec_hits = self.vector_search(
                query, base_url=base_url, embed_model=embed_model,
                k=pool, min_score=min_score,
            )
        except Exception:
            vec_hits = []

        if fts_ids and vec_hits:
            mode = "hybrid"
        elif vec_hits:
            mode = "semantic"
        elif fts_ids:
            mode = "fts"
        else:
            return [], "none"

        scores: dict[str, float] = {}
        for rank, eid in enumerate(fts_ids):
            scores[eid] = scores.get(eid, 0.0) + 1.0 / (rrf_k + rank + 1)
        for rank, (eid, _s) in enumerate(vec_hits):
            scores[eid] = scores.get(eid, 0.0) + 1.0 / (rrf_k + rank + 1)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [eid for eid, _ in ranked[:k]], mode

    # ── stats ─────────────────────────────────────────────────────

    def count_indexed(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]

    def count_embedded(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM embeddings WHERE vector IS NOT NULL"
        ).fetchone()[0]

    def unembedded_ids(self) -> set[str]:
        """Indexed entries with no vector — searchable by keyword only.

        Populated whenever ollama was down at capture time; ``write_entry``
        swallows that failure so the entry lands on disk and in FTS but never in
        the semantic index until something backfills it.
        """
        return {
            r["entry_id"]
            for r in self.conn.execute(
                "SELECT entry_id FROM embeddings WHERE vector IS NULL"
            ).fetchall()
        }

    def ids_with_other_dim(self, dim: int) -> set[str]:
        """Indexed entries whose vector has a dimension other than ``dim``.

        These are dead weight: a query vector of a different width can never be
        compared against them, so they are invisible to semantic search until
        re-embedded. Detected by width rather than by the stored ``embed_model``
        marker, so stores written before that marker existed still self-heal.
        """
        return {
            r["entry_id"]
            for r in self.conn.execute(
                "SELECT entry_id FROM embeddings "
                "WHERE vector IS NOT NULL AND length(vector) != ?",
                (dim * 4,),
            ).fetchall()
        }

    def needs_reindex(self, entry_ids: set[str]) -> set[str]:
        """Return entry_ids that are not yet in the index."""
        if not entry_ids:
            return set()
        # Chunked IN-clauses: some SQLite builds cap bound parameters at 999,
        # and a store past ~1K entries would silently hit it otherwise.
        ids = list(entry_ids)
        indexed: set[str] = set()
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            placeholders = ",".join("?" * len(chunk))
            rows = self.conn.execute(
                f"SELECT entry_id FROM embeddings WHERE entry_id IN ({placeholders})",
                chunk,
            ).fetchall()
            indexed.update(r["entry_id"] for r in rows)
        return entry_ids - indexed

    def stale_ids(self, entry_ids: set[str]) -> set[str]:
        """Indexed entry_ids whose .md file no longer exists."""
        rows = self.conn.execute("SELECT entry_id FROM embeddings").fetchall()
        return {r["entry_id"] for r in rows} - entry_ids

    # ── reindex all ───────────────────────────────────────────────

    def reindex_all(
        self,
        entries: list["Entry"],
        *,
        base_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
        progress_cb=None,
    ) -> tuple[int, int]:
        """
        Upsert all entries.
        Returns (embedded_count, skipped_count).
        progress_cb(i, total, entry) called for each entry if provided.
        """
        embedded = 0
        skipped = 0
        for i, entry in enumerate(entries):
            ok = self.upsert(entry, base_url=base_url, embed_model=embed_model)
            if ok:
                embedded += 1
            else:
                skipped += 1
            if progress_cb:
                progress_cb(i + 1, len(entries), entry)
        return embedded, skipped
