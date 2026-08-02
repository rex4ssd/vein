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

`vein --help` 只顯示 5 個核心命令，進階命令用 `vein more` 查。

### 核心（`vein --help` 看到的）

```
vein init          — 初始化 .vein/ 目錄結構
vein log           — 捕捉一筆 decision / lore / pitfall / reference
vein recall        — 語意搜尋（BM25 + embedding RRF 融合，CJK-aware）
vein brief         — orientation digest，給 AI session 用
vein status        — 統計 + 近期 entries 一覽
```

### 進階（`vein more` 看到的，仍可直接呼叫）

```
vein ask           — 關鍵字搜尋（即時，no index）
vein list          — 列出所有 entries，支援 filter
vein reindex       — 重建 FTS5 + embedding index
vein import        — 批量匯入 decisions.md 或任意 .md
vein debrief       — post-commit AI diff 掃描，自動提取 lore
vein hooks         — 管理 git post-commit hook
vein fetch         — 抓一個 GitHub repo → 提取 lore → .vein/references/
vein study fetch   — 批次 fetch 多個 repos 到同一個 collection
vein study compare — 用 AI 比較 collection 內的 repos
vein study list    — 列出所有 study collections
vein study purge   — 刪除 collection 的 raw entries
vein study watchlist add/list/run — 管理夜間自動追蹤清單
vein night-harvest — 夜間 pipeline（watchlist + debrief + morning brief）
vein morning       — 印出今日 morning brief
vein run           — 執行指令；失敗時自動 triage via lore + AI
vein pipe          — stdin 錯誤 → 搜尋 lore + AI triage
vein gc            — 清除過期 / 指定 entries
vein walk          — multi-agent workflow runner（sunnywalker）
vein mcp           — 啟動 MCP server（Claude Desktop / SSE）
```

---

## 完整工作流程

```
                 ┌─────────────────────────────────────────┐
                 │         開發中發現值得記錄的事             │
                 └──────────────┬──────────────────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │  A: 手動 vein log <type>     │   ← 你主動記
                 │  B: vein run <cmd>           │   ← 指令失敗 auto-triage
                 │  C: cmd 2>&1 | vein pipe     │   ← 錯誤 pipe 進來
                 └──────────────┬──────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  ollama polish         │   ← --no-polish 跳過
                    │  (qwen2.5-coder:7b)   │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  write .vein/type/    │
                    │  id.md (YAML + body)  │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  auto embed + index   │   ← ollama 離線 silent skip
                    └───────────────────────┘

── git commit 後（有 vein hooks 時）──────────────────────────

  git commit
       │
       ▼  post-commit hook
  vein debrief --silent
       │
       ▼  ollama diff 掃描
  自動提取值得存的 decision / lore / pitfall
       │
       ▼  write to .vein/

── 夜間 / 早晨 ───────────────────────────────────────────────

  02:00 cron → vein night-harvest
       │  ① run all watchlists (fetch + compare)
       │  ② vein debrief --since HEAD~5
       │  ③ 生成 morning brief → .vein/lore/morning-YYYY-MM-DD.md
       │
  早上 → vein morning   (印出 morning brief)
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

手動捕捉一筆 lore entry：

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
vein log d "..." --tag hal --tag timer   # 手動加 tag
vein log d "..." --no-polish             # 跳過 ollama，直接存 raw
vein log d "..." --yes                   # 跳過互動確認
vein log d "..." --source-url "https://..." --source-title "Doc title"
```

Polish 流程（ollama 可用時）：

```
raw text → qwen2.5-coder:7b → JSON {type, title, tags, body}
        → Interactive confirm (y / n / e)
        → write .vein/type/YYYYMMDD-HHMMSS-XXXX.md
```

---

## `vein debrief`

**post-commit AI diff 掃描**：自動從 git diff 提取值得存的 lore。

```bash
vein debrief                    # diff HEAD~1，互動輸出
vein debrief --since HEAD~3     # 掃最近 3 個 commits
vein debrief --silent           # post-commit hook 用（無輸出時靜默）
vein debrief --dry-run          # 預覽，不寫入
git diff HEAD~1 | vein debrief  # 從 stdin 讀 diff
```

