"""embed.py — embedding generation via ollama (nomic-embed-text).

Phase 0: pure Python cosine similarity, no sqlite-vec dependency.
Phase 1: swap to sqlite-vec for proper ANN when corpus > 10K entries.
"""

from __future__ import annotations

import math
from typing import Sequence


# ── ollama embedding call ─────────────────────────────────────────

def embed_text(
    text: str,
    *,
    base_url: str = "http://localhost:11434",
    model: str = "nomic-embed-text",
    timeout: float = 30.0,
) -> list[float] | None:
    """
    Embed a text string via ollama.
    Returns float list (768-dim for nomic-embed-text), or None if unavailable.
    """
    try:
        import httpx
    except ImportError:
        return None
    try:
        resp = httpx.post(
            f"{base_url}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("embedding")
    except Exception:
        return None


def embed_entry_text(entry) -> str:
    """Compose the text to embed for an entry (title + tags + first 400 chars of body)."""
    parts = [entry.title]
    if entry.tags:
        parts.append(" ".join(entry.tags))
    if entry.body:
        parts.append(entry.body[:400])
    return "\n".join(parts)


# ── cosine similarity ─────────────────────────────────────────────

def cosine_sim(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity. Returns 0.0 for mismatched dimensions.

    Vectors of different width come from different embedding models and are not
    comparable. This used to ``zip`` them, which truncates to the shorter
    operand and yields a plausible-looking score computed from an arbitrary
    prefix — a silent wrong answer rather than a visible failure.
    """
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


def top_k_similar(
    query_vec: list[float],
    candidates: list[tuple[str, list[float]]],  # (entry_id, vector)
    k: int = 5,
    min_score: float = 0.0,
) -> list[tuple[str, float]]:
    """Return top-k (entry_id, score) sorted by cosine similarity desc."""
    scored = [(eid, cosine_sim(query_vec, vec)) for eid, vec in candidates]
    scored = [(eid, s) for eid, s in scored if s >= min_score]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
