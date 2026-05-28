"""brief.py — rule-based vein brief generation (no LLM required for MVP)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import Entry
from .store import VeinStore


def generate_brief(store: VeinStore, regen: bool = False) -> str:
    """
    Generate orientation digest from .vein/ entries.
    Rule-based (no LLM): deterministic, fast, works offline.
    Cached in .vein/BRIEF.md with TTL.
    """
    if not regen:
        cached = store.read_brief()
        if cached:
            return cached

    cfg = store.load_config()
    project_name = cfg.get("project", {}).get("name", store.root.name)
    project_desc = cfg.get("project", {}).get("description", "")
    phase = cfg.get("project", {}).get("phase", "0")

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    decisions = store.list_entries("decision", limit=8)
    active_pitfalls = [e for e in store.list_entries("pitfall")
                       if e.status == "active"]
    recent_lore = [e for e in store.list_entries("lore", status_filter=None)
                   if e.date >= week_ago][:5]
    stats = store.stats()
    total = sum(stats.values())

    lines: list[str] = []

    # ── header ──
    lines.append(f"# Project Brief — {project_name}")
    lines.append(f"_Generated {now.strftime('%Y-%m-%d %H:%M')} UTC · Phase {phase}_")
    if project_desc:
        lines.append(f"\n{project_desc}")

    # ── stats ──
    stat_parts = [f"{v} {k}s" for k, v in stats.items() if v > 0]
    if stat_parts:
        lines.append(f"\n**Lore:** {', '.join(stat_parts)} ({total} total)")

    # ── key decisions ──
    if decisions:
        lines.append("\n## Key Decisions")
        for e in decisions:
            why = e.body_section("Why")
            why_short = (why[:80] + "…") if len(why) > 80 else why
            lines.append(f"- **{e.title}**{(' — ' + why_short) if why_short else ''}")
    else:
        lines.append("\n## Key Decisions\n_No decisions logged yet._")

    # ── active pitfalls ──
    if active_pitfalls:
        lines.append("\n## ⚠ Active Pitfalls")
        for e in active_pitfalls[:5]:
            symptom = e.body_section("Symptom") or e.body_section("Root cause")
            symptom_short = (symptom[:80] + "…") if len(symptom) > 80 else symptom
            tag_str = f" `{'` `'.join(e.tags[:3])}`" if e.tags else ""
            lines.append(f"- **{e.title}**{tag_str}{(' — ' + symptom_short) if symptom_short else ''}")

    # ── recent lore ──
    if recent_lore:
        lines.append("\n## Recent Lore (last 7 days)")
        for e in recent_lore:
            lines.append(f"- {e.date_str} — {e.title}")

    # ── STATUS.md snippet ──
    status_path = store.vein_dir / "STATUS.md"
    if status_path.exists():
        status_text = status_path.read_text(encoding="utf-8").strip()
        # only include the "Current focus" section
        for line in status_text.splitlines():
            if line.startswith("## Current focus"):
                lines.append("\n## Current Focus")
                continue
            if line.startswith("## ") and "Current focus" not in line:
                break
            if "Current focus" in "\n".join(lines[-3:]):
                lines.append(line)

    # ── footer ──
    lines.append(f"\n---\n_Use `vein ask \"<question>\"` or `vein recall \"<topic>\"` for details._")

    content = "\n".join(lines) + "\n"
    store.write_brief(content)
    return content
