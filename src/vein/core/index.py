"""index.py — SQLite-backed embedding + FTS index for .vein/

Schema:
  embeddings  (entry_id PK, entry_type, title, tags, vector JSON, indexed_at)
  fts5        (entry_id, title, body, tags)  — virtual FTS5 table

Phase 0: cosine similarity in Python (no sqlite-vec).
Phase 1: ALTER TABLE + sqlite-vec extension for ANN.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .embed import cosine_sim, embed_entry_text, embed_text, top_k_similar

if TYPE_CHECKING:
    from .models import Entry

_DDL = """
CREATE TABLE IF NOT EXISTS embeddings (
    entry_id   TEXT PRIMARY KEY,
    entry_type TEXT NOT NULL,
    title      TEXT NOT NULL,
    tags       TEXT NOT NULL DEFAULT '',
    vector     TEXT,           -- JSON array of floats, NULL if not embedded
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


class VeinIndex:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._setup()

    def _setup(self) -> None:
        self.conn.executescript(_DDL)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

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
        vector_json = json.dumps(vector) if vector else None

        self.conn.execute(
            """INSERT INTO embeddings (entry_id, entry_type, title, tags, vector, indexed_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(entry_id) DO UPDATE SET
                 entry_type=excluded.entry_type,
                 title=excluded.title,
                 tags=excluded.tags,
                 vector=excluded.vector,
                 indexed_at=excluded.indexed_at""",
            (entry.id, entry.type, entry.title, tags_str, vector_json, now),
        )

        # FTS upsert (delete + insert)
        self.conn.execute("DELETE FROM fts WHERE entry_id = ?", (entry.id,))
        self.conn.execute(
            "INSERT INTO fts (entry_id, title, body, tags) VALUES (?, ?, ?, ?)",
            (entry.id, entry.title, entry.body[:2000], tags_str),
        )
        self.conn.commit()
        return vector is not None

    def remove(self, entry_id: str) -> None:
        self.conn.execute("DELETE FROM embeddings WHERE entry_id = ?", (entry_id,))
        self.conn.execute("DELETE FROM fts WHERE entry_id = ?", (entry_id,))
        self.conn.commit()

    # ── FTS search ────────────────────────────────────────────────

    def fts_search(self, query: str, k: int = 50) -> list[str]:
        """Return entry_ids ranked by BM25 (FTS5)."""
        # escape special FTS5 chars
        safe = query.replace('"', '""').replace("'", "''")
        try:
            rows = self.conn.execute(
                "SELECT entry_id FROM fts WHERE fts MATCH ? ORDER BY rank LIMIT ?",
                (safe, k),
            ).fetchall()
            return [r["entry_id"] for r in rows]
        except sqlite3.OperationalError:
            # FTS query syntax error → fall back to LIKE
            rows = self.conn.execute(
                """SELECT entry_id FROM fts
                   WHERE title LIKE ? OR body LIKE ? OR tags LIKE ?
                   LIMIT ?""",
                (f"%{query}%", f"%{query}%", f"%{query}%", k),
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
        fts_pre_filter: int = 100,
    ) -> list[tuple[str, float]]:
        """
        Hybrid search: FTS5 pre-filter → cosine re-rank.
        Returns [(entry_id, score)] sorted by score desc.
        Returns [] if ollama unavailable.
        """
        # 1. embed query
        qvec = embed_text(query, base_url=base_url, model=embed_model)
        if qvec is None:
            return []

        # 2. FTS pre-filter to get candidates
        candidate_ids = self.fts_search(query, k=fts_pre_filter)

        # 3. if no FTS hits, use all indexed entries
        if not candidate_ids:
            rows = self.conn.execute(
                "SELECT entry_id FROM embeddings WHERE vector IS NOT NULL LIMIT ?",
                (fts_pre_filter,),
            ).fetchall()
            candidate_ids = [r["entry_id"] for r in rows]

        if not candidate_ids:
            return []

        # 4. load vectors for candidates
        placeholders = ",".join("?" * len(candidate_ids))
        rows = self.conn.execute(
            f"SELECT entry_id, vector FROM embeddings "
            f"WHERE entry_id IN ({placeholders}) AND vector IS NOT NULL",
            candidate_ids,
        ).fetchall()

        candidates = []
        for row in rows:
            try:
                vec = json.loads(row["vector"])
                candidates.append((row["entry_id"], vec))
            except (json.JSONDecodeError, TypeError):
                continue

        if not candidates:
            return []

        # 5. cosine re-rank
        return top_k_similar(qvec, candidates, k=k, min_score=min_score)

    # ── stats ─────────────────────────────────────────────────────

    def count_indexed(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]

    def count_embedded(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM embeddings WHERE vector IS NOT NULL"
        ).fetchone()[0]

    def needs_reindex(self, entry_ids: set[str]) -> set[str]:
        """Return entry_ids that are not yet in the index."""
        if not entry_ids:
            return set()
        placeholders = ",".join("?" * len(entry_ids))
        rows = self.conn.execute(
            f"SELECT entry_id FROM embeddings WHERE entry_id IN ({placeholders})",
            list(entry_ids),
        ).fetchall()
        indexed = {r["entry_id"] for r in rows}
        return entry_ids - indexed

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
