# Vein CLI 使用手冊

> Lode finds the code. **Vein remembers the why.**

---

## 安裝

```bash
cd /Users/lion/Documents/vein
pip install -e ".[dev]" --break-system-packages
vein --version
```

---

## 全命令一覽

```
vein init       — 初始化 .vein/ 目錄結構
vein log        — 捕捉一筆 decision / lore / pitfall / reference
vein status     — 顯示 .vein/ 統計 + 近期 entries
vein brief      — 生成 / 讀取 orientation digest（給 AI session 用）
vein ask        — 關鍵字搜尋（即時，no index）
vein recall     — 語意搜尋（FTS5 + embedding re-rank，需 vein reindex）
vein list       — 列出所有 entries，支援 filter
vein reindex    — 重建 SQLite 搜尋 index
vein import     — 批量匯入現有 decisions.md 或任意 .md
```

---

## 完整工作流程

```
                 ┌─────────────────────────────────────────┐
                 │         開發中發現值得記錄的事             │
                 └──────────────┬──────────────────────────┘
                                │
                    vein log <type> "<raw note>"
                                │
                    ┌───────────▼───────────┐
                    │  ollama polish         │
                    │  (qwen2.5-coder:7b)   │  ← 離線時走 fallback
                    │  raw → structured JSON │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Interactive confirm   │  ← --yes 可跳過
                    │  y / n / e(edit)      │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  write .vein/type/    │
                    │  id.md (YAML + body)  │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  auto embed + index   │  ← ollama 離線 silent skip
                    │  (nomic-embed-text)   │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  BRIEF.md 失效        │
                    │  (下次 vein brief 重生)│
                    └───────────────────────┘
```

---

## `vein init`

在當前目錄初始化 `.vein/`：

```bash
vein init                    # 使用目錄名作為專案名
vein init "my-project"       # 指定名稱
vein init --force            # 重建（覆寫 config + STATUS）
```

建立結構：

```
.vein/
  config.yaml        ← AI model 設定 + capture 參數
  STATUS.md          ← 當前 focus（手動維護）
  .gitignore         ← 排除 index/ 和 BRIEF.md
  decisions/
  lore/
  pitfalls/
  references/
  index/             ← SQLite db（gitignored）
```

---

## `vein log`

捕捉一筆 lore entry：

```bash
# 完整寫法
vein log decision "選 callback 不選 polling，因為 SystemC 是 event-driven"
vein log pitfall  "SQLite 在多 goroutine 並發寫入會 database locked"
vein log lore     "nomic-embed-text 輸出 768 維向量，normalize 後 cosine = dot"
vein log reference "https://docs.ollama.ai/api"

# 縮寫（d/l/p/r）
vein log d "用 WAL mode 解決 SQLite 鎖"
vein log p "HAL timer callback 不能在 ISR 外呼叫"

# 常用選項
vein log d "..." --tag hal --tag timer   # 手動加 tag（polish 也會自動加）
vein log d "..." --no-polish             # 跳過 ollama，直接存 raw
vein log d "..." --yes                   # 跳過互動確認
vein log d "..." --source-url "https://..." # 附來源 URL
```

### Polish 流程

```
raw text
  │
  ▼ POST /api/chat (qwen2.5-coder:7b)
  │ system prompt + few-shots + your text
  │
  ▼ JSON response
  {
    "type": "decision",
    "title": "Use WAL mode to avoid SQLite write locks",
    "tags": ["sqlite", "wal", "concurrency"],
    "body": "**Why:** ...\n\n**Trade-off:** ..."
  }
  │
  ▼ Interactive confirm (y/n/e)
  │
  ▼ write .vein/decisions/20260528-HHMMSS-XXXX.md
```

---

## `vein status`

```bash
vein status         # 顯示計數 + active pitfalls + 最近 10 entries
vein status --all   # 包含 superseded / archived
```

輸出範例：

```
myproject  Phase 0  /path/to/.vein

  type        count   active
 ────────────────────────────
  decision       12       11
  lore            7        7
  pitfall         3        3
  reference       2        2

  total          24

Active pitfalls:
  ⚠ SQLite locked under concurrent writes  (20260528-...)
  ⚠ HAL timer not re-entrant              (20260527-...)

Recent entries:
  decision   2026-05-28  Use FTS+embed for recall
  lore       2026-05-28  nomic-embed-text outputs 768-dim vectors
```

---

## `vein brief`

為新 AI session 生成 ≤2K token 的 context digest：

```bash
vein brief          # 讀 cache（TTL 1h）或即時生成
vein brief --regen  # 強制重新生成（忽略 cache）
vein brief --raw    # 直接 print，不走 rich formatter
```

### 生成邏輯（rule-based，不需 LLM）

```
.vein/ entries
  │
  ▼ 選取規則
  ├── decisions: 最新 8 筆，取 Why section
  ├── pitfalls:  status=active 全部，加 ⚠ 標記
  ├── lore:      最近 7 天內的
  └── STATUS.md: 取 "Current focus" section
  │
  ▼ 組合成 markdown digest
  │
  ▼ 寫入 .vein/BRIEF.md（TTL = config brief_ttl_seconds，預設 3600s）
```

**用法：在每個新 AI session 開頭貼入 `vein brief` 輸出**，讓 Claude / Gemini 快速了解專案狀態，不用重複 grep 整個 codebase。

---

## `vein ask`

即時關鍵字搜尋（不需 index，直接 grep files）：

```bash
vein ask "DMA callback"
vein ask "timer" --type pitfall
vein ask "uart" -n 3            # 只顯示前 3 筆
vein ask "hal" --raw            # 輸出原始 markdown（可 pipe）
```

