"""Entry dataclass — the core data unit of .vein/."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar, Literal

import yaml

EntryType = Literal["decision", "lore", "pitfall", "reference"]
EntryStatus = Literal["active", "resolved", "superseded"]
# How fast a claim decays from correct → wrong as the world/AI changes (D-026).
# external-fact: vendor APIs, platform rules, "current best practice" — decay fast.
# internal-invariant: our own architecture rationale — decay slowly.
Volatility = Literal["external-fact", "internal-invariant", "unknown"]

# Re-validation TTL (days) by volatility class. Past this, an active entry is
# flagged "may be stale" in recall — it doesn't lie about being true forever.
VOLATILITY_TTL_DAYS: dict[str, int] = {
    "external-fact":      180,   # ~6 months
    "unknown":            365,   # ~1 year (un-classified default)
    "internal-invariant": 1095,  # ~3 years (rarely flagged)
}

# Body section headers by type (used by polish + display)
BODY_SECTIONS: dict[str, list[str]] = {
    "decision":  ["Why", "Trade-off"],
    "lore":      ["Observation", "Context"],
    "pitfall":   ["Symptom", "Root cause", "Fix"],
    "reference": ["Summary"],
}

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_dt(value) -> datetime:
    """Coerce a frontmatter date value (str or datetime) to tz-aware UTC."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


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
    volatility: str = "unknown"
    verified_at: datetime | None = None
    body: str = ""
    _path: Path | None = field(default=None, repr=False, compare=False)

    # ── construction helpers ──────────────────────────────────────

    # Ids created in the same second share their timestamp prefix, so
    # uniqueness rests entirely on the 2-byte suffix — a batch of 20 collides
    # with ~0.3% probability (birthday bound), and a collision means the second
    # entry's file silently overwrites the first. Remember the ids issued for
    # the current second and re-roll on repeat; the set resets on clock tick.
    _issued_second: ClassVar[str] = ""
    _issued_ids: ClassVar[set[str]] = set()

    @classmethod
    def new_id(cls) -> str:
        while True:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            if ts != cls._issued_second:
                cls._issued_second = ts
                cls._issued_ids.clear()
            candidate = f"{ts}-{secrets.token_hex(2)}"
            if candidate not in cls._issued_ids:
                cls._issued_ids.add(candidate)
                return candidate

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
        volatility: str = "unknown",
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
            volatility=volatility,
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
        if self.volatility and self.volatility != "unknown":
            fm["volatility"] = self.volatility
        if self.verified_at:
            fm["verified_at"] = self.verified_at.isoformat()

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

        date_val = _parse_dt(fm.get("date", datetime.now(timezone.utc)))

        verified_raw = fm.get("verified_at")
        verified_at = _parse_dt(verified_raw) if verified_raw else None

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
            volatility=fm.get("volatility", "unknown"),
            verified_at=verified_at,
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

    # ── temporal truth-maintenance (D-026) ────────────────────────

    @property
    def effective_date(self) -> datetime:
        """Last point this entry was known good: verified_at, else date."""
        d = self.verified_at or self.date
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

    @property
    def age_days(self) -> int:
        return max(0, (datetime.now(timezone.utc) - self.effective_date).days)

    @property
    def ttl_days(self) -> int:
        return VOLATILITY_TTL_DAYS.get(self.volatility, VOLATILITY_TTL_DAYS["unknown"])

    @property
    def is_stale(self) -> bool:
        """Active entry older than its volatility TTL — may have decayed to wrong."""
        return self.status == "active" and self.age_days > self.ttl_days

    @property
    def staleness_note(self) -> str:
        if not self.is_stale:
            return ""
        months = self.age_days // 30
        return f"captured ~{months}mo ago, may be stale"

    @property
    def recall_demotion(self) -> int:
        """Sort key for recall: superseded entries sink to the bottom (a newer
        entry replaced them); active/resolved keep their relevance order."""
        return 1 if self.status == "superseded" else 0

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
