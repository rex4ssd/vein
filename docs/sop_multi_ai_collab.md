# SOP — Claude + Vein + Local AI 三層協作

> **目標：** 解決 Claude Code autocompact thrashing，讓 Claude / Vein / ollama 各司其職，
> 達到 1 + 1 + 1 > 3 的戰力。
>
> **讀者：** Rex 本人 + 接手的 Claude（每次 session 開頭讀一遍）
>
> **狀態追蹤：** 每個 Phase 有獨立 checklist，完成後在本檔打勾，再進下一個 Phase。

---

## 問題根源：Autocompact Thrashing

```
Autocompact is thrashing: the context refilled to the limit
within 3 turns of the previous compact, 3 times in a row.
```

**為什麼發生：**
1. CLAUDE.md / 相關 docs 一次全部載入，context 立刻半滿
2. Session 中讀了大量檔案（grep / read 太多），context 持續累積
3. Autocompact 壓縮後，下一個 task 又重新讀一批檔案 → 3 次後放棄

**根本解法不是「少讀」，而是「讀對的」：**  
每次 session 的 context 只載入 *這個 task 需要的 lore*，不是整個專案文件。
這就是 Vein 的核心存在理由。

---

## 三層 AI 分工

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Claude Code / Cowork                              │
│  角色：高層推理、程式生成、決策                              │
│  輸入：≤ 2K token 的 vein digest + 精準的目標檔案           │
│  不做：讀整個專案、處理 raw docs、embedding                  │
└──────────────────────────┬──────────────────────────────────┘
                           │ 只看 digest
┌──────────────────────────▼──────────────────────────────────┐
│  Layer 2: Vein (.vein/ + vein CLI)                          │
│  角色：專案記憶管理、lore capture / recall / digest          │
│  輸入：raw decisions、debug lore、changelog                  │
│  輸出：task-specific digest（tiered by budget）              │
└──────────────────────────┬──────────────────────────────────┘
                           │ polish / embed / summarize
┌──────────────────────────▼──────────────────────────────────┐
│  Layer 1: Local AI (ollama)                                 │
│  角色：preprocessing、embedding、capture-time polish         │
│  模型分工：                                                  │
│    llama3.2:3b    → 快速分類、簡單 Q&A、tag 建議             │
│    qwen2.5-coder:7b → 程式碼相關 lore polish、docstring      │
│    deepseek-r1:14b  → 複雜 trade-off 分析、架構推理          │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 0 — 今天就能做（不需要寫 code）

**目標：** 立刻緩解 autocompact thrashing，建立手動版三層工作流。

### 0.1 CLAUDE.md 防禦設定

- [x] CLAUDE.md ≤ 150 行（index only，不 dump 內容）← 已完成
- [ ] 建立 `.claudeignore`（排除大型 derived 檔案）

```bash
# /Users/lion/Documents/vein/.claudeignore
# 讓 Claude Code 忽略這些，不自動載入進 context
docs/competitive_landscape.md   # 長，按需讀
docs/naming.md                  # 歷史，按需讀
docs/changelog.md               # 按需 grep
.vein/index/                    # binary
.vein/cache/
__pycache__/
*.pyc
```

- [ ] CLAUDE.md §6 SOP 加一條：「每個 session 開始先明確 scope，只讀 task 相關的檔案」

### 0.2 手動版 Vein Recall（今天的 workaround）

在 Vein CLI 寫好之前，每次開新 session 的流程：

```
1. 在 chat 說明這個 session 的 task scope（一句話）
2. Claude 根據 scope grep decisions.md 的相關 D-xxx
3. 把 grep 結果（≤ 2K token）作為 context anchor
4. 完成後：把新的決策 / 雷區口頭告訴 Claude，Claude 寫進 decisions.md
```

### 0.3 Session 紀律

- [ ] 每個 session 只做**一件事**（功能邊界清楚）
- [ ] 大任務拆成子任務，每個子任務獨立 session
- [ ] Session 結束前說 "ca"，commit 後再開新 session
- [ ] 遇到 context 快滿：`/clear` → 重新說 scope → 繼續（不要硬撐）

### Phase 0 驗收
- [ ] 連續 5 個 session 沒有 autocompact thrashing
- [ ] .claudeignore 有效（用 Claude Code 確認大檔不被自動載入）

---

## Phase 1 — Vein CLI v0.1（核心三指令）

**目標：** `vein init / log / recall` 能跑，手動版 workaround 升級為 CLI。

### 1.1 要實作的功能

