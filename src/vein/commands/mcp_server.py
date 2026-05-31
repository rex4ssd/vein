"""vein mcp — MCP server exposing vein tools to any MCP client.

Usage:
  vein mcp                     # stdio transport (Claude Desktop default)
  vein mcp --transport sse     # SSE transport (browser / remote)

Claude Desktop config (~/.claude.json or claude_desktop_config.json):
  {
    "mcpServers": {
      "vein-lode": {
        "command": "vein",
        "args": ["mcp"],
        "cwd": "/Users/lion/Documents/lode"
      }
    }
  }

Tools exposed:
  vein_recall  — semantic + FTS search over .vein/ lore
  vein_log     — capture a decision, lore, pitfall, or reference
  vein_brief   — get the session orientation primer (~800 tokens)
  vein_status  — project name + entry counts
"""

from __future__ import annotations

import sys
from pathlib import Path

import click


def _require_mcp():
    try:
        from mcp.server.fastmcp import FastMCP  # noqa: F401
    except ImportError:
        click.echo(
            "MCP package not installed.\n"
            "Run: pip install 'lode-vein[mcp]'",
            err=True,
        )
        sys.exit(1)


def _build_server():
    """Build and return the FastMCP server instance."""
    from mcp.server.fastmcp import FastMCP
    from ..core.store import VeinStore

    mcp = FastMCP(
        "vein",
        instructions=(
            "Vein is the decision & debug lore archive for this project. "
            "Call vein_brief() at the start of every session to orient yourself. "
            "Call vein_recall() to look up why something was built a certain way. "
            "Call vein_log() when you or the user make an architectural decision, "
            "find a non-obvious bug cause, or discover an API quirk worth remembering."
        ),
    )

    # ── recall ────────────────────────────────────────────────────────────

    @mcp.tool()
    def vein_recall(query: str, limit: int = 5) -> str:
        """Search project lore — decisions, pitfalls, API quirks, workarounds.

        Call this whenever you want to understand *why* something in the codebase
        looks the way it does, or before making a change that might conflict with
        a past decision.

        Args:
            query: Natural language question or keyword (e.g. "DMA callback",
                   "why sqlite", "rate limit workaround")
            limit: Max results to return (default 5)

        Returns:
            Matching lore entries as markdown, or "No results" if nothing found.
        """
        store = VeinStore.require()
        cfg = store.load_config()
        base_url   = cfg.get("model", {}).get("base_url",   "http://localhost:11434")
        embed_model = cfg.get("model", {}).get("embed_model", "nomic-embed-text")
        min_score  = cfg.get("capture", {}).get("min_cosine_threshold", 0.30)

        entries = []
        mode = "keyword"

        # 1. vector search
        try:
            idx = store.open_index()
            hits = idx.vector_search(
                query, base_url=base_url, embed_model=embed_model,
                k=limit, min_score=min_score,
            )
            idx.close()
            if hits:
                entries = [store.read_entry(eid) for eid, _ in hits]
                mode = "semantic"
        except Exception:
            pass

        # 2. FTS fallback
        if not entries:
            try:
                idx = store.open_index()
                ids = idx.fts_search(query, k=limit)
                idx.close()
                if ids:
                    entries = [store.read_entry(eid) for eid in ids]
                    mode = "fts"
            except Exception:
                pass

        # 3. grep fallback
        if not entries:
            entries = [e for e, _ in store.grep_entries(query, limit=limit)]

        if not entries:
            return f"No lore found for: {query}\nTip: run `vein reindex` to rebuild the search index."

        lines = [f"## Vein recall: `{query}` ({mode}, {len(entries)} results)\n"]
        for e in entries:
            tag_str = f" · `{'` `'.join(e.tags[:4])}`" if e.tags else ""
            status_note = f" ⚠ {e.staleness_note}" if e.staleness_note else (
                " [superseded]" if e.status == "superseded" else ""
            )
            lines.append(f"### [{e.type}] {e.title}{status_note}")
            lines.append(f"_id: {e.id} · {e.date_str[:10]}{tag_str}_\n")
            if e.body:
                lines.append(e.body)
            lines.append("")

        return "\n".join(lines)

    # ── log ───────────────────────────────────────────────────────────────

    @mcp.tool()
    def vein_log(
        type: str,
        message: str,
        tags: list[str] | None = None,
    ) -> str:
        """Capture a lore entry into .vein/ — no polish, immediate write.

        Call this after:
        - Making an architectural decision ("why X not Y")
        - Finding a non-obvious bug cause or workaround
        - Discovering an external API quirk
        - Hitting a pitfall worth remembering

        Args:
            type: Entry type — one of: decision, lore, pitfall, reference
                  (or short alias: d, l, p, r)
            message: The raw knowledge to capture. Be specific — include
                     the *why*, not just the *what*. One to three sentences.
            tags:    Optional list of tags (e.g. ["sqlite", "fts5", "index"])

        Returns:
            Confirmation with the saved entry ID and path.
        """
        _type_aliases = {
            "d": "decision", "dec": "decision",
            "l": "lore",
            "p": "pitfall", "pit": "pitfall",
            "r": "reference", "ref": "reference",
        }
        resolved = _type_aliases.get(type.lower().strip(), type.lower().strip())
        valid = ("decision", "lore", "pitfall", "reference")
        if resolved not in valid:
            return f"Unknown type '{type}'. Valid: {', '.join(valid)} (or d/l/p/r)"

        from ..core.models import Entry
        from ..core.polish import fallback_polish

        store = VeinStore.require()

        draft = fallback_polish(message, resolved)  # type: ignore[arg-type]
        if tags:
            existing = draft.get("tags") or []
            for t in tags:
                if t not in existing:
                    existing.append(t)
            draft["tags"] = existing

        entry = Entry.make(
            type=resolved,          # type: ignore[arg-type]
            title=draft.get("title", message[:80]),
            body=draft.get("body", message),
            tags=draft.get("tags", []),
            source="mcp",
        )
        path = store.write_entry(entry)

        return (
            f"✓ Saved [{resolved}] {entry.id}\n"
            f"  Title: {entry.title}\n"
            f"  Path:  {path.relative_to(store.root)}\n"
            f"  Tags:  {', '.join(entry.tags) or '(none)'}\n\n"
            f"Tip: run `vein reindex` to make this entry searchable via recall."
        )

    # ── brief ─────────────────────────────────────────────────────────────

    @mcp.tool()
    def vein_brief() -> str:
        """Get the project orientation digest — call this at the start of every session.

        Returns a ~800-token summary of:
        - Key architectural decisions
        - Active pitfalls to avoid
        - Recent lore (last 7 days)
        - Current project focus

        No arguments needed. Result is cached (TTL 1 hour, invalidated on new log).
        """
        from ..core.brief import generate_brief
        store = VeinStore.require()
        return generate_brief(store)

    # ── status ────────────────────────────────────────────────────────────

    @mcp.tool()
    def vein_status() -> str:
        """Get project name and .vein/ entry counts.

        Returns a one-line summary: project name, phase, and how many
        decisions / lore / pitfalls / references are stored.
        """
        store = VeinStore.require()
        cfg = store.load_config()
        name  = cfg.get("project", {}).get("name", store.root.name)
        phase = cfg.get("project", {}).get("phase", "0")
        stats = store.stats()
        total = sum(stats.values())
        parts = [f"{v} {k}s" for k, v in stats.items() if v > 0]
        stat_str = ", ".join(parts) if parts else "no entries yet"
        return f"{name} (Phase {phase}) — {total} lore entries: {stat_str}"

    return mcp