設計邏輯：commit 完成後是最好的 capture 時機——diff 是完整的「這次改了什麼」記錄。ollama 判斷哪些值得留，離線時靜默跳過。

通常搭配 `vein hooks install` 自動化，不需要手動呼叫。

---

## `vein hooks`

管理 git post-commit hook：

```bash
vein hooks install   # 在 .git/hooks/post-commit 安裝 hook
vein hooks remove    # 移除 hook
vein hooks status    # 顯示是否已安裝
```

安裝後，每次 `git commit` 都自動跑 `vein debrief --silent`。有 ollama 才真正提取，無 ollama 靜默 pass。

---

## `vein status`

```bash
vein status         # 顯示計數 + active pitfalls + 最近 10 entries
vein status --all   # 包含 superseded
```

輸出範例：

```
myproject  Phase 0  /path/to/.vein

  type        count   active
 ────────────────────────────
  decision       12       11
  lore            8        8
  pitfall         3        3
  reference       5        5

  total          28

Active pitfalls:
  ⚠ SQLite locked under concurrent writes  (20260528-...)

Recent entries:
  reference  2026-06-02  VS Code GUI 行為規格 vs Lode 對照
  reference  2026-06-02  VSCode / search / Replace in Files
```

---

## `vein brief`

為新 AI session 生成 ≤2K token 的 context digest：

```bash
vein brief          # 讀 cache（TTL 1h）或即時生成
vein brief --regen  # 強制重新生成
vein brief --raw    # 直接 print，不走 rich formatter
```

生成邏輯（rule-based，不需 LLM）：
- decisions: 最新 8 筆，取 Why section
- pitfalls: status=active 全部，加 ⚠ 標記
- lore: 最近 7 天內的
- STATUS.md: 取 "Current focus" section

**用法：在每個新 AI session 開頭貼入 `vein brief` 輸出**，讓 Claude / Gemini 快速了解專案狀態。

---

## `vein morning`

印出今日 morning brief（由 `vein night-harvest` 預先生成）：

```bash
vein morning                   # 今天的 brief
vein morning --date 2026-05-31 # 指定日期
```

若今日 brief 尚未生成（`night-harvest` 還沒跑），會即時生成。

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

語意搜尋（FTS5 BM25 + embedding cosine，RRF 融合）：

```bash
vein recall "concurrent write issue"
vein recall "為什麼用 sqlite"          # 中文可用，逐字 token + phrase match
vein recall "why polling bad" --budget 32k
vein recall "timer" --fts-only        # 只用 FTS5，跳過 embedding
vein recall "dma" -n 10
```

**排序方式：** BM25 排名與 cosine 排名用 RRF（Reciprocal Rank Fusion）融合，不是
「有 vector 結果就不看關鍵字」。兩邊都命中的排最前。ollama 沒開 → 降級純 FTS5 → 再降級 grep。

顯示的 mode 標籤：`hybrid`（兩邊都有）/ `semantic`（只有向量）/ `fts` / `keyword`（grep）。

**中文查詢：** SQLite 內建的 `unicode61` tokenizer 會把「一整段沒有標點的中文」當成單一 token，
查 `索引` 撈不到 `就整個放棄索引`。Vein 在 index 與 query 兩端都把漢字逐字切開，再用 FTS5 phrase
（`"索 引"`，要求 token 相鄰）還原精確比對。

查詢分三層，命中就停：phrase AND（最精確）→ phrase OR → CJK bigram OR。
第三層是給「中文不打空格」的自然查法用的——`索引效能` 當成單一 phrase 會要求這四個字連著出現，
拆成 `"索 引" OR "引 效" OR "效 能"` 才找得到分別講索引和效能的 entry。
詳見 `src/vein/core/cjk.py` 與 D-030。

**tip:** `vein log` / `vein debrief` / MCP `vein_log` 都會即時進 index，正常不需手動 reindex。
`vein status` 有顯示 index 覆蓋率，有缺口（ollama 當時沒開）才需要跑 `vein reindex`。

