"""brief.py — rule-based vein brief generation (no LLM required for MVP)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .store import VeinStore


def _detail(text: str, title: str, limit: int = 80) -> str:
    """Trim ``text`` for display, or drop it when it just repeats the title.

    The capture paths that don't run an LLM (MCP ``vein_log``, and
    ``fallback_polish`` generally) store the raw message as ``**Why:** <msg>``
    and set the title to a truncation of that same message. Rendering
    ``**{title}** — {why}`` then prints the same sentence twice, which on a
    store captured mostly through MCP roughly doubles the brief for no
    information — and the brief exists to fit a token budget.
    """
    text = " ".join(text.split())
    if not text:
        return ""
    head = " ".join(title.split())[:40].rstrip("…")
    if head and (text.startswith(head) or head.startswith(text[:40])):
        return ""
    return text[:limit] + "…" if len(text) > limit else text


def _current_focus(status_text: str) -> list[str]:
    """Body lines of the ``## Current focus`` section of STATUS.md.

    The previous inline version compared against ``"Current focus"`` while
    appending a ``"## Current Focus"`` header, so the guard never fired and the
    section shipped empty in every brief ever generated. It also used the last
    three output lines as its state, which capped the section at three lines and
    broke outright if any other ``##`` heading preceded Current focus.
    """
    out: list[str] = []
    inside = False
    for line in status_text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = "current focus" in line.lower()
            continue
        if inside:
            out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return out


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

    # One pass over the store. This used to be three list_entries calls plus a
    # stats() glob; each call re-parses every file's YAML and only then applies
    # `limit`, so generating a brief parsed 430 decisions to display 8 (~0.5s).
    entries = store.list_entries(status_filter=None)
    by_type: dict[str, list] = {}
    for e in entries:
        by_type.setdefault(e.type, []).append(e)

    decisions = [e for e in by_type.get("decision", []) if e.status == "active"][:8]
    active_pitfalls = [e for e in by_type.get("pitfall", []) if e.status == "active"]
    recent_lore = [e for e in by_type.get("lore", []) if e.date >= week_ago][:5]

    # Counts reflect what is actually readable — an entry whose frontmatter
    # won't parse is invisible to every other section, so counting it here
    # would only make the brief disagree with itself.
    stats = {t: len(v) for t, v in sorted(by_type.items()) if v}
    total = len(entries)

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
            why = _detail(e.body_section("Why"), e.title)
            lines.append(f"- **{e.title}**{(' — ' + why) if why else ''}")
    else:
        lines.append("\n## Key Decisions\n_No decisions logged yet._")

    # ── active pitfalls ──
    if active_pitfalls:
        lines.append("\n## ⚠ Active Pitfalls")
        for e in active_pitfalls[:5]:
            raw = e.body_section("Symptom") or e.body_section("Root cause")
            symptom = _detail(raw, e.title)
            tag_str = f" `{'` `'.join(e.tags[:3])}`" if e.tags else ""
            lines.append(f"- **{e.title}**{tag_str}{(' — ' + symptom) if symptom else ''}")

    # ── recent lore ──
    if recent_lore:
        lines.append("\n## Recent Lore (last 7 days)")
        for e in recent_lore:
            lines.append(f"- {e.date_str} — {e.title}")

    # ── STATUS.md snippet ──
    status_path = store.vein_dir / "STATUS.md"
    if status_path.exists():
        focus = _current_focus(status_path.read_text(encoding="utf-8"))
        if focus:
            lines.append("\n## Current Focus")
            lines.extend(focus)

    # ── footer ──
    lines.append(f"\n---\n_Use `vein ask \"<question>\"` or `vein recall \"<topic>\"` for details._")

    content = "\n".join(lines) + "\n"
    store.write_brief(content)
    return content
