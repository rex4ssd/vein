"""Entry dataclass — the core data unit of .vein/."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml

EntryType = Literal["decision", "lore", "pitfall", "reference"]
EntryStatus = Literal["active", "resolved", "superseded"]

# Body section headers by type (used by polish + display)
BODY_SECTIONS: dict[str, list[str]] = {
    "decision":  ["Why", "Trade-off"],
    "lore":      ["Observation", "Context"],
    "pitfall":   ["Symptom", "Root cause", "Fix"],
    "reference": ["Summary"],
}

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass
class Entry:
    id: str
    type: EntryType
    title: str
    tags: list[str] = field(default_factory=list)
    date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "local"
    source_url: str = ""
    source_title: str = ""
    related: list[str] = field(default_factory=list)
    status: EntryStatus = "active"
    superseded_by: str = ""
    body: str = ""
    _path: Path | None = field(default=None, repr=False, compare=False)

    # ── construction helpers ──────────────────────────────────────

    @classmethod
    def new_id(cls) -> str:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = secrets.token_hex(2)
        return f"{ts}-{suffix}"

    @classmethod
    def make(
        cls,
        type: EntryType,
        title: str,
        body: str = "",
        tags: list[str] | None = None,
        source: str = "local",
        source_url: str = "",
        source_title: str = "",
        related: list[str] | None = None,
    ) -> "Entry":
        return cls(
            id=cls.new_id(),
            type=type,
            title=title,
            tags=tags or [],
            date=datetime.now(timezone.utc),
            source=source,
            source_url=source_url,
            source_title=source_title,
            related=related or [],
            body=body,
        )

    # ── serialisation ─────────────────────────────────────────────

    def to_file_content(self) -> str:
        """Render YAML frontmatter + markdown body."""
        fm: dict = {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "tags": self.tags,
            "date": self.date.isoformat(),
            "source": self.source,
        }
        if self.source_url:
            fm["source_url"] = self.source_url
        if self.source_title:
            fm["source_title"] = self.source_title
        if self.related:
            fm["related"] = self.related
        if self.status != "active":
            fm["status"] = self.status
        if self.superseded_by:
            fm["superseded_by"] = self.superseded_by

        yaml_str = yaml.dump(fm, allow_unicode=True, sort_keys=False,
                              default_flow_style=False).rstrip()
        body = self.body.strip()
        return f"---\n{yaml_str}\n---\n\n{body}\n"

    @classmethod
    def from_file(cls, path: Path) -> "Entry":
        """Parse YAML frontmatter + markdown body from a .vein/ entry file."""
        text = path.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(text)
        if not m:
            raise ValueError(f"No YAML frontmatter found in {path}")

        fm = yaml.safe_load(m.group(1)) or {}
        body = m.group(2).strip()

        date_val = fm.get("date", datetime.now(timezone.utc))
        if isinstance(date_val, str):
            date_val = datetime.fromisoformat(date_val)
        if date_val.tzinfo is None:
            date_val = date_val.replace(tzinfo=timezone.utc)

        entry = cls(
            id=fm.get("id", path.stem),
            type=fm.get("type", "lore"),
            title=fm.get("title", ""),
            tags=fm.get("tags") or [],
            date=date_val,
            source=fm.get("source", "local"),
            source_url=fm.get("source_url", ""),
            source_title=fm.get("source_title", ""),
            related=fm.get("related") or [],
            status=fm.get("status", "active"),
            superseded_by=fm.get("superseded_by", ""),
            body=body,
        )
        entry._path = path
        return entry

    # ── display helpers ───────────────────────────────────────────

    @property
    def short_id(self) -> str:
        """Display-friendly ID: last 8 chars (date + suffix)."""
        return self.id

    @property
    def date_str(self) -> str:
        return self.date.strftime("%Y-%m-%d")

    @property
    def summary(self) -> str:
        """First non-empty line of body, or title if no body."""
        for line in self.body.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line[:120]
        return self.title

    def body_section(self, name: str) -> str:
        """Extract a named section (e.g. 'Why:') from the body."""
        pattern = re.compile(rf"^\*\*{re.escape(name)}[:\*]*(.*?)(?=\n\*\*|\Z)",
                              re.MULTILINE | re.DOTALL)
        m = pattern.search(self.body)
        if m:
            return m.group(1).strip()
        return ""