---

## `vein list`

```bash
vein list                         # 全部 active entries
vein list --type pitfall          # 只看 pitfalls
vein list --status all            # 含 superseded
vein list --tag vscode            # tag 含 "vscode" 的
vein list --tag project:lode      # cross-project lore
vein list -n 20
vein list --ids-only              # 只印 id，可 pipe 用
```

---

## `vein fetch`

**抓一個 GitHub repo 的 lore 進 `.vein/references/`**：

```bash
vein fetch microsoft/vscode
vein fetch https://github.com/simonw/llm
vein fetch owner/repo --dry-run              # 先看會抓什麼
vein fetch owner/repo --tag project:lode     # 額外加 tag
vein fetch owner/repo --max-files 15         # 最多讀 N 個 md 檔
```

流程：
1. `git clone --depth=1` 到 temp dir
2. 讀 README + docs/*.md（優先 ARCHITECTURE、DECISIONS、WHY）
3. ollama 提取 reference / decision / lore / pitfall entries（最多 6 筆）
4. 寫入 `.vein/references/`；離線時 fallback 到純 README summary

---

## `vein study`

**批次 fetch 多個 repos 到一個 collection，再用 AI 比較**：

```bash
# fetch 多個 repos 進 collection "study_mcp"
vein study fetch study_mcp jlowin/fastmcp modelcontextprotocol/python-sdk

# AI 比較 collection 內所有 repos
vein study compare study_mcp

# 列出所有 collections
vein study list

# 列出 collection 內的 entries
vein study list study_mcp

# 刪除 raw entries（保留 compare summary）
vein study purge study_mcp --keep-compare

# 管理夜間自動追蹤清單
vein study watchlist add study_mcp simonw/llm BerriAI/litellm
vein study watchlist list
vein study watchlist run study_mcp    # 立即跑一次
```

Collection 實作方式：在 entries 加 `study:<name>` tag，不需新 schema。

---

## `vein night-harvest`

**夜間自動化 pipeline**，建議加到 cron：

```bash
vein night-harvest                  # 跑全部 watchlist + debrief + morning brief
vein night-harvest --since HEAD~5   # debrief 多抓幾個 commits
vein night-harvest --purge-raw      # fetch 後自動清 raw entries
```

Cron 設定（每天 02:00）：

```
0 2 * * *  cd /Users/lion/Documents/vein && vein night-harvest >> ~/.vein-harvest.log 2>&1
```

Pipeline 步驟：
1. 跑所有 watchlists（fetch + compare + optional purge）
2. `vein debrief` 抓近期 commits
3. 生成 morning brief → `.vein/lore/morning-YYYY-MM-DD.md`

---

## `vein run`

**執行指令；失敗時自動搜尋 lore + AI triage**：

```bash
vein run cargo check
vein run pytest tests/ --ai    # 失敗時呼叫 AI 分析
vein run "make build" --log    # 同時存 log
```

取代手動 copy-paste 流程：`fail → copy error → chat → paste fix → paste back`
→ 改為：`vein run cmd → 失敗 → 自動 recall + triage`

---

## `vein pipe`

**stdin 錯誤 → 搜尋 lore + AI triage**：

```bash
cargo check 2>&1        | vein pipe
pytest tests/ 2>&1      | vein pipe --cmd "pytest tests/"
make build 2>&1         | vein pipe --ai
cat build.log           | vein pipe --log
```

---

## `vein gc`

清除 `.vein/` 過期或指定 entries：

```bash
vein gc --dry-run                        # 預覽，不刪除
vein gc --stale                          # 刪 volatility TTL 過期的 entries
vein gc --older-than 60                  # 刪 60 天以上的 entries
vein gc --collection study_llm           # 清掉整個 collection
vein gc --collection study_llm --keep-compare   # 保留 compare summary
vein gc --type reference                 # 只清 reference 類型
vein gc --committed --older-than 7       # 只清已 git commit 的（safer）
```

刪除後 SQLite index 自動更新；大量 gc 後建議跑一次 `vein reindex`。

---

## `vein reindex`

重建 `.vein/index/vein.db` 的 FTS5 + embedding index：

```bash
vein reindex                    # 增量：只補「該嵌但沒嵌」的
vein reindex --all              # 全部重嵌，但保留 DB
vein reindex --force            # 先 drop 再重建
vein reindex --type pitfall     # 只 reindex pitfalls
```

**預設是增量**，只處理三種 entry：

1. 根本不在 index 裡的
2. 在 index 裡但沒有 vector 的（capture 當下 ollama 沒開）
3. vector 維度跟現在的 embed model 不符的（換過模型）

第 3 點會自動偵測：reindex 先對現行模型送一個探測字串問出維度，再掃出所有寬度不符的 entry。
換 embed model 後直接跑 `vein reindex` 就會全部補上，不需要記得加 `--force`。

什麼時候跑：第一次 setup、手動編輯 `.vein/*.md` 後、換 embed model 後、`vein recall` 搜不到預期結果。
`vein status` 會顯示 `{embedded}/{total} embedded`，有缺口會直接提示。

需要 ollama：

```bash
ollama serve
ollama pull nomic-embed-text    # 首次下載
vein reindex
```

---

## `vein import`

從現有 docs 批量匯入：

```bash
# decisions.md（自動識別 D-xxx 格式）
vein import docs/decisions.md
vein import docs/decisions.md --dry-run

# 任意 .md（作為一筆 reference 匯入）
vein import docs/vscode_ux_behavior_spec.md --type reference

# 大量匯入加速
vein import docs/decisions.md --no-index   # 先不 embed，最後再 vein reindex
```

解析規則：有 `### D-\d+` pattern → decisions.md 格式，每個 block 一筆 entry；否則整份檔案一筆 lore entry。

---

## `vein mcp` — 接 LLM

啟動 MCP server，讓任何 MCP client 直接查 `.vein/`。暴露 4 個 tool：
`vein_brief()` / `vein_recall(query)` / `vein_log(type, message)` / `vein_status()`。

```bash
vein mcp                                       # stdio（Claude Code / Desktop）
vein mcp --project /Users/lion/Documents/vein  # 指定 store（會 os.chdir，不靠 cwd）
vein mcp --transport sse --port 8765           # SSE（browser / remote）
```

接法依介面而不同——**三者機制不一樣，別搞混**：

### Cowork（桌機 app）→ 必須走 plugin

Cowork **不讀** 專案 `.mcp.json` 也不讀 `claude_desktop_config.json`。唯一的路是打包成 plugin 安裝：

```bash
cd /Users/lion/Documents/vein && python3 shell/build_vein_cowork_plugin.py
# → dist/vein-lore-plugin.zip
```

安裝：Cowork tab → 左側欄 **Customize** → **Plugins** → Personal plugins 的 **+** → 上傳該 zip。
確認：重開 session，對話框打 `call vein_status`。

### Claude Code → 專案 `.mcp.json`（或 `~/.claude.json`）

```json
{
  "mcpServers": {
    "vein": { "command": "vein", "args": ["mcp", "--project", "/Users/lion/Documents/vein"] }
  }
}
```

### Claude Desktop（Chat，非 Cowork）→ `claude_desktop_config.json`

同上 JSON，放進 `~/Library/Application Support/Claude/claude_desktop_config.json`，重開 app 看 🔌。

> **已知限制：** GUI 起的 MCP 若接不到 ollama，recall 會 silent 降級成 FTS5/BM25 關鍵字（少了語意 re-rank）。要恢復：`ollama serve` 在跑、`nomic-embed-text` 已 pull，且 launch env 看得到 `localhost:11434`（必要時 plugin `.mcp.json` 補 `OLLAMA_HOST` env）。

---

## 維護腳本（`shell/`）

| 腳本 | 做什麼 | 何時跑 |
|------|--------|--------|
| `build_vein_cowork_plugin.py` | 把 `vein mcp` 打包成 Cowork plugin zip | 第一次接 Cowork、換 store 路徑 / 換機器 |
| `import_lode_decisions.py` | 解析 `lode/docs/decisions.md` → 匯入 `### 🔴/🟡` 真雷 + 架構決策表 + known-issue 表 | 每次在 decisions.md 新增雷後（idempotent，只補新的） |
| `prune_noise.py` | 刪 auto-fetch 雜訊（IINA 符號 dump / `fetch`+`github` / `auto` 比較 stub / 空 body）；預設 dry-run，永遠跳過 `source:lode:docs/decisions.md` | 雜訊變多時 |

```bash
python3 shell/import_lode_decisions.py     # 匯入 + 自動 reindex
python3 shell/prune_noise.py               # 預覽（dry-run）
python3 shell/prune_noise.py --yes         # 實刪 + reindex
```

> 這套取代了舊的 `export_lore_to_lode.py` 快照流程（已移除）——Lode 現在直接走 MCP，不再產 `vein_lore.md` 影印本。

---

## config.yaml 說明

```yaml
version: 1

project:
  name: "myproject"
  description: ""
  phase: "0"

model:
  backend: ollama
  base_url: http://localhost:11434
  embed_model: nomic-embed-text       # recall embedding
  digest_model: llama3.2:3b           # morning brief / debrief
  polish_model: qwen2.5-coder:7b      # log polish
  analyze_model: deepseek-r1:14b      # study compare（重度分析）

capture:
  interactive: true          # vein log 是否互動確認
  brief_ttl_seconds: 3600    # BRIEF.md cache TTL（1h）
  min_cosine_threshold: 0.30

index:
  path: .vein/index/
  fts_candidate_k: 50
  recall_top_k: 5
```

---

## 典型日常流程

### 開始新 session

```bash
vein brief                   # 貼給 AI 當 context
vein recall "DMA timeout"    # 查特定問題
```

### 開發途中記筆記

```bash
vein log d "選 WAL mode 不選 journal mode，single writer pattern"
vein log p "HAL DMA submit 不能在 callback 內呼叫，會 re-entrant deadlock"
vein log l "nomic-embed-text normalize 後 dot product = cosine"
```

### 用指令失敗自動找答案

```bash
vein run pytest tests/          # 失敗時自動 recall + triage
cargo check 2>&1 | vein pipe    # pipe 進來
```

### 收工

```bash
vein status        # 確認今天新增了什麼
git add .vein/decisions .vein/lore .vein/pitfalls .vein/references
git commit -m "vein: update lore"
# post-commit hook 自動跑 vein debrief（若已安裝）
```

### 研究競品 / 外部 repo

```bash
# 抓一個 repo
vein fetch simonw/llm --tag project:vein

# 批次比較 MCP SDK 選項
vein study fetch study_mcp jlowin/fastmcp modelcontextprotocol/python-sdk
vein study compare study_mcp
vein recall "mcp sdk"    # 馬上可以 recall 比較結果
```

### 抓 VS Code / 其他工具的 GUI 行為規格

```bash
# 一次性手動 fetch（需要本機網路）
python3 shell/fetch_vscode_ux.py --area all --platform macos

# dry-run 先看
python3 shell/fetch_vscode_ux.py --area search --dry-run

# 有 ollama 會自動 enrich 每條行為
python3 shell/fetch_vscode_ux.py --area explorer --platform macos

# recall
vein recall "vscode rename"
vein recall "vscode tab dirty"
```

### 設定夜間自動化

```bash
# 初始化 watchlist
vein study watchlist add study_tools simonw/llm jlowin/fastmcp

# 安裝 git hook（每次 commit 自動 debrief）
vein hooks install

# 加 cron（每天 02:00）
crontab -e
# 加入: 0 2 * * *  cd /Users/lion/Documents/vein && vein night-harvest >> ~/.vein-harvest.log 2>&1

# 早上看昨晚成果
vein morning
```

### 清理舊資料

```bash
vein gc --stale --dry-run         # 看哪些過期了
vein gc --collection study_old --keep-compare
vein reindex                      # gc 後重建 index
```
