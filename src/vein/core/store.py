"""Store — .vein/ path resolution, entry I/O, and listing."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Iterator

import yaml

from .models import Entry, EntryType

VEIN_DIR = ".vein"
ENTRY_DIRS: dict[str, str] = {
    "decision":  "decisions",
    "lore":      "lore",
    "pitfall":   "pitfalls",
    "reference": "references",
}
CONFIG_FILENAME = "config.yaml"
STATUS_FILENAME = "STATUS.md"
BRIEF_FILENAME = "BRIEF.md"

# Default .vein/config.yaml written by vein init
_DEFAULT_CONFIG = """\
version: 1

project:
  name: "{name}"
  description: ""
  phase: "0"

model:
  backend: ollama
  base_url: http://localhost:11434
  embed_model: nomic-embed-text
  digest_model: llama3.2:3b
  polish_model: qwen2.5-coder:7b
  analyze_model: deepseek-r1:14b

capture:
  interactive: true
  brief_ttl_seconds: 3600
  min_cosine_threshold: 0.30

index:
  path: .vein/index/
  fts_candidate_k: 50
  recall_top_k: 5
"""

_DEFAULT_STATUS = """\
# Status — {name}

**Phase:** 0
**Started:** {date}

## Current focus

(fill in)

## Blocked / waiting

