# Vein — Data Format & Capture Pipeline

> **核心命題：retrieval quality 在 write time 決定，不在 search time。**

---

## 1. `.vein/` 目錄結構

```
.vein/
  config.yaml              ← 專案設定（model backend、project name、phase）
  STATUS.md                ← 當前 phase / TODO（人類 + AI 手動維護）
  decisions/
    20260527-143022.md     ← 每條 entry 一個 file，timestamp ID
    20260528-090015.md
  lore/
    20260528-110000.md
  pitfalls/
    20260527-160000.md
  references/
    20260527-170000.md
  index/                   ← generated，.gitignore
    embeddings.db          ← sqlite-vec，nomic-embed-text vectors
    fts.db                 ← sqlite FTS5 全文索引
  BRIEF.md                 ← generated，.gitignore，TTL=1h
```

**設計原則：**
- `decisions/` / `lore/` / `pitfalls/` / `references/` 進 git → project asset
- `index/` + `BRIEF.md` 不進 git → generated，各機器各自建
- 每條 entry 獨立一個 `.md` 檔 → git diff 清楚，merge conflict 不互相影響

---

## 2. Entry Schema（YAML frontmatter + Markdown body）

```markdown
---
id: 20260527-143022          # timestamp，唯一 key，不改
type: decision               # decision | lore | pitfall | reference
title: "DMA API uses callback not polling"
tags: [dma, hal, systemc, callback, host-build]
date: 2026-05-27T14:30:22+08:00
source: local                # local | git-hook | mcp | import-doxygen | import-file
source_url: ""               # web clipper 或 import 來源 URL
source_title: ""
related: [20260526-120000]   # 其他 entry 的 id（timestamp）
status: active               # active | resolved | superseded
superseded_by: ""            # 若 superseded，填新 entry id
---

**Why:** SystemC DMA model is event-driven (sc_event); polling would
busy-wait in HOST build, wasting simulation time. MP build's IRQ handler
maps naturally to callback semantics.

**Trade-off:** Callbacks require careful ISR context management. Never
call `hal_dma_submit` from within an existing callback — re-entrant
callback hell.

**How to avoid pitfall:** Use `hal_dma_submit_deferred()` if you need
to queue from callback context.
```

### Body 的三個 section（type 決定哪些必填）

| type | 必填 section | 選填 |
|---|---|---|
| `decision` | **Why:** + **Trade-off:** | How to avoid pitfall |
| `lore` | **Observation:** | Context, Source |
| `pitfall` | **Symptom:** + **Root cause:** + **Fix:** | Reproduction seed, Affected paths |
| `reference` | **Summary:** + source_url | Why relevant |

Section 不強制格式，但 LLM polish prompt 會引導生成這個結構。

---

## 3. Capture Pipeline — 這是 Vein 的核心

### 3.1 `vein log`（主路徑）

```
User input (raw prose)
        │
        │  例：vein log decision "dma用callback不用polling因為systemc是event-driven"
        ▼
┌─────────────────────────────────────────┐
│           ollama polish                 │
│  model: qwen2.5-coder:7b               │
│                                         │
│  prompt template:                       │
│  "You are a technical lore archivist.  │
│   Given this raw note from an engineer: │
│   <raw>                                 │
│   {input}                               │
│   </raw>                                │
│                                         │
│   Generate a structured lore entry:    │
│   1. title: imperative, ≤10 words      │
│   2. type: decision/lore/pitfall/ref   │
│   3. tags: 3-5, snake_case             │
│   4. body: Why / Trade-off sections    │
│   5. pitfall_flag: any pitfall here?   │
│                                         │
│   Output JSON only."                   │
└────────────────┬────────────────────────┘
                 │
                 ▼
         structured draft (JSON)
                 │
                 │  convert → YAML frontmatter + Markdown body
                 ▼
         ┌───────────────────┐
         │  interactive diff  │  ← 終端顯示 diff，user 按 y/n/e(dit)
         └────────┬──────────┘
                  │ confirmed
                  ▼
         write to .vein/{type}/{id}.md
                  │
                  │  background task
                  ▼
         generate embedding (nomic-embed-text)
         → upsert into index/embeddings.db
         → upsert into index/fts.db
                  │
                  ▼
         invalidate BRIEF.md cache
```

