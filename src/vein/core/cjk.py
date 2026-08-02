"""cjk.py — CJK-aware tokenisation for the FTS5 index.

**The problem.** SQLite's stock ``unicode61`` tokenizer splits on Unicode
category: every letter (``L*``) and digit (``N*``) is a token character, and
everything else is a separator. Han ideographs and Kana are category ``Lo``, so
a whole run of them collapses into **one token** — Chinese and Japanese have no
inter-word spaces, so in practice the token is "the entire clause between two
punctuation marks":

    "SQLite 索引雷:LIKE 有 ESCAPE 就整個放棄索引"
      → tokens: sqlite, 索引雷, like, 有, escape, 就整個放棄索引

A user searching ``索引`` matches *neither* ``索引雷`` nor ``就整個放棄索引``.
Measured against this repo's corpus, CJK query recall was 0–54%; realistic
multi-word queries ("為什麼用 sqlite") returned **zero** rows.

**The fix.** Index each CJK character as its own token (``segment``), and turn
each whitespace-delimited chunk of the query into an FTS5 *phrase* of the same
per-character tokens (``build_match``). A phrase requires consecutive tokens, so
``"索 引"`` matches exactly the documents containing the substring 索引 — full
recall, no precision loss, and no third-party tokenizer to ship.

Only scripts that are actually written without spaces are split (Han, Kana,
and their extension planes). Hangul is deliberately excluded: Korean *is*
space-delimited, so ``unicode61`` already handles it correctly and splitting it
would destroy word boundaries.
"""

from __future__ import annotations

import re

# Ranges of scripts written without inter-word spaces.
_CJK_RANGES: tuple[tuple[int, int], ...] = (
    (0x3040, 0x30FF),    # Hiragana + Katakana
    (0x3400, 0x4DBF),    # CJK Unified Ideographs Ext A
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0xFF66, 0xFF9F),    # Halfwidth Katakana
    (0x20000, 0x2FA1F),  # CJK Unified Ideographs Ext B–F + Compat Supplement
)

# Runs of letters/digits, mirroring what unicode61 treats as token characters.
# ``[^\W_]`` is \w minus underscore; unicode61 treats "_" as a separator.
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def is_cjk(ch: str) -> bool:
    """True if ``ch`` belongs to a script written without inter-word spaces."""
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def segment(text: str) -> str:
    """Space out CJK characters so ``unicode61`` emits one token each.

    Applied to title/body/tags *before* they go into the FTS table. Idempotent:
    re-segmenting already-segmented text only adds redundant whitespace, which
    the tokenizer collapses.

        >>> segment("就整個放棄索引 sqlite")
        ' 就  整  個  放  棄  索  引  sqlite'
    """
    if not text:
        return text
    return "".join(f" {ch} " if is_cjk(ch) else ch for ch in text)


def tokenize(text: str) -> list[str]:
    """Split ``text`` into the tokens a segmented FTS index would contain.

    CJK characters become individual tokens; runs of Latin/digits stay whole.

        >>> tokenize("MCP伺服器")
        ['MCP', '伺', '服', '器']
    """
    out: list[str] = []
    for run in _TOKEN_RE.findall(text):
        buf: list[str] = []
        for ch in run:
            if is_cjk(ch):
                if buf:
                    out.append("".join(buf))
                    buf = []
                out.append(ch)
            else:
                buf.append(ch)
        if buf:
            out.append("".join(buf))
    return out


def build_match(query: str, *, op: str = "AND") -> str | None:
    """Compile a user query into an FTS5 MATCH expression, or None if empty.

    Each whitespace-delimited chunk becomes one double-quoted phrase, so
    ``sqlite-vec`` matches the adjacent pair (sqlite, vec) and ``索引`` matches
    the adjacent pair (索, 引). Quoting every chunk also neutralises FTS5 syntax
    characters (``-`` ``*`` ``:`` ``^`` ``(`` ``)`` ``NEAR`` …) that previously
    raised ``OperationalError`` and dumped the search into a LIKE scan.

        >>> build_match("為什麼用 sqlite-vec")
        '"為 什 麼 用" AND "sqlite vec"'
    """
    phrases: list[str] = []
    for chunk in query.split():
        toks = tokenize(chunk)
        if toks:
            phrases.append('"' + " ".join(toks) + '"')
    if not phrases:
        return None
    return f" {op} ".join(phrases)


def build_loose_match(query: str) -> str | None:
    """Compile a query into OR'd CJK **bigrams** — the recall tier.

    ``build_match`` turns each whitespace chunk into one phrase, which is exactly
    right for a chunk the user meant as one word. But Chinese is written without
    inter-word spaces, so a natural query like ``索引效能問題`` arrives as a
    single 6-character chunk and the phrase form demands that exact substring —
    it will not find a document about 索引 and another about 效能.

    Splitting into overlapping 2-character phrases matches how Chinese words are
    actually shaped, and lets BM25 rank documents hitting more of them first:

        >>> build_loose_match("索引效能")
        '"索 引" OR "引 效" OR "效 能"'

    Boundary-straddling bigrams (``引效``) are near-misses that rarely match
    anything, so they cost recall nothing. Latin tokens become standalone terms,
    which also unglues mixed chunks like ``為什麼用sqlite``.

    This is the last tier before giving up, so it trades precision for reach on
    purpose — ``fts_search`` only reaches it when the phrase tiers found nothing.
    """
    terms: list[str] = []

    def flush(run: list[str]) -> None:
        if len(run) == 1:
            terms.append(f'"{run[0]}"')
        elif len(run) == 2:
            terms.append(f'"{run[0]} {run[1]}"')
        elif run:
            terms.extend(f'"{a} {b}"' for a, b in zip(run, run[1:]))

    for chunk in query.split():
        run: list[str] = []
        for tok in tokenize(chunk):
            if len(tok) == 1 and is_cjk(tok):
                run.append(tok)
            else:
                flush(run)
                run = []
                terms.append(f'"{tok}"')
        flush(run)

    if not terms:
        return None
    return " OR ".join(dict.fromkeys(terms))