(fill in)
"""


class VeinStore:
    """Encapsulates all .vein/ I/O for one project."""

    def __init__(self, root: Path):
        self.root = root
        self.vein_dir = root / VEIN_DIR

    # ── root discovery ────────────────────────────────────────────

    @classmethod
    def find(cls, start: Path | None = None) -> "VeinStore | None":
        """Walk up from start (default: cwd) to find the nearest .vein/."""
        cwd = (start or Path.cwd()).resolve()
        for parent in [cwd, *cwd.parents]:
            if (parent / VEIN_DIR).is_dir():
                return cls(parent)
        return None

    @classmethod
    def require(cls, start: Path | None = None) -> "VeinStore":
        store = cls.find(start)
        if store is None:
            raise RuntimeError(
                "No .vein/ directory found. Run `vein init` first."
            )
        return store

    # ── initialisation ────────────────────────────────────────────

    def init(self, name: str, force: bool = False) -> bool:
        """Create .vein/ structure. Returns True if created, False if already exists."""
        if self.vein_dir.exists() and not force:
            return False

        self.vein_dir.mkdir(exist_ok=True)
        (self.vein_dir / "index").mkdir(exist_ok=True)

        for subdir in ENTRY_DIRS.values():
            (self.vein_dir / subdir).mkdir(exist_ok=True)

        cfg_path = self.vein_dir / CONFIG_FILENAME
        if not cfg_path.exists() or force:
            from datetime import date
            cfg_path.write_text(
                _DEFAULT_CONFIG.format(name=name),
                encoding="utf-8",
            )

        status_path = self.vein_dir / STATUS_FILENAME
        if not status_path.exists() or force:
            from datetime import date
            status_path.write_text(
                _DEFAULT_STATUS.format(name=name, date=date.today().isoformat()),
                encoding="utf-8",
            )

        gitignore = self.vein_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("index/\nBRIEF.md\nWALKER.json\n", encoding="utf-8")

        return True

    # ── config ────────────────────────────────────────────────────

    def load_config(self) -> dict:
        cfg_path = self.vein_dir / CONFIG_FILENAME
        if not cfg_path.exists():
            return {}
        return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    # ── write ─────────────────────────────────────────────────────

    def write_entry(
        self,
        entry: Entry,
        *,
        auto_index: bool = True,
        base_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
    ) -> Path:
        subdir = ENTRY_DIRS.get(entry.type, "lore")
        dest_dir = self.vein_dir / subdir
        dest_dir.mkdir(exist_ok=True)
        path = dest_dir / f"{entry.id}.md"
        path.write_text(entry.to_file_content(), encoding="utf-8")
        entry._path = path
        # invalidate brief cache
        self._invalidate_brief()
        # update index
        if auto_index:
            try:
                idx = self.open_index()
                idx.upsert(entry, base_url=base_url, embed_model=embed_model, silent=True)
                idx.close()
            except Exception:
                pass  # index failure is non-fatal
        return path

    def _invalidate_brief(self) -> None:
        brief = self.vein_dir / BRIEF_FILENAME
        if brief.exists():
            brief.unlink()

    # ── read ──────────────────────────────────────────────────────

    def read_entry(self, id_or_path: str | Path) -> Entry:
        if isinstance(id_or_path, Path):
            return Entry.from_file(id_or_path)
        # search by id prefix
        for entry in self.iter_entries():
            if entry.id.startswith(id_or_path):
                return entry
        raise KeyError(f"Entry not found: {id_or_path}")

    def iter_entries(
        self,
        type_filter: EntryType | None = None,
        status_filter: str | None = "active",
    ) -> Iterator[Entry]:
        """Yield Entry objects, newest first."""
        dirs = ([ENTRY_DIRS[type_filter]] if type_filter else list(ENTRY_DIRS.values()))
        paths: list[Path] = []
        for d in dirs:
            p = self.vein_dir / d
            if p.is_dir():
                paths.extend(sorted(p.glob("*.md"), reverse=True))

        for path in paths:
            try:
                entry = Entry.from_file(path)
                if status_filter and entry.status != status_filter:
                    continue
                yield entry
            except Exception:
                continue

    def list_entries(
        self,
        type_filter: EntryType | None = None,
        status_filter: str | None = "active",
        limit: int | None = None,
    ) -> list[Entry]:
        entries = list(self.iter_entries(type_filter, status_filter))
        if limit:
            entries = entries[:limit]
        return entries

    # ── delete ───────────────────────────────────────────────────

    def delete_entry(self, entry: Entry) -> bool:
        """Delete an entry's .md file and remove it from the index.

        Returns True if the file existed and was deleted.
        Safe to call with an entry whose _path is None or already gone.
        """
        path = entry._path
        if path is None:
            # try to reconstruct path from id + type
            subdir = ENTRY_DIRS.get(entry.type, "lore")
            path = self.vein_dir / subdir / f"{entry.id}.md"

        deleted = False
        if path and path.exists():
            path.unlink()
            deleted = True

        # remove from search index (best-effort)
        try:
            idx = self.open_index()
            idx.remove(entry.id)
            idx.close()
        except Exception:
            pass

        if deleted:
            self._invalidate_brief()
        return deleted

    # ── stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for type_key, subdir in ENTRY_DIRS.items():
            d = self.vein_dir / subdir
            result[type_key] = len(list(d.glob("*.md"))) if d.is_dir() else 0
        return result

    # ── index ─────────────────────────────────────────────────────

    def open_index(self) -> "VeinIndex":
        """Open (or create) the SQLite index.

        Primary location is ``.vein/index/vein.db``. Some filesystems —
        network mounts (NFS/SMB), FUSE, and certain synced/Docker volumes —
        cannot host a SQLite DB: fcntl byte-range locking fails and SQLite
        raises ``OperationalError: disk I/O error``. The index is generated
        and gitignored, so on failure we transparently relocate it to a
        per-repo directory under the OS cache dir. ``idx.relocated_to`` is
        set when this fallback is used so callers can surface a note.
        """
        from .index import VeinIndex
        db_path = self.vein_dir / "index" / "vein.db"
        db_path.parent.mkdir(exist_ok=True)
        try:
            return VeinIndex(db_path)
        except sqlite3.OperationalError:
            fallback = self._fallback_index_path()
            fallback.parent.mkdir(parents=True, exist_ok=True)
            idx = VeinIndex(fallback)
            idx.relocated_to = fallback
            return idx

    def _fallback_index_path(self) -> Path:
        """Per-repo SQLite index location for filesystems that can't host one.

        Keyed by a hash of the absolute .vein/ path so distinct repos never
        collide. Prefers ``$XDG_CACHE_HOME``/``~/.cache``; falls back to the
        system temp dir if the cache dir itself isn't writable.
        """
        import hashlib
        import os
        import tempfile

        key = hashlib.sha1(str(self.vein_dir.resolve()).encode()).hexdigest()[:12]
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
        try:
            target = Path(base) / "vein" / key
            target.mkdir(parents=True, exist_ok=True)
        except OSError:
            target = Path(tempfile.gettempdir()) / "vein-index" / key
            target.mkdir(parents=True, exist_ok=True)
        return target / "vein.db"

    # ── brief cache ───────────────────────────────────────────────

    def read_brief(self) -> str | None:
        """Return cached brief if still valid (within TTL), else None."""
        brief_path = self.vein_dir / BRIEF_FILENAME
        if not brief_path.exists():
            return None
        cfg = self.load_config()
        ttl = cfg.get("capture", {}).get("brief_ttl_seconds", 3600)
        import time
        age = time.time() - brief_path.stat().st_mtime
        if age > ttl:
            return None
        return brief_path.read_text(encoding="utf-8")

    def write_brief(self, content: str) -> None:
        (self.vein_dir / BRIEF_FILENAME).write_text(content, encoding="utf-8")

    # ── search (simple grep — Phase 0) ────────────────────────────

    def grep_entries(self, query: str, limit: int = 10) -> list[tuple[Entry, int]]:
        """
        Simple keyword search across title + body.
        Returns [(entry, score)] sorted by score desc.
        score = number of query terms matched (case-insensitive).
        """
        terms = [t.lower() for t in query.split() if t.strip()]
        if not terms:
            return []

        results: list[tuple[Entry, int]] = []
        for entry in self.iter_entries(status_filter=None):
            haystack = f"{entry.title} {' '.join(entry.tags)} {entry.body}".lower()
            score = sum(1 for t in terms if t in haystack)
            if score > 0:
                results.append((entry, score))

        results.sort(key=lambda x: (-x[1], x[0].date), reverse=False)
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]


def cross_project_search(
    query: str,
    *,
    exclude_root: Path | None = None,
    limit: int = 5,
) -> list[tuple[str, Entry, int]]:
    """Keyword-search every registered .vein/ except ``exclude_root``.

    Returns ``[(project_name, entry, score)]`` sorted by score desc. Uses grep
    (not the per-project SQLite index) so it needs no ollama and works even when
    a project's index hasn't been built. This powers ``recall -x`` / ``ask -x``.
    """
    from . import registry

    excl = exclude_root.resolve() if exclude_root else None
    out: list[tuple[str, Entry, int]] = []
    for root in registry.roots():
        if excl is not None and root.resolve() == excl:
            continue
        store = VeinStore(root)
        name = (store.load_config().get("project", {}) or {}).get("name") or root.name
        for entry, score in store.grep_entries(query, limit=limit):
            out.append((name, entry, score))

    out.sort(key=lambda x: x[2], reverse=True)
    return out[:limit] if limit else out