```
vein init
  → 建立 .vein/ 目錄結構
  → 寫入預設 config.yaml（含 digest_budget: 2000、ollama model 設定）
  → 建立 .vein/.gitignore

vein log <type> "<message>"
  → type: decision / lore / pitfall / reference
  → 呼叫 ollama（qwen2.5-coder:7b）polish message
  → 存進 .vein/decisions/YYYYMMDD-HHMMSS.md
  → 格式包含：title / body / tags / source / source_url / date

vein brief
  → 掃 .vein/ 最近 10 條 lore + active pitfalls + config overview
  → 呼叫 ollama（llama3.2:3b）生成 ~800 token orientation brief
  → cache 進 .vein/BRIEF.md（TTL 1hr 或有新 vein log 就失效）
  → 用途：新 session 開頭一次，取代 Claude 的 grep × 5~10 定向動作

vein ask "<question>"
  → 比 recall 更口語，專門回答「為什麼 X 是這樣」類問題
  → 內部走 semantic search，輸出直接回答問句的格式
  → .vein/ 沒有答案時明確告知 "no lore found"，讓 Claude 才去 grep

vein recall "<query>"
  → 呼叫 ollama（nomic-embed-text）embed query
  → sqlite-vec 查最近 top-5 lore entries
  → 呼叫 ollama（llama3.2:3b）生成 ≤ 2K token digest
  → 印到 stdout（可 pipe 進 pbcopy）
```

### 1.2 ollama 模型分工（config.yaml）

```yaml
version: 1
recall:
  digest_budget: 2000        # token limit for Claude context
  embed_model: nomic-embed-text
  digest_model: llama3.2:3b  # 快、省資源
  top_k: 5

log:
  polish_model: qwen2.5-coder:7b  # code-aware polish

analyze:
  model: deepseek-r1:14b          # 複雜 trade-off
```

### 1.3 Session 工作流（CLI 版）

```bash
# ── Session 開始（任何問題規模都做這一步）──
vein brief | pbcopy
# 貼進 Claude context，~800 token，取代所有初始 grep

# ── 小問題 ──
vein ask "為什麼 X 這樣設計？"
# .vein/ 有答案 → 直接給 Claude，0 grep
# .vein/ 沒有 → Claude grep → 完成後 vein log

# ── 複雜工作 ──
vein recall "這個 session 的 task scope" | pbcopy
# 貼進 Claude context 作為 task-specific anchor

# 做事...

# ── Session 結束，記錄決策 ──
vein log decision "為什麼選 X 不選 Y — 因為..."
vein log lore "踩到的雷：Z 在某條件下會壞，預防方法是..."

# commit
git add -A && git commit -F -
```

### 1.4 Cowork 使用方式（Phase 1）

Cowork session 開頭的 SOP：
```
1. 執行：vein brief → 得到 orientation brief (~800 token)
2. 把 brief 貼進 Cowork chat 作為第一則訊息（取代大量 grep）
3. 說明 task
4. 簡單問題：先 vein ask，.vein/ 有答案就不用讓 Claude grep
5. 完成後讓 Claude 用 vein log 記錄新 lore
```

### Phase 1 驗收
- [ ] `vein init` 在 Lode 專案跑成功，`.vein/` 結構正確
- [ ] `vein log decision "..."` 存進檔，ollama polish 有效
- [ ] `vein recall "sqlite"` 能找回 D-002 的 sqlite-vec 決策
- [ ] digest ≤ 2000 token（用 tiktoken 驗證）
- [ ] Dogfood on Vein 本身：用 `vein log` 記第一條真實決策

---

## Phase 2 — Vein CLI v0.2（自動化 + Git 整合）

**目標：** 減少手動操作，lore capture 融入 git workflow。

### 2.1 要實作的功能

```
vein auto [--from-diff HEAD~1 HEAD]
  → 分析 git diff
  → 呼叫 deepseek-r1:14b 判斷：這個 diff 有 trade-off 嗎？
  → 如果有：輸出建議 log message，問要不要存進 .vein/
  → 可設定「複雜度門檻」（diff > N 行才問）

vein review "<query>"
  → 比 recall 更深：不只找 lore，還做跨條目的矛盾檢查
  → 「這個決策跟 D-002 有衝突嗎？」
  → 輸出：related lore + potential conflicts + suggested questions

vein status
  → 最近 7 天的 lore 活動
  → 未解決的 pitfall 數量
  → dogfood 進度（目標 ≥ 10 條 / 2 週）
```

### 2.2 Git Hook 整合

```bash
# .git/hooks/post-commit（vein init 自動安裝）
#!/bin/bash
DIFF_SIZE=$(git diff HEAD~1 HEAD --stat | tail -1 | grep -oP '\d+ insertion')
if [ "$DIFF_SIZE" -gt 50 ]; then
    echo "🌿 vein: significant commit detected, run 'vein auto' to capture lore?"
fi
```

### 2.3 Tiered Budget（D-011 實作）

```bash
vein recall "query"              # 預設 2K（cloud LLM / 省 token）
vein recall --budget 32k "query" # 本機 13B（qwen2.5-coder:7b）
vein recall --budget 200k "query"# 本機 70B+
vein recall --raw "query"        # 不壓縮，全量（未來 405B）
```

### Phase 2 驗收
- [ ] `vein auto` 分析 Lode 的一個 real commit，建議有意義
- [ ] Git hook 在 Vein / Lode 兩個 repo 裝好並有效
- [ ] `vein status` 顯示正確的 dogfood 進度
- [ ] Lode dogfood ≥ 10 條 entries，retrieval 品質主觀評分 ≥ 7/10

---

## Phase 3 — Vein MCP Server（Platform Independence）