# ── CLI command ───────────────────────────────────────────────────────────────

@click.command("mcp")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    show_default=True,
    help="Transport protocol. stdio = Claude Desktop / CLI. sse = browser / remote.",
)
@click.option("--port", default=8765, show_default=True, help="Port for SSE transport.")
@click.option("--project", default="", help="Override project root path.")
def cmd_mcp(transport: str, port: int, project: str) -> None:
    """Start the Vein MCP server.

    \b
    Examples:
      vein mcp                          # stdio (Claude Desktop)
      vein mcp --transport sse          # SSE on :8765 (remote / browser)
      vein mcp --project /path/to/repo  # explicit project root

    \b
    Claude Desktop config:
      Add to ~/.config/claude/claude_desktop_config.json:
      {
        "mcpServers": {
          "vein-myproject": {
            "command": "vein",
            "args": ["mcp"],
            "cwd": "/path/to/your/project"
          }
        }
      }
    """
    _require_mcp()

    # optionally override project root via env so VeinStore.require() finds it
    if project:
        import os
        os.chdir(project)

    mcp_server = _build_server()

    if transport == "stdio":
        mcp_server.run(transport="stdio")
    else:
        click.echo(f"Starting SSE server on http://localhost:{port}/sse …")
        mcp_server.run(transport="sse", port=port)