**為什麼 interactive diff 不可省：**
LLM 有時會：
- 誤判 type（把 lore 判成 decision）
- tags 偏差（加了不相關的 tag）
- 把兩個概念混成一條

這些在 write time 修正的成本很低（5 秒），在 recall time 出問題的成本很高（找不到、找錯）。所以「確認步驟」是 quality gate，不是 UX 障礙。

---

### 3.2 Polish Prompt 設計細節

**System prompt（qwen2.5-coder:7b）：**

```
You are a technical lore archivist for software/hardware projects.
Your job: take raw engineer notes and convert them into structured,
retrievable lore entries.

Rules:
- title: imperative form, ≤10 words, no jargon expansion
- type: decision (a choice was made between alternatives),
        lore (an observation/behavior worth knowing),
        pitfall (a trap that can cause bugs or wasted time),
        reference (an external resource with context)
- tags: 3-5 tags, snake_case, prefer specific over generic
  (prefer "dma_callback" over "architecture")
- body sections depend on type:
  decision → Why: (forces/constraints) + Trade-off: (what you give up)
  lore → Observation: + Context: (when does this matter)
  pitfall → Symptom: + Root cause: + Fix: + (optional) Reproduction:
  reference → Summary: (why this matters to THIS project)
- related: IDs of entries this connects to (leave empty if unsure)
- If the input contains multiple distinct decisions, output an array.

Output: JSON only. No prose outside JSON.
```

**Few-shot examples（固定 inject 進 prompt）：**

```json
// input: "sqlite不能在多個goroutine同時寫"
{
  "type": "pitfall",
  "title": "SQLite rejects concurrent writes from multiple goroutines",
  "tags": ["sqlite", "concurrency", "goroutine", "database"],
  "body": {
    "Symptom": "database is locked error under concurrent write load",
    "Root cause": "SQLite's default journal mode (DELETE) uses file-level lock; concurrent writers serialize or fail",
    "Fix": "Use WAL mode: PRAGMA journal_mode=WAL; or serialize writes via a single writer goroutine",
    "Reproduction": "goroutine × 10, each INSERT 100 rows simultaneously"
  }
}
```

---

### 3.3 Embedding Strategy（`vein recall` 的底層）

**什麼要 embed：**
```
embed_text = f"{title}\n{tags joined by space}\n{body first 400 chars}"
```
- title + tags 提高 precision（避免 false match）
- body 前 400 字提高 recall（捕捉細節）
- 不 embed 整個 body：長文會稀釋 important signal

**Model：** `nomic-embed-text`（768 dim，ollama 可用，品質 vs size 均衡）

**Index：** `sqlite-vec`（Phase 0 輕量，不依賴外部 vector DB）
- cosine similarity
- top-K = 5（`vein recall` 預設）
- KNN + FTS5 hybrid：先 FTS5 filter（speed），再 vector re-rank（precision）

**Hybrid search 流程：**
```
vein recall "DMA timeout"
        │
        │  FTS5: find entries containing "DMA" OR "timeout" → candidate set
        ▼
  candidate set（top-50 by BM25）
        │
        │  vector re-rank: embed query → cosine sim → top-5
        ▼
  top-5 entries
        │
        │  llama3.2:3b: synthesize into ≤2K token digest
        ▼
  output to stdout (or pipe to Claude / Gemini)
```

FTS5 先 filter 讓 vector search 只在 50 條裡算，不是全庫掃——這在 `.vein/` 有 10K+ entries 時還是夠快。

---

### 3.4 `vein brief` 生成邏輯

```
.vein/ all entries (full scan)
        │
        │  rule-based 篩選：
        │  - decisions: sort by date desc, top 10
        │  - pitfalls: status=active only
        │  - lore: last 7 days
        │  - references: tagged "pinned" only
        ▼
  raw brief material (~3K tokens)
        │
        │  llama3.2:3b compress:
        │  "Summarize each entry in 1 sentence.
        │   Keep: title, type, key trade-off or symptom.
        │   Output: markdown, ≤800 tokens total."
        ▼
  BRIEF.md (cached, TTL=1h, invalidated on any vein log)
```