**目標：** Vein 成為任何 MCP-compatible tool 的 portable memory layer，
徹底解決「換 IDE 記憶消失」的問題。

### 3.1 要實作的功能

```
vein serve [--port 3000]
  → 啟動 MCP server
  → 暴露 tools：
      vein_recall(query, budget?)    → digest string
      vein_log(type, message, tags?) → entry_id
      vein_review(query)             → analysis string
      vein_status()                  → stats object

vein serve --install
  → 自動寫入 Claude Code / Cursor 的 MCP config
  → 驗證連線
```

### 3.2 Claude Code 整合方式

```json
// ~/.claude/mcp_servers.json
{
  "vein": {
    "command": "vein",
    "args": ["serve", "--stdio"],
    "env": {
      "VEIN_PROJECT": "/Users/lion/Documents/lode"
    }
  }
}
```

Session 開頭不再需要手動 paste digest：
Claude Code 自動透過 MCP 呼叫 `vein_recall`，context 精準。

### 3.3 Cowork 整合方式

Cowork 的 system prompt 可以加：
```
每次開始 task，先呼叫 vein_recall("<task scope>") 取得 lore digest，
再開始工作。完成後呼叫 vein_log 記錄新決策。
```

### Phase 3 驗收
- [ ] `vein serve` 在 Claude Code 連線成功
- [ ] 一次完整的 Claude Code session：自動 recall → 工作 → 自動 log，全程不手動 paste
- [ ] 在 Cowork 和 Claude Code 共用同一個 `.vein/`，兩邊看到一致的 lore
- [ ] Flip `rex4ssd/vein` public（Phase 3 完成 = D-008 flip 條件達成）

---

## Phase 4 — Community & Ecosystem（開源後）

**目標：** Vein 從個人工具變成有生態的 OSS。

### 4.1 Shared Lore Templates

```bash
vein template list                    # 看可用 template
vein template import python-cli       # 匯入 Python CLI 專案的常見決策
vein template import tauri-rust-app   # 匯入 Tauri app 的常見決策
```

Template 是社群貢獻的「starter lore」，例如：
- 「為什麼選 sqlite-vec 不選 chromadb」（通用 Python AI 專案）
- 「為什麼選 MIT 不選 AGPL」（OSS 專案）
- 「為什麼選 Click 不選 argparse」（Python CLI）

### 4.2 `vein.dev` / `vein.app` 公開頁

- template library browser
- 安裝文件（brew / pipx）
- 案例展示（Vein dogfood on Vein 的截圖）

### Phase 4 驗收
- [ ] ≥ 3 個 community template 可用
- [ ] `vein template import` 正確匯入，不覆蓋本地 custom lore
- [ ] GitHub star ≥ 100（外部驗證）

---

## 當前 Phase 狀態

| Phase | 狀態 | 起始條件 |
|---|---|---|
| Phase 0 | 🟡 **進行中** | 今天開始 |
| Phase 1 | ⬜ 未開始 | Phase 0 驗收完成 |
| Phase 2 | ⬜ 未開始 | Phase 1 驗收完成 |
| Phase 3 | ⬜ 未開始 | Phase 2 dogfood ≥ 2 週 |
| Phase 4 | ⬜ 未開始 | Phase 3 驗收 + repo public |

---

## 快速參考：每次 session 的 context 策略

```
Context budget 分配（Phase 1 最佳實踐）：

情況 A — 開新視窗 / 方向不明確
  [vein brief]              ~800 token   ← 一次定向，取代所有 grep
  [CLAUDE.md index]         ~500 token   ← 固定（可省）
  [目標檔案內容]            ~3000 token  ← task-specific
  [chat history]            ~1000 token  ← 累積
  ─────────────────────────────────────
  合計                      ~5300 token  ✓

情況 B — 已知 task scope（複雜工作）
  [vein brief]              ~800 token   ← 開頭定向
  [vein recall digest]      ~2000 token  ← task-specific anchor
  [目標檔案內容]            ~4000 token  ← task-specific
  [chat history]            ~1000 token  ← 累積
  ─────────────────────────────────────
  合計                      ~7800 token  ✓

情況 C — 小問題
  [vein ask 答案]           ~500 token   ← 直接給答案，0 grep
  ─────────────────────────────────────
  合計                      ~500 token   ✓✓✓

不應該出現：
❌ 新 session 不跑 vein brief 直接開始 grep
❌ vein ask 有答案卻還讓 Claude 去 grep 確認
❌ 讀 competitive_landscape.md（長，非必要）
❌ 讀 changelog.md 全文（grep 就好）
❌ 重複 read 剛才寫過的檔案
❌ 同一個 session 處理超過 2 個不相關的 task

黃金原則：
  vein ask 先 → 沒答案才 grep → grep 完一定 vein log
```

---

## 相關 Decisions

- D-001：為什麼用 Python（快速 iteration）
- D-009：語言策略（Go rewrite 觸發條件）
- D-010：MCP server 是 platform independence 的戰略核心
- D-011：Tiered digest 架構（大記憶 AI Server 相容）