---

## `vein recall`

語意搜尋（FTS5 BM25 + nomic-embed-text cosine re-rank）：

```bash
vein recall "concurrent write issue"
vein recall "why polling bad" --budget 32k
vein recall "timer" --fts-only     # 只用 FTS5，跳過 embedding
vein recall "dma" -n 10
```

### 搜尋優先順序

```
呼叫 vein recall "query"
  │
  ▼ 嘗試 vector search（需 ollama + nomic-embed-text）
  │   embed query → FTS5 pre-filter top-50 → cosine re-rank top-k
  │
  ├── 成功 → 顯示 semantic 結果
  │
  ▼ fallback: FTS5 search（SQLite only，不需 ollama）
  │
  ├── 成功 → 顯示 FTS 結果
  │
  ▼ fallback: grep（直接掃 .md 檔）
  │
  └── 顯示 keyword 結果
```

**tip:** 第一次使用或新增 entries 後，執行 `vein reindex` 讓 FTS5 + embedding 生效。

---

## `vein list`

```bash
vein list                         # 全部 active entries
vein list --type pitfall          # 只看 pitfalls
vein list --status all            # 含 superseded / archived
vein list --tag dma               # tag 含 "dma" 的
vein list -n 20                   # 最多 20 筆
vein list --ids-only              # 只印 id，可 pipe 用
```

輸出範例（rich table）：

```
 ID                     Type       Title                        Tags          Date
 ─────────────────────────────────────────────────────────────────────────────────
 20260528-101259-78f1   decision   Use FTS+embed for recall                   2026
 20260528-101308-15f4   lore       nomic-embed-text 768-dim                   2026
 20260528-101305-e320   pitfall    SQLite locked concurrent                   2026
```

---

## `vein reindex`

重建 `.vein/index/vein.db` 的 FTS5 + embedding index：

```bash
vein reindex                    # 增量 upsert 全部 entries
vein reindex --force            # 先 drop 再重建
vein reindex --type pitfall     # 只 reindex pitfalls
```

**什麼時候跑：**
- 第一次 setup（ollama 還沒跑、或剛 `ollama pull nomic-embed-text`）
- 手動編輯 `.vein/*.md` 後
- 換了 embed model 後（需 `--force`）
- `vein recall` 搜不到預期結果

需要 ollama 跑 embedding：

```bash
ollama serve
ollama pull nomic-embed-text    # 首次下載
vein reindex
```

Embedding 失敗（ollama 離線）時，entries 仍會進 FTS5 index（全文搜尋仍可用），
`vein recall --fts-only` 依然有效。

---

## `vein import`

從現有 docs 批量匯入：

```bash
# 從 decisions.md（自動識別 D-xxx 格式）
vein import docs/decisions.md
vein import docs/decisions.md --dry-run   # 先預覽，不實際寫入

# 從任意 .md（作為一筆 lore entry 匯入）
vein import docs/architecture.md --type lore

# 不要即時 embed（大量匯入時加速，之後再 vein reindex）
vein import docs/decisions.md --no-index
```

### decisions.md 解析規則

```
### D-001 — 選 Python 不選 Rust/Go    ← 識別為 D-xxx block header
**Date:** 2026-05-26                  ← 作為 entry date
body 段落...                           ← body 內容
                                      ← 遇到下一個 D-xxx 或 H1/H2 停止
```

偵測邏輯：
- 有 `### D-\d+` pattern → `decisions.md` 格式，每個 block 一筆 entry
- 無上述 pattern → plain markdown，整份檔案作為一筆 lore entry

---

## config.yaml 說明

`vein init` 產生的預設 config：

```yaml
version: 1

project:
  name: "myproject"
  description: ""
  phase: "0"

model:
  backend: ollama
  base_url: http://localhost:11434
  embed_model: nomic-embed-text          # 768-dim
  digest_model: llama3.2:3b             # brief 壓縮（未來）
  polish_model: qwen2.5-coder:7b        # log 時 polish
  analyze_model: deepseek-r1:14b        # recall 綜合（未來）

capture:
  interactive: true          # vein log 是否互動確認
  brief_ttl_seconds: 3600    # BRIEF.md cache TTL（1h）
  min_cosine_threshold: 0.30 # recall 最低 cosine 分數門檻

index:
  path: .vein/index/
  fts_candidate_k: 50        # FTS5 pre-filter 取前 N 筆
  recall_top_k: 5            # 最終回傳筆數
```

---

## 典型日常流程

### 開始新 session

```bash
# 貼給 AI 當 context
vein brief

# 或查特定問題
vein recall "DMA timeout"
```

### 開發途中記筆記

```bash
# 決策
vein log d "選 WAL mode 不選 journal mode，因為 SystemC write pattern 是 single writer"

# 踩雷
vein log p "HAL DMA submit 不能在 callback 內呼叫，會 re-entrant deadlock"

# 知識
vein log l "nomic-embed-text normalize 後 dot product = cosine，省一次 sqrt"
```

### 收工 / 切換 session

```bash
vein status        # 確認今天新增了什麼
vein brief --regen # 重生 digest 給下次用
git add .vein/decisions .vein/lore .vein/pitfalls .vein/references
git commit -m "vein: update lore"
```

### 批量匯入歷史決策

```bash
vein import docs/decisions.md --dry-run   # 先確認解析正確
vein import docs/decisions.md --no-index  # 匯入但暫不 embed
vein reindex                              # 統一 embed
vein status                              # 驗證
```