**Why rule-based 先，LLM 後（不是全 LLM）：**
- rule-based 保證 active pitfalls 一定出現（LLM 可能 drop 它）
- LLM 只做 compression，不做 selection → 輸出更可預測
- 速度：rule filter 是 microseconds；LLM 只處理 3K → 0.5-1 秒

---

### 3.5 Import Pipeline（Phase 2）

#### `vein import --from-doxygen`

```
Doxygen XML
        │  xml.etree parse
        ▼
@pre/@post/@note/@warning → raw text list
        │
        │  qwen2.5-coder:7b batch:
        │  "For each annotation, is it lore-worthy?
        │   Output: [{keep: true/false, type, title, body_draft}]"
        ▼
interactive confirmation list (y/n/e per item)
        │
        ▼
batch vein log → .vein/
```

#### `vein import --from-file` (MarkItDown)

```
PDF / DOCX / XLSX / HTML
        │  markitdown → markdown string
        ▼
full markdown text
        │
        │  qwen2.5-coder:7b chunk + extract:
        │  "List decisions/trade-offs in this document.
        │   Each as: {type, title, body_draft}"
        │  (chunked at 2K tokens with 200 token overlap)
        ▼
candidate list
        │
interactive confirmation
        │
        ▼
batch vein log → .vein/
```

---

## 4. Quality gates 總覽

| 階段 | Gate | 目的 |
|---|---|---|
| Write time | interactive diff confirm | 防止 LLM 誤判 type / tag |
| Write time | title length check (≤15 words) | 強迫簡潔，embedding signal 更強 |
| Write time | duplicate detection (FTS5 title match ≥ 80%) | 防重複 entry |
| Index time | embedding 不為空 | 防 embedding failure silently skip |
| Recall time | top-5 score threshold (cosine ≥ 0.3) | 沒有好結果就說「找不到」，不硬給 |
| Brief time | pitfall active count check | 若 active pitfall > 10，warn user to review |

---

## 5. Config.yaml（完整 schema）

```yaml
version: 1

project:
  name: "vein"
  description: "Decision & debug lore archive for AI-assisted development"
  phase: "0"
  status_file: ".vein/STATUS.md"

model:
  backend: ollama            # ollama | rapid-mlx
  base_url: http://localhost:11434
  embed_model: nomic-embed-text
  digest_model: llama3.2:3b     # vein brief, vein recall synthesis
  polish_model: qwen2.5-coder:7b # vein log polish, vein import
  analyze_model: deepseek-r1:14b # vein auto (git hook heavy analysis)

capture:
  interactive: true          # false = auto-accept polish output (CI mode)
  brief_ttl_seconds: 3600
  min_cosine_threshold: 0.30

index:
  path: .vein/index/
  fts_candidate_k: 50        # FTS5 first-pass candidate count
  recall_top_k: 5            # final top-K returned by vein recall
```

---

## 6. 關鍵設計決策（why this format）

**為什麼 per-entry 一個 file，而不是 all-in-one JSONL 或 SQLite：**
- git diff 以 file 為單位 → 每條 lore 獨立 diff，reviewer 看得清楚
- merge conflict 只發生在同一條 entry 同時被修改（rare）
- markdown 人類可讀，不需要工具才能看
- LLM 直接 read file，不需要 parsing layer

**為什麼 YAML frontmatter 而不是純 JSON / pure markdown：**
- frontmatter 是 Jekyll / Hugo / Obsidian 通用格式，生態工具都認識
- body 保持 markdown → LLM 生成自然，人類讀也自然
- 機器 parse frontmatter（pyyaml），人類讀 body

**為什麼 timestamp ID 而不是 D-001 sequential：**
- timestamp 不需要中央計數器，多機器、多工具並行 capture 不 conflict
- sequential ID（D-001）在兩個 branch 同時新增 entry 時必有衝突
- timestamp 排序天然代表 capture time，有意義
- `related` 欄位用 timestamp ID 引用，仍然 human-readable

**為什麼 capture-time polish 而不是 query-time expansion：**
- 一次 polish，多次搜尋（amortize LLM cost）
- 搜尋時 user 在等，polish 時 user 在工作
- structured entry 的 embedding quality > raw prose embedding（measured in gbrain's research）
- polish 失敗可以在 confirm step 立刻修正；query-time 失敗沒有 feedback loop
