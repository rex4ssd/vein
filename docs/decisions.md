# Decisions & Pitfalls — Vein

> 任何 trade-off 選擇、放棄的路線、不可違反的 invariant、踩過的雷，都寫進來。
> 三個月後接手看這份，比看 git log 快 10 倍。
>
> 格式：
> - `D-NNN`：decision（為什麼選 A 不選 B）
> - `P-NNN`：pitfall（踩過的反 pattern + 預防 check）
> - `I-NNN`：invariant（不可違反的鐵律）

---

## Decisions

### D-001 — 用 Python，不用 Rust／Go／TypeScript

**Date:** 2026-05-26

**Choice:** v0.1 用 Python 3.11+ 寫 CLI kernel。

**Why:**
- Rex 5+ 年 Python，iteration 最快
- ollama / sqlite-vec / MCP SDK 在 Python 生態都成熟
- Phase 0 目標是「能跑 + dogfood」，**不是**「效能極致」
- 寫起來短：CLI 800 行 Python vs 2000+ 行 Rust

**Trade-off accepted:**
- 啟動時間 ~200ms（Python interpreter），`vein recall` 整體要 6-10s（ollama 占大頭），200ms 不痛
- 將來如果 vein 變 daemon（v0.3 MCP server），Python 也夠（aiohttp / fastmcp）

**Revisit when:**
- `vein recall` 變成熱路徑、單次跑 < 1s（不太可能）
- 要 single-binary distribution（用 PyInstaller 或 Rust 重寫 core）

---

### D-002 — vector store 用 sqlite-vec，不用 chromadb / faiss / qdrant

**Date:** 2026-05-26

**Choice:** `sqlite-vec`（asg017 那個 extension）。

**Why:**
- **單檔**：`.vein/index/embeddings.db` 一個檔，跨機器 rsync 就好
- **無 daemon**：chromadb 要起 server、qdrant 要 docker，sqlite 零配置
- **熟悉**：Python `sqlite3` stdlib，sqlite-vec 是 extension
- **夠用**：v0.1 預期專案 ≤ 10K chunks，sqlite-vec 在這 scale 表現好（< 100ms query）

**Rejected:**
- `chromadb`：要 daemon、有 telemetry default、檔散
- `faiss`：學術出身、Python binding 笨重、index 不易 inspect
- `qdrant`：太重、要 docker
- pure-numpy in-memory：每次 `vein recall` 都 load 全部 vector，慢

**Revisit when:**
- 專案 > 100K chunks 且 query 變慢
- 需要 multi-tenant / 多人 share index

---

### D-003 — chunking 用 fixed-token，不用 semantic split

**Date:** 2026-05-26

**Choice:** v0.1 固定 400 token、50 overlap。

**Why:**
- semantic split（按 markdown header / 函數邊界）要 parse 每種檔型，工程量大
- fixed-token 簡單、可預測、debug 容易
- retrieval 階段用 top-k 補救單 chunk 太短的問題

**Trade-off:**
- 切到函數中間 / 段落中間，會切壞語意
- 用 50-token overlap 緩解

**Revisit when:**
- dogfood 發現 retrieval 品質明顯被切壞影響（看 brief 出來有沒有「斷頭」感）
- 引入 tree-sitter 之後可以低成本做 syntactic chunking

---

### D-004 — embedding 用 nomic-embed-text，不用 OpenAI / cloud

**Date:** 2026-05-26

**Choice:** `ollama pull nomic-embed-text`（768-dim）。

**Why:**
- **Local-first 是 G2**（goal 2 of spec），embedding 送雲端就破功
- nomic-embed-text 在 MTEB 上排前段，跟 OpenAI text-embedding-3-small 接近
- ollama 已經在本機跑，不增加 dependency

**Trade-off:**
- 比 OpenAI embedding 慢 ~3x（local 算）
- index 階段 batch 處理，慢可接受；query 階段 < 50ms 影響不大

---

### D-005 — `.vein/cache/` 進 .gitignore，`.vein/config.yaml` 進 git

**Date:** 2026-05-26

**Choice:** 預設 `.gitignore`：

```
.vein/cache/
.vein/index/embeddings.db
.vein/memory/
```

進 git：

```
.vein/config.yaml
.vein/digests/
.vein/.gitignore        ← 自己
```

**Why:**
- `config.yaml` 是 source of truth，要跟 code 一起 version
- `digests/` 是人寫 / 半自動產的高價值產出（週報、topic digest），值得 commit
- `cache/` / `embeddings.db` 是 derived view，重建成本可接受，不該膨脹 repo
- `memory/sessions.jsonl` 含個人 query history，可能含敏感 keyword，預設不 commit

---

### D-006 — 採 Open Core 商業模式（Vein OSS + Lode 付費 + 未來 Cloud 訂閱）

**Date:** 2026-05-26

**Choice:** Vein CLI 100% MIT 開源、Lode 維持付費 GUI、Vein Cloud (v1.x+) 訂閱。Solo 功能完全不鎖。

**Why:** 見 [`strategy.md`](strategy.md) 完整論述。摘要：
- 個人功能不鎖 → 最大化 adoption funnel
- 商業價值來自「協作 / 合規 / ops」不是「鎖功能」
- Lode 整合是「不可替代附加值」，不是強制購買

**Architectural constraints（Phase 0 就要做對的事）：**
1. `config.yaml` 必有 `version:` field（未來 schema migration 用）
2. `config.yaml` 預留 `team:` block（留空但保留 key 位置）
3. chunks / digests 設計成「可逐筆獨立加密」（newline-delimited JSON、separate files）
4. License 選 MIT（不選 AGPL/BUSL/SSPL，最大化 OSS adoption）
5. **無 telemetry default**：連 phone-home / license check 都不裝
6. Vein CLI **絕對不能對 Lode 有 hard dependency**：OSS 用戶完全不需碰 Lode 也能跑全功能

**Trade-off accepted:**
- MIT 允許 fork / 商業分支：可能未來有競品。我們的 moat 是「Rex 親自 dogfood 累積的工作流深度」 + Lode 整合，不是 license。
- 「不鎖個人功能」= 部分 power user 永遠不付費。OK，他們是 adoption 的一部分。

**Rejected:**
- AGPL：嚇跑企業 internal use，無謂的傷害 adoption
- BUSL（HashiCorp 那種延遲開源）：信任成本高，社群討厭
- 全閉源賣 license key：完全違反 OSS funnel 邏輯，跟 Lode 重疊

**Revisit when:**
- 出現大廠 fork 並提供 cloud 服務搶生意（不太可能；他們會自己做）
- OSS 採用率 < 100 stars 且持平 6 個月（戰略要重新檢討）

**⚠️ Caveat（2026-05-26 後加）：**
D-006 寫的時候假設「沒人在做這個 niche」。後來 web search 發現至少 7 個直接競品在做 per-project AI context broker（見 [`competitive_landscape.md`](competitive_landscape.md)）。Open Core 模式本身仍然成立，但**「Vein 作為獨立 OSS adoption funnel」這個前提要靠 Path D（decision lore niche）差異化才成立**。

---

### D-007 — 專案命名為 **vein**，採「Lode Vein」product family 命名

**Date:** 2026-05-26

**Choice:**
- **產品本體名稱：** `vein`
- **Product family 名稱：** **「Lode Vein」**（marketing / blog / homepage 用）
- **CLI 命令：** `vein`（4 字、無連字號、短）

**Brand family 設計（Microsoft Office pattern）：**

| 對應角色 | Microsoft Office | Lode 系列 |
|---|---|---|
| Family / suite 名 | Microsoft Office | **Lode Vein** |
| Product A | Word | **Lode**（file viewer / compare / git） |
| Product B | Excel | **Vein**（decision lore archive） |
| Product C/D | PowerPoint / Outlook | (預留 Seam / Shaft) |
| 用戶實際打的命令 | `word` / `excel` | `lode` / `vein` |

每個 product 都有**獨立 CLI 短名 + 獨立識別**，但 marketing 上強 family 包裝。

> Lode finds the code. Vein remembers the why.

### Marketing 講法統一（給未來所有外部文件）

| 場景 | 用詞 |
|---|---|
| Blog 標題 / 主視覺 | **Lode Vein** — Decision & debug lore for AI-assisted dev |
| Homepage hero | "**Lode Vein**: the missing decision history for your AI" |
| GitHub README 第一行 | "**Vein** (part of the **Lode Vein** suite) — local-first decision lore archive" |
| 對話 / 介紹自己時 | 「我做了 **Lode Vein**，Lode 找到檔，Vein 記住為什麼」 |
| 在已知 Lode 用戶圈 | 「Lode 旁邊那個 Vein」 |
| 在 OSS / Reddit / HN | 「Vein — decision lore archive for AI coding」 |
| 純 OSS 不提 Lode 也行 | 「Vein」獨立講得通，不依賴 Lode 才有意義 |

**Why（投票過程見 [`naming.md`](naming.md)）：**
- 舊名（`ctx`）至少撞 3 個獨立 OSS 名字（context-hub / Vedantham / ActiveMemory）
- 從 20 個候選收斂到 Top 3：vein / crux / etch
- Rex 選 vein：跟 Lode 同 brand family、未來可擴 Lode/Vein/Seam 系列、CLI 順
- vein 在 software namespace 不擁擠（mining 比喻少見）

**Rejected：`lode-ctx` / `lode-vein`（CLI 命令）為什麼不行：**
- `lode-ctx`：「ctx」是紅海 namespace，加前綴不改變 SEO / 用戶分類；Path D thesis 失效
- 連字號 CLI 命令痛（`lode-ctx log "..."` 每次手指要找橫線）
- 暗示 sub-product feel，OSS standalone 故事弱

**Availability check（2026-05-26）：**
- 🟢 npm `vein`：空
- 🟢 GitHub `rex4ssd/vein`：可建
- 🟡 PyPI `vein`：被 squat（placeholder package，無後續）
- ❓ Domain `.dev` / `.app`：未測

**Split naming 策略（避開 PyPI squat）：**

| 通路 | 名稱 | 備註 |
|---|---|---|
| Brand / 對外名 | **vein** | 所有 marketing / docs / 對話用這個 |
| CLI 命令 | `vein` | 用戶日常打 |
| GitHub repo | `rex4ssd/vein` | 主 repo |
| PyPI package | `lode-vein`（暫定） | `pip install lode-vein` → 安裝後提供 `vein` CLI |
| Homebrew | `vein`（透過 `rex4ssd/tap`） | self-tap 可控 |
| Domain | `rexcode.app/vein` subdirectory | 主站 |

**Future namespace 預留：**
- **Lode** — desktop GUI / file viewer / compare（已存在）
- **Vein** — decision lore archive CLI + MCP（本專案）
- **Seam** — 預留（mining: 礦層 / 縫）
- **Shaft** — 預留（mining: 礦坑）

Phase 0 只做 Vein。Seam / Shaft 是 namespace 保留，沒實作計畫。

**Revisit when:**
- 確認 PyPI `vein` claim 有沒有機會
- 確認 `.dev` / `.app` domain 有沒有撞

---

### D-008 — Visibility: private 現在，v0.3 flip public

**Date:** 2026-05-26

**Choice:** `rex4ssd/vein` 建為 **private repo**，達到以下三個條件後 flip 成 public：

1. **三個核心命令真的能跑：** `vein init` + `vein log` + `vein recall`
2. **Dogfood on Lode 至少 2 週：** 真實寫過 ≥ 10 條 decision/lore，retrieval 品質確認
3. **README / docs_cloudflare 完整：** 陌生人 30 秒能看懂、5 分鐘能上手

預期觸發時程：Phase 0 完成後、Phase 0.3（MCP server）之前。

**Why（為什麼選 B 不選 A/C）：**

| 路徑 | 採 / 拒 | 理由 |
|---|---|---|
| **A. Public from day 1** | ❌ 拒 | Spec 還在 churn；public 看見 churn 觀感差；無 working product 給人試 |
| **B. Private now, v0.3 flip public** | ✅ 採 | 第一次接觸 Vein 的人看到 working product；spec breaking change 不受外部牽制；跟 Lode 私有 + public release 同 pattern |
| **C. Public + Alpha tag** | ❌ 拒 | 「Alpha」標籤對多數人沒擋；早期 issue noise 大於收穫 |

**參照 pattern：** Lode 自己也是 `rex4ssd/lode` private dev + `rex4ssd/lode-releases` public binaries 雙 repo。

**Public 之前要做的事（pre-flip checklist）：**

- [ ] `vein init` 能跑
- [ ] `vein log decision/lore "..."` 能存進 `.vein/decisions/` 或 `.vein/debug_lore/`
- [ ] `vein recall "<query>"` retrieval 跑得起來、品質可接受
- [ ] Dogfood on Lode ≥ 2 週、≥ 10 條真實 entries
- [ ] LICENSE 檔（MIT）
- [ ] `docs_cloudflare/index.md` polish 完整
- [ ] `docs_cloudflare/install.md` 真實可跑（不是 placeholder）
- [ ] README.md（從 `docs_cloudflare/index.md` 精簡版）
- [ ] CONTRIBUTING.md 雛形
- [ ] `.github/ISSUE_TEMPLATE/` 雛形

**Reserve `lodevein` GitHub org（順手做）：**
保留 namespace 給未來 family 擴張。預防別人註冊變蹭名。

**Revisit when:**
- Lode dogfood Vein 一個月後，如果發現需要外部視角才能改進，可考慮提早 flip
- 若有人宣布類似 "decision lore" product 搶 first-mover 名分，可考慮提早 flip 搶 mindshare

---

## Pitfalls（雷區）

### P-001 — placeholder：第一個踩到的雷請寫這裡

Vein 還沒寫 code，雷區待累積。

預期會踩的：
- ollama timeout / connection refused 怎麼降級
- sqlite-vec 在 macOS 上 load extension 路徑問題
- pbcopy 在 SSH session 失效
- digest 結果含 markdown fenced code block 被剪貼簿吃掉換行

---

## Invariants（不可違反）

### I-001 — `.vein/cache/` 永遠不可進 git

**Why:** cache 會變大（GB 級），含 query 結果可能有敏感 keyword。

**How to enforce:** `.vein/.gitignore` 預設寫好；validator 加 check：`git check-ignore .vein/cache/foo.json` 必須 exit 0。

---

### I-002 — ollama 失敗時必須明確報錯，不可 silent fallback

**Why:** 如果 ollama 跑不起來，靜默 fallback 到 grep 會讓 user 以為 vein 在用 local AI（其實沒），digest 品質爛還不知道為什麼。

**How to enforce:** `OllamaError` raise to top；CLI 印明確「ollama 連不上 http://localhost:11434」+ 退出 code 2。

---

### I-003 — `vein recall` 輸出永遠不超過 config.recall.digest_budget_tokens

**Why:** spec G1（context 省 60%）的核心。如果 brief 自己就 5K token，意義盡失。

**How to enforce:** digest 後 tiktoken count；超過直接 truncate + 警告。

---

### I-004 — config.yaml schema 必須 version 化

**Why:** 將來改 schema 不能讓舊 `.vein/` 直接壞。

**How to enforce:** `config.yaml` 必有 `version:` 欄；vein 讀取時 check `version` 並走對應 migrator。

---

### I-005 — Vein CLI 不可對 Lode（或任何商業產品）有 hard dependency

**Why:** Open Core 戰略（D-006）的信任基礎。OSS 用戶必須 100% 不需 Lode 也能跑全功能。

**How to enforce:**
- `pyproject.toml` 的 `dependencies` 不可出現 Lode-related package
- 任何「Lode 整合」功能必須走 well-defined data format（讀 `.vein/` 即可），不可走 RPC 進 Lode binary
- validator 加 check：`vein --help` 不可提到 Lode（避免「沒裝 Lode 看到推薦覺得被綁」）
- 唯一允許的：`vein --version` 末尾可有一行 marketing footer，可被 `--quiet` 關閉

---

### I-006 — Vein 永遠不可預設 telemetry / phone-home

**Why:** D-006 brand promise。一旦預設打開過一次，社群信任就回不去。

**How to enforce:**
- 任何 outbound HTTP 必須明確 user action 觸發
- 不可有「匿名統計」「使用情況回報」「auto-update check」default-on
- 如果未來要加 opt-in telemetry，必須：
  1. CLI 明顯 prompt（不是 dialog 預設打勾）
  2. 開源 telemetry endpoint server 程式碼
  3. 文件清楚列出每個 event 內容

---

### D-009 — 語言策略：Python 現在，Go 評估觸發條件

**Date:** 2026-05-27

**Choice:** Phase 0 維持 Python 3.11+；Phase 1 依以下條件評估 Go rewrite。

**Go 的優勢（對 CLI distribution 有意義）：**
- Single binary：`brew install vein` 直接裝，不需要 Python 環境
- 啟動時間：~5ms vs Python ~200ms（對 `vein recall` 這種熱路徑有感）
- Cross-compile：`GOOS=linux GOARCH=amd64 go build` 一行，免 CI 矩陣
- PyPI squat 問題自動消失（不走 PyPI）

**Go 的代價：**
- Rex 的 iteration 速度慢 3-5x（Go 比 Python 囉唆）
- ollama / sqlite-vec / tiktoken 的 Python binding 成熟；Go 版薄，要自己包 HTTP + CGO
- Phase 0 dogfood 優先，distribution 問題還不痛

**觸發 Go rewrite 評估的條件（任一）：**
1. `pip install lode-vein` 安裝摩擦讓外部用戶明顯抱怨
2. `vein recall` 成為熱路徑，200ms startup 被感知（通常不太可能，ollama 才是瓶頸）
3. Phase 1 打算做 binary release + Homebrew tap，distribution UX 比 iteration 速度更重要

**橋接方案（Go rewrite 之前）：**
- `uv tool install lode-vein`（uv 安裝體驗比 pip 好很多）
- `pipx install lode-vein` 作為 fallback
- API 設計在 Python 穩定後，Go rewrite 只是 re-implement，不是 re-design

**Revisit when:** Phase 0 dogfood 完成、外部用戶 > 50 人時重新評估。

---

### D-010 — MCP server 是 platform independence 的關鍵，不只是功能

**Date:** 2026-05-27

**Context:** IDE-native memory（Cursor Memory、Windsurf Memory）是 Vein 的 platform risk。他們的結構性弱點：雲端依賴、vendor lock-in、付費門檻、單一 model 綁定。

**Choice:** Phase 0.3 的 MCP server 不只是「方便整合」，而是核心戰略：讓 `.vein/` 成為任何 MCP-compatible tool 都能讀寫的 portable memory layer。

**架構意圖：**

```
Cursor      ──┐
Windsurf    ──┤── MCP ──→ vein serve ──→ .vein/ (你的 lore)
Claude Code ──┤
本機 ollama ──┘
```

不管用什麼 IDE、什麼 model，記憶住在 `.vein/`，跟 `.git/` 一樣是專案資產。換工具不丟記憶。

**對 Cursor 的直接反擊：**
- Cursor Memory：雲端、$40/month、綁 Cursor model 合約
- Vein：local-first、$0（搭 ollama）、跑任何 model、`.vein/` 跟你走

**Phase 0.3 之前要做對的事（避免 MCP 上線後要 breaking change）：**
1. `.vein/` schema 的 `id` 欄位要穩定（MCP tool 用 id 查 lore）
2. lore entry 要有 `tags:` 欄位（MCP client 用 tag 過濾）
3. `vein serve` 的 protocol 直接對齊 MCP spec，不做自己的 RPC

**Positioning narrative（給 docs_cloudflare/why.md）：**
> "Cursor Memory costs $40/month and lives in their cloud.  
> Vein costs $0, lives in your `.vein/`, and works with every tool you already use."

**Revisit when:** MCP spec 有 breaking change，或 Cursor/Windsurf 宣布支援 local MCP server（那時反而是好事，代表生態認可）。

---

### D-011 — 大記憶 AI Server（百 GB unified memory）是 upgrade path，不是 existential threat

**Date:** 2026-05-27

**Context:** Mac Studio Ultra 192GB unified memory 已可跑 405B 模型；future local AI server 的 context window 可能達數百萬 token。「把整個 codebase 塞進 context」在兩三年內不是夢。這會讓 Vein 的 digest / compression 失去意義嗎？

**結論：不會。原因是 raw data ≠ curated lore。**

Git 有所有 commit history，但 decisions.md 還是存在 —— 因為 commit 記錄 *what changed*，Vein 記錄 *why we chose this over that*。Context 越大，AI 看得到的 noise 也越多；Vein 的 lore 是人工確認過的 signal，作為「優先載入的 anchor layer」價值不減，反而更高。

**Tiered digest 架構（Phase 0 就要設計對）：**

| 使用情境 | 推薦 budget | 對應指令 |
|---|---|---|
| Cloud LLM（Claude / GPT）省 token | ≤ 2K token | `vein recall "query"` |
| 本機 13B（16GB RAM） | ≤ 32K token | `vein recall --budget 32k "query"` |
| 本機 70B+（64GB+ RAM） | ≤ 200K token | `vein recall --budget 200k "query"` |
| 本機 405B / 百萬 ctx | 不壓縮，全量 | `vein recall --raw "query"` |

`config.yaml` 設計要支援 `recall.digest_budget` 可覆寫，不寫死 2K。

**架構 invariant（Phase 0 就要做對）：**
- `.vein/` 儲存格式永遠是完整 lore（不預先壓縮）
- digest 是 **read-time** 的 view，不是 write-time 的損耗
- 同一份 `.vein/` 可以在 3B 機器上出 2K digest，在 405B 機器上出全量

**對 Printing Press 的互補關係：**
Printing Press 給 AI 執行工具（muscle memory），Vein 給 AI 決策脈絡（long-term memory）。兩者合在一起是完整的 AI-assisted dev stack：知道怎麼做 + 記得為什麼這樣做。未來可以考慮 cross-reference：Vein lore 可以記「為什麼選某個 Printing Press CLI」。

**Revisit when:** 本機 context window 超過 1M token 且成本接近 $0 時，重新評估 `--raw` 是否變成預設。

---

### D-012 — Web Clipper：lore entry schema 從 Phase 1 就要預留 source 欄位

**Date:** 2026-05-27

**Context:** 需求：在 Chrome 選取文字 → 透過 bookmarklet / Chrome Extension 存進 `.vein/` 作為 reference lore（「為什麼選這個 library」「這篇文章影響了 D-002」）。

**Choice:** Phase 1 的 lore entry schema 就預留 `source_url` 和 `source_title`，不等 Phase 2 再加。

**Why 現在就要做：**
- schema 加欄位是 non-breaking change，但 migration 要寫；Phase 1 就對，省掉這個工
- bookmarklet 是 Phase 2 功能，但 `vein serve` HTTP endpoint 的 payload 要接受這兩個欄位
- 搜尋時「從哪個 URL 來的」是有用的 filter

**Lore entry 完整 schema（Phase 1 目標）：**

```yaml
# .vein/decisions/20260527-143022.md frontmatter
---
id: 20260527-143022
type: decision          # decision / lore / pitfall / reference
title: "為什麼選 sqlite-vec"
tags: [database, vector, local-first]
date: 2026-05-27T14:30:22+08:00
source: local           # local | bookmarklet | git-hook | mcp | template
source_url: ""          # 網頁來源 URL（bookmarklet 填入）
source_title: ""        # 網頁標題
related: [D-002]        # 關聯的 decision id
---
```

**Web clipper 實作路徑（複雜度遞增）：**

| 方式 | 何時做 | 說明 |
|---|---|---|
| Bookmarklet | Phase 2（vein serve 之後） | `fetch('localhost:3747/log', ...)` |
| `lode://` URL scheme | Lode v0.x（另案） | Lode app 處理，轉寫進 .vein/ |
| Chrome Extension | Phase 3 之後 | 完整 UX，含右鍵選單 |

**Bookmarklet 草稿（待 vein serve 完成後啟用）：**

```javascript
javascript:(function(){
  var sel = window.getSelection().toString().trim();
  if (!sel) { alert('請先選取文字'); return; }
  fetch('http://localhost:3747/log', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      type: 'reference',
      message: sel,
      source_url: location.href,
      source_title: document.title
    })
  }).then(r => r.json()).then(d => alert('✓ Saved: ' + d.id));
})();
```

**Revisit when:** Chrome Extension 有需求（外部用戶反映 bookmarklet 不夠用）。

---

### D-013 — fubon_stock × Vein：獨立 `.vein/` + AI 下單 audit trail

**Date:** 2026-05-27

**Context:** fubon_stock（`/Users/lion/Documents/fubon_stock/`）計劃引入：台股歷史行情回測 + AI 自動下單。Vein 在這裡有兩個角色：策略設計決策記錄、AI 下單 audit trail。

**Choice:**
1. `fubon_stock` 建立獨立的 `.vein/`（不跟 Vein 專案 lore 混）
2. AI 每次下單前後各呼叫一次 `vein log`，記錄推理過程

**Why 獨立 `.vein/`：**
- 股票策略的 lore 跟 Vein 開發的 lore 語意完全不同
- 日後可能有人只用 fubon_stock 不用 Vein，lore 不應互相污染
- `vein recall "RSI"` 在 fubon_stock context 下要找股票策略，不是 Vein 的 code 決策

**AI 下單 audit trail 的結構：**

```python
# 下單前 — 記錄 AI 推理
vein log decision \
  "買進 2330 100 張 @ 920 — AI reasoning: RSI=27(oversold), \
   三大法人連買 3 日共 5000 張, MACD golden cross D1; \
   risk: stop_loss=-5% (@874), position=2% portfolio; \
   strategy_version=v3.2"

# 下單後 — 記錄執行結果
vein log lore \
  "2330 成交 @ 921（滑點 +1），時間 09:03:42; \
   預期 vs 實際：開盤前預估 920，實際多 1 元（流動性正常）"

# 平倉 / 停損時
vein log lore \
  "2330 平倉 @ 880 (-4.9%)，觸發 stop_loss; \
   AI 推理在事後看：法人買超是假突破，主力出貨跡象 D+2 出現"
```

**Lore 分類建議（fubon_stock 專用 tag）：**

| tag | 用途 |
|---|---|
| `strategy-design` | 為什麼選這個指標 / 參數 |
| `backtest-result` | 回測數據記錄 |
| `trade-entry` | AI 下單推理 |
| `trade-exit` | 平倉 / 停損原因 |
| `api-pitfall` | Fubon Neo API 雷區 |
| `market-observation` | 市場行為觀察（非策略，純觀察）|

**`vein recall` 在股票 debug 的威力：**

```bash
# 事後 debug：「AI 昨天為什麼買 2330？」
vein recall "2330 trade entry 2026-05-28"
→ 立刻看到當時的 RSI / 法人數據 + AI 推理全文

# 策略迭代：「v2 跟 v3 的差異是什麼？」
vein recall "strategy v2 v3 comparison"
→ 看到當初版本升級的 trade-off 記錄
```

**風險管理前提（不是 Vein 的功能，但要 Vein 記錄）：**
1. 先 paper trading ≥ 3 個月，Vein 記錄每筆虛擬交易的 AI 推理
2. 真實下單前，`vein recall "paper trading lessons"` 確認有沒有系統性問題
3. 每日損益超過 -2% → 自動暫停，`vein log pitfall` 記錄當天市況

**Architectural constraint：**
- `fubon_stock` 的 `vein log` 呼叫要用 `--project /Users/lion/Documents/fubon_stock` flag 指定專案路徑
- 或在 `fubon_stock/` 目錄下執行（vein 自動找最近的 `.vein/`，類似 git 的 root detection）

**Revisit when:** AI 下單策略穩定後，考慮把 audit trail 做成 structured JSON 而非 markdown prose，方便程式化分析交易決策品質。

---

### D-014 — `vein brief`：新 session / 小問題的 grep waste 解法

**Date:** 2026-05-27

**Context:** 每次開新對話視窗，或問大專案裡的小問題，Claude 的第一反應是：
grep × 5~10 + read × 3~5 → 才弄清楚背景 → 才開始真正工作。
這些「定向成本」浪費 ~5-15K token，而且每次 session 都重來。

**根本原因：** Claude 沒有關於這個專案的 pre-computed orientation，每次從零開始探索。

**Choice:** 新增 `vein brief` 指令，輸出一份 ~800 token 的 orientation digest，
覆蓋 90% 的「我是誰、現在在哪、有哪些雷」定向問題。

**`vein brief` 的輸出結構：**

```markdown
# Project Brief — {project_name} (generated {timestamp})

## What is this project?
{1-2 句 from config.yaml description}
Current phase: {from .vein/config.yaml}

## Key Architecture Decisions (top 5 by recency + relevance)
- D-XXX: {title} — {1 句 rationale}
- ...

## Active Pitfalls (unresolved P-xxx)
- P-XXX: {title} — {1 句 how to avoid}

## Recent Lore (last 7 days)
- {date}: {lore title}

## Current TODO / Phase Status
{from config.yaml or .vein/STATUS.md}
```

**`vein brief` 的實作：**
- 不做 embedding search（不需要，是 full-scan of recent + pinned lore）
- 用 `llama3.2:3b` 把 raw lore list 壓成 brief（速度快）
- 結果 cache 進 `.vein/BRIEF.md`，TTL = 1 小時或有新 `vein log` 就失效
- 可帶 `--regen` 強制重新生成

**`vein ask`：小問題的 grep 替代品**

比 `vein recall` 更口語化，專門對應「我想知道為什麼 X 是這樣」類問題：

```bash
# 代替 Claude 自己 grep + read 多個檔
vein ask "為什麼 DualTree 用 virtual scroll？"
→ 立刻從 .vein/ 找到 D-015，輸出 rationale

vein ask "ResizeObserver 在哪裡用？為什麼？"
→ D-018 + 相關 pitfall

vein ask "有沒有跟 sqlite 相關的雷？"
→ P-004, P-007 的摘要
```

內部是 `vein recall` 加上問答 prompt，差別在輸出格式更像回答問題而非 digest。

**Session SOP 更新（with vein brief）：**

```
新 session 開始（任何大小的問題）
    │
    ▼
  vein brief              ← 一次，得到 orientation（~800 token）
    │
    ▼
  task scope 確認
    │
    ├─ 簡單問題 ──► vein ask "<question>"  → 直接回答，0 grep
    │
    └─ 複雜工作 ──► vein recall "<scope>"  → task digest → 開始工作
                          │
                          ▼
                     只在 vein 找不到答案時才 grep/read
```

**小問題的 virtuous cycle：**

```
vein ask "X 為什麼這樣？"
    │
    ├─ .vein/ 有答案 → 直接給，0 grep ✓
    │
    └─ .vein/ 沒有答案
           │
           ▼
        Claude grep/read 找答案
           │
           ▼
        vein log lore "X 為什麼這樣：因為..." ← 記進去
           │
           ▼
        下次同類問題 → vein ask 直接回答 ✓

每個被問過的問題，自動讓 .vein/ 更完整
```

**`.vein/BRIEF.md` 的 git 策略：**
- 進 `.gitignore`（generated file，不 commit）
- 每台機器 / 每個 session 各自 generate
- 原始 lore entries 才是 git-tracked 的 source of truth

**對 CLAUDE.md 的影響：**
- CLAUDE.md §6 SOP 第一步改為：先跑 `vein brief`，再讀 CLAUDE.md（brief 更精準）
- 長期目標：CLAUDE.md 只剩 30 行 meta-index，orientation 全部靠 `vein brief`

**Revisit when:**
- brief 品質不夠好（llama3.2:3b 壓縮後資訊失真）→ 換 qwen2.5-coder:7b
- brief 生成太慢（> 5 秒）→ 考慮純 rule-based 生成，不過 LLM

---

### D-015 — Model backend 抽象化：支援 ollama + Rapid-MLX（及未來其他 backend）

**Date:** 2026-05-27

**Context:** Rapid-MLX（Apple Silicon 原生推論）比 ollama 快 4.2x，API 格式與 ollama 相容。
若 Phase 1 把 model backend hardcode 成 ollama，之後要支援 Rapid-MLX 就要改很多地方。

**Choice:** Phase 1 就把 model backend 抽象成 config，不 hardcode。

**config.yaml 設計：**

```yaml
version: 1
model:
  backend: ollama            # ollama | rapid-mlx | （未來：lmstudio、jan）
  base_url: http://localhost:11434
  embed_model: nomic-embed-text
  digest_model: llama3.2:3b
  polish_model: qwen2.5-coder:7b
  analyze_model: deepseek-r1:14b
```

切換到 Rapid-MLX 只需改 `backend` 和 `base_url`，其他不動。

**為什麼 Rapid-MLX 值得支援：**
- `vein brief` 從 ~5-8 秒 → ~1-2 秒
- `vein ask` 從「有等待感」→「秒回」
- `vein log` polish 從 ~3-5 秒 → < 1 秒
- 整體 UX 跳一個 tier

**Trade-off：**
- Rapid-MLX 不是所有 Mac 都能裝（需要 Apple Silicon + macOS 13+）
- ollama 是目前更廣泛支援的選項，保持為預設
- Linux / Windows 用戶繼續用 ollama

**Architectural invariant（Phase 1 就要做對）：**
- 所有 ollama HTTP call 必須透過 `ModelBackend` abstraction class，不可直接 `requests.post("http://localhost:11434/...")`
- backend 切換是 config change，不是 code change

**Revisit when：** Rapid-MLX API 與 ollama 有 breaking 差異（目前相容）。

---

### D-016 — `vein import` 子命令：用 MarkItDown 擴大 lore capture 來源

**Date:** 2026-05-27

**Context:** Microsoft 開源的 MarkItDown（`pip install markitdown`）可把 PDF / Word / Excel / PPT / HTML / 圖片全轉成 Markdown。
目前 `vein log` 只接受手動文字輸入，無法從文件、會議紀錄、規格書捕捉 lore。

**Choice:** Phase 2 新增 `vein import` 子命令，底層用 MarkItDown 作為文件解析層。

**命令設計：**

```bash
# 從檔案捕捉 lore
vein import --from-file spec.pdf
vein import --from-file meeting_notes.docx
vein import --from-file design_decision.xlsx

# 從逐字稿捕捉 lore（配合 jt-live-whisper 等轉錄工具）
vein import --from-transcript meeting_2026-05-27.txt
```

**內部流程：**
```
input file
    │
    ▼
markitdown → markdown string
    │
    ▼
ollama（qwen2.5-coder:7b）：
  "這份文件裡有哪些 trade-off 選擇或架構決策？
   列出候選 lore entries（每條一句話）"
    │
    ▼
Rex 確認哪些要記 → vein log 批量存入
```

**為什麼這個功能重要：**
很多 decision 不是在寫 code 時產生的，而是在讀規格書、開 PRD 會議、查技術文章時產生的。
MarkItDown 讓 Vein 從「只捕捉 code-time decision」升級為「捕捉任何來源的 decision」。

**Dependencies：**
- `markitdown` 加入 `pyproject.toml` optional dependencies（`pip install lode-vein[import]`）
- 不強制依賴，`vein import` 若未安裝 markitdown 給出明確提示

**Revisit when：** MarkItDown 對某些檔型轉換品質不佳（例如複雜 PDF 表格），考慮加入 pymupdf 作為 PDF fallback。

---

### D-017 — `vein import --from-doxygen`：從 Doxygen XML 批量 capture lore

**Date:** 2026-05-27

**Context:** IC FW 大型專案通常已有 Doxygen 文件。Doxygen XML 包含 `@pre`（前置條件）、`@post`（後置條件）、`@note`（行為備忘）、`@warning`（已知危險），這些都是 architectural invariant 和 pitfall 的天然來源，但沒有工具把它們轉成可搜尋的 decision lore。

**Choice:** Phase 2 在 `vein import` 下新增 `--from-doxygen` 模式，parse Doxygen XML → 批量生成 lore candidates → 工程師確認後寫入 `.vein/`。

**命令設計：**

```bash
# 從單一 header 的 Doxygen XML 批量 import
vein import --from-doxygen hal/doxygen/xml/hal__dma_8h.xml

# 從整個 module
vein import --from-doxygen hal/doxygen/xml/ --tag hal

# dry-run：只列出 candidates，不寫入
vein import --from-doxygen hal/doxygen/xml/ --dry-run
```

**內部流程：**

```
Doxygen XML
    │
    │  parse @pre @post @note @warning
    ▼
候選清單（raw text）
    │
    │  ollama (qwen2.5-coder:7b)：
    │  "判斷每條是 decision / lore / pitfall，給出 1 句 title"
    ▼
互動式確認列表（y/n/edit 每條）
    │
    ▼
批量 vein log → .vein/
```

**為什麼需要這個功能：**
- 存量 Doxygen 文件一次 import，瞬間讓新建的 `.vein/` 有 lore 基礎
- 不需要從零開始 capture；FW 工程師已有的 `@note` 習慣可以直接轉換
- 特別適合：新專案接手、工程師離職前 lore 搶救

**Doxygen tag 對應 Vein type：**

| Doxygen tag | Vein type | 說明 |
|---|---|---|
| `@pre` / `@post` | `decision` | Architectural invariant，API 使用規則 |
| `@note` | `lore` | 行為備忘，值得記錄但非 pitfall |
| `@warning` | `pitfall` | 已知危險，直接對應 pitfall |
| `@deprecated` | `pitfall` | 舊路徑警示 |

**Dependencies：**
- Python `xml.etree.ElementTree`（stdlib，不需額外依賴）
- `vein import` 基礎框架（D-016 的 MarkItDown 整合完成後）
- ollama with `qwen2.5-coder:7b`（D-015 的 model backend 抽象）

**Trade-off（vs 純手動 capture）：**
- 自動化：降低 capture 摩擦，但品質不如手寫（有些 `@note` 是實作細節，不是 lore）
- 解法：`--dry-run` + 互動確認讓工程師 filter，不是全自動 commit

**Revisit when：** Doxygen XML schema 跨版本不穩定（rare），或工程師不寫 Doxygen（考慮改 parse inline comment）。

---

### D-018 — Cross-environment lore：SystemC 假設不等於 MP 行為

**Date:** 2026-05-27

**Context:** IC FW 開發用 QEMU + SystemC co-simulation 做 pre-silicon 驗證，但 SystemC model 永遠是近似值（TLM，非 cycle-accurate）。Pre-silicon 通過的 FW，post-silicon 可能因 timing 差異失敗。這種「跨環境行為差異」是 FW 開發中最高價值的 lore，也最容易在人員流動時流失。

**Choice:** 在 `.vein/` lore schema 中明確支援 `cross_env` tag 和 `env_delta` 結構化欄位，讓 SystemC ↔ ASIC 的差異可被精確搜尋。

**Lore entry 格式（SystemC vs MP delta）：**

```yaml
---
id: 20260527-170000
type: pitfall
title: "SystemC DMA completion latency ≠ real ASIC"
tags: [dma, timing, systemc-vs-mp, cross-env]
date: 2026-05-27T17:00:00+08:00
env_delta:
  systemc: "固定 100ns（TLM model 限制）"
  real_asic: "50~300ns depending on NAND state"
  affected_paths: [hal_dma_submit, gc_trigger_wait]
related: [D-017]
---

FW 的 DMA timeout 不能照 SystemC 數字設定。
SystemC model 的 DMA latency 是常數（TLM abstraction），
真實 ASIC 因 NAND state、thermal、wear-leveling 影響，
最壞情況可達 SystemC 的 3x。

Timeout 設定必須以真實 silicon 最壞情況（300ns + 20% margin）為準。
已知受影響：hal_dma_submit timeout, gc_trigger_wait timeout。
```

**`vein recall` 的威力（跨環境查詢）：**

```bash
# 所有 SystemC 跟 real silicon 的已知差異
vein recall "systemc vs mp delta"

# DMA 相關的跨環境問題
vein recall "dma cross env"

# 新的 pre-silicon → post-silicon 驗證
vein recall "timing delta"
→ 馬上知道哪些 path 在 post-silicon 要特別注意
```

**為什麼需要專門的結構：**
1. 這類 lore 有獨特的時效性：pre-silicon 建立，post-silicon 驗證（可能推翻或補充）
2. 需要雙向查詢：「這個 API 在 SystemC 下有哪些已知限制？」以及「這個 ASIC 行為有 SystemC 對應的 lore 嗎？」
3. `env_delta` 欄位讓 lore 的準確性更高（不只是「有差異」，而是「差多少、影響哪裡」）

**對 `vein log` 的影響：**
- Phase 1 先用 tag（`systemc-vs-mp`）搜尋
- Phase 2 若 IC FW use case 成為重點，才把 `env_delta` 加入 schema
- 不在 Phase 0 做（先有 generic lore 比 specialized schema 更重要）

**推廣方向（IC FW 以外）：**
- 同樣的「跨環境行為差異」在其他領域也存在：dev/staging/prod 行為不同、ARM vs x86 差異、CPU architecture 差異
- `env_delta` 是 generic pattern，不只是 IC FW 專用

**Revisit when:** FW use case 真實 dogfood（有人把 Vein 用在真實 IC 專案）之後，根據實際使用回饋調整 schema。

---

### D-019 — Vein vs 原生 AI memory（claude-pers-mcp 等）：兩層不競爭

**Date:** 2026-05-27

**Context:** Claude Code 有內建 memory（`~/.claude/memory/`），各 IDE 也有類似的 memory MCP。有人會問：「有了原生 AI memory，Vein 還有什麼用？」

**Choice:** 兩者解不同層的問題，正確姿勢是同時用。

**根本差異：**

```
原生 AI memory (claude-pers-mcp 等)  →  "Rex 這個人是誰？"
Vein (.vein/)                        →  "這個專案為什麼長這樣？"
```

| 維度 | 原生 AI memory | Vein |
|---|---|---|
| Scope | 全局，跟著 user | Per-project，跟著 repo |
| 儲存位置 | `~/.claude/memory/`（本機） | `.vein/`（repo 內） |
| Git-tracked | 否 | 是 |
| 多 AI 工具可用 | 否（Claude 獨有） | 是（plain markdown，任何工具） |
| 主要內容 | User 偏好、跨專案習慣 | 決策 rationale、pitfall、lore |
| 寫入方式 | Claude 自動判斷要記什麼 | 工程師刻意 `vein log` |
| Pitfall + chaos seed | 不支援 | 一等公民 |
| 可共享給隊友 | 否 | 是（git clone 帶走全部 lore） |

**什麼情況原生 memory 更好：**
- 跨專案的個人偏好（"Rex 喜歡 terse 回答"）
- 自動 capture，不需要工程師刻意操作
- 單人 solo workflow，不需要 team sharing

**什麼情況 Vein 更好：**
- 「為什麼這個 API 長這樣」類的專案決策
- 多人團隊，lore 要 share
- 換 AI 工具（從 Claude Code 換 Cursor）不丟記憶
- IC FW / 複雜系統，pitfall 有 reproduction steps
- 工程師離職，lore 不隨人走

**Vein 的真實弱點（相對原生 memory）：**
- 需要手動 `vein log`，原生 memory 是全自動
- Phase 2 git hook / Phase 3 MCP write-back 之前，capture 紀律依靠人

**Revisit when:** 若未來 Claude Code 支援 per-project memory（住在 `.claude/` 之類），重新評估定位。目前（2026-05-27）原生 memory 仍是 user-global，無 project scope。

---

### D-020 — AI provider config 與 command system 設計

**Date:** 2026-05-27

**Context:** Vein 需要三個 config/tooling 層：
1. AI provider 設定（Claude/Gemini/OpenAI/local ollama 的 model 選擇、routing）
2. 開發指令快速選單（類 cmd_entry.csv 模式）
3. Folder-based sequential batch runner（有 log，fail 即 break）

**Choice & 檔案配置：**

```
vein/
  config/
    ai_providers.yaml    ← model names, endpoints, routing, budget tiers（committed）
  .env                   ← API keys（gitignored）
  .env.example           ← key template（committed）
  cmd/
    cmd_vein_entry.csv   ← 開發指令清單（同 py/ 的 cmd_entry.csv 格式）
    cmd_vein_entry.py    ← standalone runner（不依賴 py/ 的 cmd_entry_core）
    run_batch.py         ← folder runner with full .log
    batch/
      01_lint.sh
      02_test.sh
      03_validate_docs.py
    logs/                ← gitignored，run_YYYYMMDD_HHMMSS.log + run_latest.log symlink
```

**ai_providers.yaml 的關鍵設計：**
- `local` block：ollama / rapid-mlx，Phase 0 primary backend
- `claude` / `gemini` / `openai` block：`enabled: false` 預設，按需開
- `routing` block：每個 task role（embed / digest / polish / analyze / ask / review）指定 provider 優先序
- `budget` block：2k / 32k / 200k / raw 四個 tier，對應 D-011 的 tiered digest 設計
- 非敏感設定全在 yaml；API key 只在 .env

**run_batch.py 的關鍵設計：**
- 掃 folder → natural sort（01_xxx 先於 02_xxx，10 不早於 09）
- 支援 `.sh`（bash）+ `.py`（sys.executable）
- 每 step 完整 capture stdout/stderr 進 log（DEBUG level）
- fail 預設 break；`--no-break` 繼續但記 warning
- log 路徑：`<folder>/logs/run_YYYYMMDD_HHMMSS.log` + `run_latest.log` symlink
- 環境變數注入：`VEIN_BATCH=1`、`VEIN_PROJECT_ROOT`
- exit code：0=all OK，1=failure，2=bad args

**cmd_vein_entry.py vs py/ cmd_entry_core 的差異：**
- 不 import py/ 的 cmd_entry_core（vein self-contained）
- 不寫 schedule_history.csv（vein 沒有 task_runner 依賴）
- 簡化但保留同樣的 CSV format、shell: prefix、$var 展開

**Routing 策略（Phase 0）：**
- embed / digest / polish / analyze → 全部 local（不花錢）
- ask → local first，fallback cloud
- review → cloud first（重推理任務）

**Revisit when：** Phase 1 開始用 cloud API 做 `vein review` 時，補上 rate limiting / cost tracking。

---

### D-021 — Automated Context Passing：消除 copy-paste 循環

**Date:** 2026-05-29

**問題：** 開發中最浪費時間的 pattern 是手動 copy-paste 循環：
run → fail → copy error → 開 Claude/Gemini tab → paste → copy fix → paste 回 terminal → repeat。
每個循環 30–90 秒，每天 10–20 次。更深的問題是 context 斷裂（AI 沒有專案背景）和知識流失（fix 後沒有記錄）。

**核心洞察：** copy-paste 是「人工做 context routing」的症狀。解法是讓程式自動路由：
錯誤 → vein search → 命中就顯示 pitfall fix，未命中才呼叫 AI（帶 lore context）→ 記錄回 vein。

**Choice：** `vein pipe` + `vein run` + shell hook 三層架構

```
# 層次 1: pipe（現在就能用）
cargo check 2>&1 | vein pipe --ai

# 層次 2: run wrapper（現在就能用）
vein run cargo check --ai --log

# 層次 3: shell hook 後，一鍵 triage 上一條失敗指令
cargo check   # fail
vt --ai       # 自動 re-run + pipe 給 vein
```

**AI 在這個架構裡是函數節點，不是對話對象：**
- `qwen2.5-coder:7b` = error triage 函數（input: cmd+error+lore, output: fix）
- `nomic-embed-text` = 語意搜尋函數（input: text, output: vector）
- 人只在 AI 答不了或需要 trade-off 時介入

**error term extraction（`triage.py`）：**
- 過濾 Compiling / warning / INFO / DEBUG 等 noise 行
- 抓 Error / Exception / FAILED / note 等 signal 行
- 壓縮到 ≤600 chars，作為 vein grep query + AI prompt context

**關鍵 trade-off：**
- `vein run CMD` 需要 subprocess（不支援 alias、shell function）；
  `vein pipe` 更通用，任何指令都能 pipe 給它
- shell hook `vt` 用 `fc -ln -1` 拿 last command，zsh only（bash 需要另一個方法）
- AI 建議是 local qwen2.5-coder:7b，離線 / 慢機器可用 `--no-ai` 只查 vein

**Files：**
- `src/vein/core/triage.py` — error extraction + ollama triage call
- `src/vein/commands/pipe.py` — `vein pipe` command
- `src/vein/commands/run.py`  — `vein run` command
- `shell/vein.zsh`            — zsh integration (vt / vr / vp / vb aliases)
- `docs/auto_context.md`      — 完整設計文件 + 使用場景

**Revisit when：** Phase 0.3 MCP server 完成後，改成 AI 直接 call `mcp:vein:search`，不再需要 pipe。

---

### D-022 — Sunnywalker：multi-agent workflow runner 命名與設計

**Date:** 2026-05-29

**問題：** 開發一個 feature 需要多輪 code → validate → fix → review 循環，每次手動跑腳本、看 log、決定下一步，還是靠人腦路由。需要一個可以自動執行「AI A coding → AI B validate → AI C report → AI D review → loop」的 pipeline。

**命名：sunnywalker**
- 有方向感（walker = 按步驟往前走）
- 暗示 AI agents 協作（多個 walker）
- 命令入口：`vein walk`（subcommand group）
- 狀態檔：`.vein/WALKER.json`（gitignored）

**架構選擇：YAML workflow definition + WorkflowRunner state machine**

```
sunnywalker.yaml           ← 定義步驟 + routing rules（committed）
.vein/WALKER.json          ← runtime state（gitignored，可 resume）
shell/sunnywalker/         ← 每個 step 的 script templates
  b_validate.sh            ← 使用者自訂 test/lint 指令
  c_report.py              ← 自動從 vein 生成 markdown report
  d_review.py              ← ollama 讀 vein entries → PASS/FAIL
  e_ca.sh                  ← git commit
```

**on_fail 路由設計：**
- `stop` — 最保守，等人介入
- `goto:code` — 自動回 coding（最常用）
- `retry:3` — 自動 retry，適合 flaky tests
- `skip` — non-critical step（e.g. report 失敗不阻擋）
- `ai_decide` — ollama 決定跳去哪個 step（實驗性）

**human_step 設計：**
- `human_step: true` 的 step 會暫停等 Enter
- 這是「你 / AI 做完 coding 後按 Enter 繼續」的接口
- 未來 MCP 模式下，AI coding agent 完成後直接 signal done，不需要 human Enter

**Templates 依 tech stack：**
- `--template python`：pytest + ruff
- `--template rust`：cargo check + cargo test
- `--template tauri`：tsc + cargo check（for Lode）

**Vein 在 sunnywalker 裡的角色：**
- b_validate.sh 失敗 → `2>&1 | vein pipe` → 自動 triage + 記錄 pitfall
- c_report.py 從 vein 讀 entries，輸出 WALKER_REPORT.md
- d_review.py 讀近 7 天 vein entries，AI 決定 PASS/FAIL
- 整個 workflow 的 "shared memory" 是 `.vein/`，不是 WALKER.json

**Key trade-off：**
- WorkflowRunner 故意設計成「dumb runner」— 只跑 script、讀 exit code、routing
- AI logic 全在 scripts 裡（ollama call in d_review.py），不在 runner
- 好處：任何 script 都能插入，runner 不需要知道 AI 細節
- 壞處：scripts 需要手動維護；未來 MCP 模式可以消除這個 overhead

**Files：**
- `src/vein/core/workflow.py`  — WorkflowRunner, WalkerState, StepDef
- `src/vein/commands/walk.py`  — `vein walk` subcommand group
- `docs/sunnywalker.md`        — 完整設計文件 + 使用指南

**Revisit when：** Phase 0.3 MCP server — AI coding agent 直接 signal `vein walk step code pass`，不需要 human Enter。

---

### D-023 — SunnyWalker `orchestrator/` 與 `vein walk` 是同一件事的兩個成熟度；不另造 agent

**Date:** 2026-05-29

**問題：** Rex 想打造「未來高效創建 app」的框架，建立/驗證/失敗/除錯流程要能跨專案復用（下一個可能是 SunnyFly app），問 Vein 能否做到、或需不需要再造新 agent。

**現況盤點：**
- SunnyWalker 專案（`/Users/lion/Documents/SunnyWalker/`）已有可跑的 `orchestrator/`（claude_loop）：4-agent ring（A Coder → B Validator → C Reporter → D Reviewer）、append-only ring 檔當 baton、`MAIN_ENTRY.md` resume manifest、heartbeat crash recovery、daily report、auto-archive，並附 `REUSE.md`（複製資料夾 + 改 `config.yaml` / `validate.sh` / spec 即可換專案）。
- Vein 這邊 [D-022](#) 已設計 `vein walk`（sunnywalker runner）+ `.vein/` 當 shared memory。

**結論（thesis）：兩者是同一概念的兩個成熟度，不是兩個系統。**
- SunnyWalker 的 `orchestrator/` = `vein walk` 的**獨立原型**（standalone、已驗證可跑、但記憶綁在 per-project 的 ring 檔 + daily log，archive 後跨不了專案）。
- `vein walk`（D-022）= **一般化版本**，把 shared memory 從 ring 檔換成 `.vein/`，因此 lore 能跨專案 recall。

**回答 Rex 的兩個問題：**
1. **不需要再造新 agent。** 「框架」= loop 引擎 + 記憶層兩塊：loop = `vein walk`（原型已存在於 SunnyWalker/orchestrator），記憶 = `.vein/`。Vein 不是 agent，是掛在現有 A/D agent 上的記憶 tool（A 開工 `vein recall` 注入 digest、D 收工 `vein log` 抽 decision/lore）。
2. **流程復用 ≠ 經驗復用。** orchestrator 已解決「流程復用」（換專案重跑同一條 ring）。Vein 補的是「經驗復用」——讓專案 N+1 真正受益於 N 學到的東西，而不是每個新 app 從零冷啟。

**分層模型（記給接手）：**

| 層 | 職責 | 現況 |
|---|---|---|
| scaffold | 開新 app 骨架（setup_day0.sh / project.yml / xcodegen） | SunnyWalker 有，per-project |
| loop（`vein walk`） | 建立/驗證/失敗/除錯 ring | SunnyWalker orchestrator 已跑；vein walk 待實作 |
| memory（`.vein/`） | 跨專案 decision + debug lore digest | **缺，這是 Vein 的價值點** |

**決策：SunnyWalker 列為 Vein 的第二個 dogfood 對象**（與 Lode 並列）。理由：
- 專案 brief 本來就要驗 "generic Python project"；SunnyWalker orchestrator 是個自動化 multi-agent loop，是「digest 能不能取代重讀 docs」最嚴苛的壓力測試（agent 沒有人類直覺，digest 不準就立刻爆）。
- 同時驗證跨語言：Lode = Tauri/Rust/TS，SunnyWalker = Swift/iOS。cert-lore（見 [D-024](#)）在兩者之間共用，正好證明跨專案 recall 的價值。

**Trade-off accepted：**
- 短期 SunnyFly 要快 → 直接照 `orchestrator/REUSE.md` 複製，先有可跑的 loop，`.vein/` 記憶層後補。不必等 `vein walk` 寫完。
- 長期收斂方向：`vein walk` 取代手抄 orchestrator，`.vein/` 取代 per-project ring 當記憶。

**Revisit when：** `vein walk` 實作完，回頭評估是否把 SunnyWalker 的 `orchestrator/` migrate 過來（或保留為獨立原型）。

---

### D-024 — Lode lore 回填：既有 50+ 雷區 + app-cert docs 如何進 `.vein/`

**Date:** 2026-05-29

**問題：** Lode 修 bug、送 App Store 認證踩了大量雷，散在 `docs/` 66 個檔（`decisions.md` ~50 條 🔴、`PITFALLS_*.md`、`APPLE_REJECTION_*`、`MAS_SUBMISSION_*`、15 份 `SESSION_REPORT_*`）。如何讓這些經驗被 Vein 保留、且未來可 recall。

**關鍵 reframe：問題不是「沒寫下來」，是「寫下來但無法被有效取用」。** Lode 的 lore 早就寫得很完整，痛點是：
1. 散在 66 個檔，新 session 要 grep / 通讀才找得到。
2. 自由格式 markdown，無結構化 tag、無 semantic recall。
3. **跨不了專案**——SunnyWalker（Swift app）撞到同類 cert 問題時，完全用不到 Lode 的教訓。

**兩軌策略：**

**軌一：bulk backfill 既有 docs（一次性）** — 走 [D-016](#) `vein import --from-file`（MarkItDown）。優先吃高密度檔：`decisions.md`、`PITFALLS_*.md`、`APPLE_REJECTION_*`、`MAS_*`。pipeline：markdown → qwen2.5-coder:7b 抽 candidate（type/title/body_draft）→ interactive y/n/e 確認 → batch `vein log`。**重點：interactive 確認不可省**，50 條雷靠 LLM 全自動分類 type/tag 必有誤判。

**軌二：capture-going-forward（長期）** — 在 sunnywalker loop 裡，D Reviewer 收工 `vein log` 抽當天 decision/lore；`validate.sh` 失敗 `2>&1 | vein pipe` 自動 triage 成 pitfall（[D-022](#) 已設計）。新雷出現當下就進 `.vein/`，不再事後追。

**Lore 分兩類，cert-lore 跨專案價值最高：**

| 類別 | 例子（Lode 實際） | scope |
|---|---|---|
| code/debug pitfall | stale closure 吃字、`import * as` 撐爆 bundle、`convertFileSrc` vs Blob URL | project + subsystem（多半綁 Tauri/React，跨專案弱） |
| **platform / cert lore** | App Store Connect 禁 alpha channel、`com.apple.quarantine` xattr 觸 91109 reject、macOS IAP screenshot 必須 exact 2880×1800 | **跨專案強**——咬任何上架 Mac/iOS app 的人 |

**設計決策：schema 用 `tags` 標記 cross-project lore。** cert/platform 類加 `tags: [appstore, macos, cert, cross-project]`，讓 SunnyWalker / SunnyFly 的 `vein recall "app store reject"` 能跨 `.vein/` 撈到 Lode 的教訓。這也回頭定義了一個需求：**`vein recall` 要支援跨多個 `.vein/` 的 global/shared scope**（Phase 0.x 補；v0.1 先 per-project）。

**Trade-off accepted：**
- 不追求一次回填全部 66 檔。先 import 4~5 個高密度檔（cert + decisions），夠啟動 dogfood 即可；其餘 SESSION_REPORT 等低密度檔按需再撈。
- 手工種子（見本次 session 建的 `lode/.vein/`）先證明 schema，import 工具寫完再 bulk。

**Files（本次 session 起手）：** `/Users/lion/Documents/lode/.vein/`（config + STATUS + 3 條 exemplar entry），作為 Lode dogfood 與 import 工具的 golden-output 對照。

**Revisit when：** `vein import --from-file` 實作完，跑一輪 bulk import Lode docs，比對自動產出 vs 手工種子的品質落差。

---

### D-025 — Cross-project recall：global registry + grep，不建跨專案 index

**Date:** 2026-05-29

**問題：** [D-024](#) 點名 cross-project recall 是讓新專案（SunnyWalker/SunnyFly）受益於舊專案（Lode）lore 的關鍵——尤其 cert lore。需要一個機制讓 `vein recall`/`ask` 跨多個 `.vein/` 搜尋。

**Choice：** global registry（plain text）+ per-repo grep 聚合，加 `-x/--cross-project` flag。

- **Registry：** `$XDG_CONFIG_HOME/vein/registry.txt`（default `~/.config/vein/registry.txt`），一行一個 project root 絕對路徑。`vein init` 自動註冊（含對既有 repo 再跑 init 也會補登記）。`roots()` 回傳時自動 dedup + 濾掉已不存在 `.vein/` 的路徑。
- **搜尋：** `store.cross_project_search(query, exclude_root, limit)` 對每個註冊 repo 跑 `grep_entries`（純 keyword），結果標註 project name、依 score 合併排序。
- **Flag：** `recall -x` / `ask -x` 在本地結果之後附「── from other projects ──」區塊。

**為什麼用 grep 不用跨專案 embedding index：**
- 跨專案 recall 本質是廣域 keyword sweep，grep 純 Python、零依賴、**不需要 ollama、不需要對方 repo 已 build index**（對方 index 可能因 [D-?](#)（sqlite-on-FUSE pitfall）被 relocate 或根本沒建）。
- scale 夠：每 repo 數十～數百條 entry，grep 線性掃可接受。
- 本地搜尋仍保留 semantic/FTS 品質；只有 cross-project 段落降級成 keyword。這個 trade-off 對「我在別的專案大概踩過類似雷嗎」這種探索式查詢剛好。

**Rejected：**
- 集中式單一大 index（所有專案 embeddings 進一個 DB）：破壞 Vein 的 per-project / git-tracked / 單檔 rsync 模型（[D-002](#)），且要解決跨 repo embedding 版本一致性。
- 每次 cross-project 都即時對每個 repo 跑 ollama embed：慢、且 ollama 不在就完全不能用，違背 graceful-degrade 原則。

**驗證（dogfood）：** 空的 SunnyWalker repo 跑 `vein ask "app store reject" -x` → 正確撈出 Lode 的 alpha-channel cert pitfall，標註來源 `lode`。tests：`tests/test_registry.py`（registry idempotent / 濾 missing / init 自動註冊 / cross-project 找得到他人 lore / 排除自身）。共 38 passed。

**Files：** `src/vein/core/registry.py`（新）、`src/vein/core/store.py::cross_project_search`、`src/vein/commands/{init,recall,ask}.py`。

**Revisit when：** registry 條目變多、或想要「semantic 跨專案」時，評估是否做 opt-in 的 shared embedding index（但先確認 grep 真的不夠用）。

---

### D-026 — 資料分層邊界 + Lore 是會衰變的斷言（不是永恆事實）

**Date:** 2026-05-29

**問題：** AI 協作會狂產資料（Markdown / JSON / AST / test log）。兩個風險：(1) Vein 被當垃圾桶 → 檢索撈出過期垃圾、token 塞爆；(2) 更隱蔽——**寫入當下正確的 lore，很久以後會變錯**，因為世界 / 平台 / AI 在變（Apple 改 cert 規則、某 API 改簽名、某「最佳實踐」被取代）。對 → 錯是時間造成的，write-time 擋不住。

---

**原則 A — 資料分層：distilled-in / raw-out。**

Vein 只存「蒸餾過的 why」（decision / pitfall / lore），**raw artifact 永遠不進 Vein**。對到 Hot/Warm/Cold：

| 層 | 內容 | 位置 | Vein 的角色 |
|---|---|---|---|
| Hot | 當前 sprint context | 雲端 LLM context cache | 不存；只用 `brief`（≤2K digest）決定餵什麼進去 |
| Warm | ADR / 決策 / 雷區 | **`.vein/` 本體**（typed markdown + git） | core |
| Cold | AST / test log / SSD log | 旁邊的 Parquet / DuckDB（columnar，~1/10 JSON size） | 只存一條 `type: reference` 指過去（`source_url`），不存 raw |

效果：Vein 永遠只有幾百~幾千條精煉 entry（[D-002](#) ≤10K chunks，FTS5 + flat cosine 都快），GB 級 raw 在 cold store，要時才撈。**邊界守則：任何「機器產的大量原始輸出」一律進 cold layer，Vein 端只留指標。**

---

**原則 B — Lore 是 point-in-time 斷言，不是永恆事實。**（Rex 2026-05-29 補充）

[原則 A 之外最關鍵的一條]。**write-time dedup（FTS5 ≥80% title match）只處理「空間冗餘」——兩條 entry 講同一件事。它抓不到「時間衰變」——一條當年對、現在錯。** 因為寫入當下不可能知道未來會怎麼變。所以：

- **「語意去重在 ingestion 當下做」這句在當下成立，但不能當作全部。** 它是必要、非充分。
- correct → wrong 的轉變**只能事後偵測**，靠週期性 re-validation，不是一次性 write-time gate。
- 因此 `vein consolidate` 的本質是 **truth-maintenance pass，不是 dedup GC**。

**抗腐爛機制（roadmap，分 schema 改動 vs pass）：**

1. **volatility 分級（schema，新 frontmatter 欄位）：** `volatility: external-fact | internal-invariant`。
   - `external-fact`（Apple cert 規則、vendor API、「現在最佳做法」）→ 衰變快，短 revalidation TTL。
   - `internal-invariant`（我們的 mmap 設計、為何走 native drag-drop）→ 衰變慢，幾乎不過期。
   - recall 對兩類給不同 age-decay 斜率。
2. **temporal metadata（schema）：** 既有 `date` 之外加 `verified_at`（最後一次確認仍為真）；既有 body 的 **`Revisit when:`** section 升級成 machine-readable trigger（條件命中 → 自動排進 re-validation queue）。
3. **status-aware + age-decay recall ranking：** schema 已有 `active / resolved / superseded`，但 recall 還沒用。改成：`superseded` 降到底、`active` 但超過 volatility TTL 的標 ⚠「captured N months ago, may be stale」、age-decay 排序。**這才是真正防「撈出過期垃圾」的關鍵，光靠 write-time 不夠。**
4. **`vein consolidate`（pass，Phase 2）：** 週期或 on-demand 重新檢視 entries——
   - 偵測 supersession（新 entry 與舊衝突 → 舊的標 `superseded` + 填 `superseded_by`）。
   - 標 stale（過 TTL 或 `Revisit when` 命中）→ 排進**人工/LLM 重驗 queue**。
   - **不自動刪**，輸出候選清單走 interactive confirm（跟 ingestion 同一套閘哲學）。

> 對照系統層的 memory 原則：「recalled memory 反映寫入當時為真的狀態——若提到某 file/function/flag，推薦前要先驗證它還存在。」Vein 的 lore 一模一樣：**capture 的是 point-in-time truth，用之前要當它可能已過期。**

---

**Trade-off accepted：**
- volatility / verified_at 增加 capture 時的一點 metadata 負擔 → 給合理 default（log 時 LLM 可猜 volatility，人工可改）。
- consolidate 需要算力（embedding 比對 + LLM 重判）→ 設計成 off-peak / on-demand，不擋日常 recall。

**Rejected：**
- 「write-time curate 就夠，不需要事後 pass」：被 Rex 的時間衰變論點否決——空間去重 ≠ 時間真值維護。
- 自動刪過期 entry：違背「lore 是 project asset、debug 史要保留」；過期的標 superseded/archived，不刪（resolved pitfall 仍是歷史價值）。

**Files（待實作，標 Phase）：** schema 改動（`volatility` / `verified_at`）+ recall ranking → Phase 1；`vein consolidate` → Phase 2。data_format.md §2 schema 與 §4 quality gates 需依本決策更新。

**Revisit when：** entry 數破千、或 dogfood 中真的撈到「當年對現在錯」的 entry——那會是驗證 consolidate 設計的第一個 golden case。

---

## 已知 Known Issues

(空 — 還沒寫 code，待累積)

---

### D-027 — 捕獲策略：debrief > hook > MCP > manual（2026-05-31）

**問題：**
自動捕獲 → 雜訊太多；手動捕獲 → 沒人做。這個矛盾的解法是找到正確的觸發點。

**決定：四層捕獲架構，按品質排序**

```
1. MCP vein_log()     — Claude 自己決定記什麼，品質最高，但只在 AI session 中
2. vein debrief       — commit 後 AI 掃 diff，自動提取，無需人工，中等品質
3. vein hooks install — post-commit 自動跑 debrief --silent，完全透明
4. vein log (手動)    — 最高品質，不強求
```

**Why debrief 是主力：**
- `git commit` 是開發者已經在做的動作，不改習慣
- diff 是完整的「這次做了什麼」記錄
- 本機 AI 在 commit 後有充分上下文判斷「值不值得記」
- 沒有 ollama → graceful skip，不影響工作流
- 互動式 hook（問 d/l/p/Enter）被廢棄：太打斷 flow，跟「不改習慣」矛盾

**Rejected approaches:**
- PostToolUse hook（每個工具呼叫都觸發）：捕捉「做了什麼」，沒有「為什麼」
- Stop hook 全收：每個 Claude turn 都記，噪音爆量
- 互動式 post-commit prompt：打斷 git 工作流，用戶會關掉

---

### D-028 — Multi-agent / Multi-project：.vein/ 是 AI-agnostic 共享記憶層（2026-05-31）

**定位重新確認：**

Vein 的真正護城河不是「比其他 note 工具更好」，而是**唯一一個以 repo 為單位、AI-agnostic 的決策記憶層**。

```
沒有 Vein：
  Claude session → 記在 Claude memory（Claude 限定）
  Gemini session → 重新載入，沒有上一次的 context
  換工具 → 全部歸零

有 Vein：
  任何 AI session → vein brief → 同一份 .vein/ ground truth
  Claude 記的，Gemini 也能讀
  換工具，.vein/ 跟著 repo 走
```

**Multi-agent 的具體價值：**
1. 每個 AI 在 session 開始呼叫 `vein_brief()` → 相同 orientation，不重複解釋
2. Agent A 做了決定 → `vein_log()` → Agent B 下次讀到
3. `vein debrief` 在 commit 後自動補捉 Agent 沒記到的部分
4. 跨專案：`vein recall -x` 讓 Lode 的決定在 Vein 開發時也可見

**Multi-project 的具體價值：**
- Rex 同時跑 Lode / Vein / fubon_stock / YSK pipeline
- 每個有自己的 .vein/
- `vein recall -x` 跨專案搜尋
- 未來：`vein global brief` 跨所有專案的 orientation digest

**Marketing headline 修正：**
- 舊：「決策 lore 歸檔工具」
- 新：「**AI-agnostic project memory — 任何 AI、任何 session、同一份決策記憶**」

---

### D-029 — 錯誤方向修正：縮焦 core，把 walk/run/pipe 降級（2026-05-31）

**現況：** vein 有 13 個 command。對新用戶來說太多，定位模糊。

**問題命令：**

| Command | 問題 |
|---------|------|
| `vein walk` (sunnywalker) | 完整 workflow runner，跟「決策 lore」定位不同。是 Rex 的個人工具，不是 vein 的核心 |
| `vein run` / `vein pipe` | Error triage。有用但跟 lore capture 沒直接關係，稀釋產品定位 |
| `vein ask` | 功能幾乎跟 `vein recall` 重疊，造成混淆 |

**決定：**
- `vein walk`：保留功能（Rex 在用），但從 public docs / README 移出，標為 advanced/internal
- `vein run` / `vein pipe`：同上，保留但不主推
- `vein ask`：考慮 Phase 1 合併進 `vein recall`（`--natural-language` flag）
- **Core 7 commands（對外主推）：** init, log, recall, brief, debrief, mcp, hooks

**Why：**
「能做 13 件事的工具」vs「把一件事做到極致的工具」——後者更容易讓陌生人在 5 分鐘內上手，符合 D-008 public flip 條件三。

---

### D-030 — Recall 三重失效：CJK 斷詞、rowid-order 候選、embed model 漂移（2026-08-02）

**症狀（Rex 回報）：** 中文 recall 幾乎必定撈到 2026-06-02 23:41:30 那批 Lode 匯入的舊 entry，
之後兩個月寫的 900 多條像不存在。

**根因是三個獨立 bug 疊在一起，缺一都不會這麼慘：**

**1. FTS5 `unicode61` 沒有 CJK 斷詞**
unicode61 依 Unicode category 切 token，漢字是 `Lo`（letter），所以「一整段標點之間的中文」= 一個 token。
`就整個放棄索引` 是單一 token，查 `索引` 完全撈不到。實測本 repo corpus：單詞 CJK recall 0–54%，
`為什麼用 sqlite` 這種多詞查詢回 **0 筆**。

**2. `vector_search` 的候選集是 rowid order 的前 100 筆**
```python
candidate_ids = self.fts_search(query, k=100)
if not candidate_ids:                      # ← 中文查詢幾乎必定走這裡
    rows = conn.execute(
        "SELECT entry_id FROM embeddings WHERE vector IS NOT NULL LIMIT 100")
```
沒有 `ORDER BY` = rowid order = **最早插入的 100 筆** = 06-02 那批匯入。
語意搜尋等於只在最舊的 100 筆裡挑答案，之後寫的永遠撈不到。這就是「凍結在 06-02」的真正機制。

**3. 捕獲路徑用 nomic，查詢路徑用 config 的模型**
`store.write_entry()` 的 default 寫死 `embed_model="nomic-embed-text"`，而
`vein log` / `vein debrief` / MCP `vein_log` 三條主要捕獲路徑**都沒傳這個參數**。
`recall` 卻是從 `config.yaml` 讀 `qwen3-embedding:4b`。
結果：886 筆有 vector 的 entry 裡 **747 筆是 768 維**（nomic），查詢向量是 2560 維（qwen3）。
舊 code 的 `cosine_sim` 用 `zip`，長度不等會**靜默截斷**到 768 維算出一個看起來合理的分數——
不會報錯，只是答案是垃圾。而唯一維度正確的 139 筆，剛好就是 06-02 那批。
所以 Rex 說的「寫得進 storage 但不在語意索引裡」字面上完全正確。

**決定：**

| Bug | 解法 |
|-----|------|
| CJK 斷詞 | 新 `core/cjk.py`：index 時每個漢字獨立成 token（`segment`），query 時同樣切開再包成 FTS5 phrase（`build_match`）。`"索 引"` 要求 token 相鄰 = 精確 substring match，recall 100% 且不失精度 |
| 候選集 | `vector_search` 改**全 corpus 掃描**，不再用 FTS 當 gate。909 筆 × 2560 維 ≈ 200ms（numpy 有裝更快），到 ~50K 筆前都不需要 ANN |
| model 漂移 | `write_entry` 的 default 改成**讀專案 config**（`store.model_cfg()`），不是模組常數。維度不符的 vector 在 scan 時跳過並計數，`recall` 會提示，`vein reindex` 自動偵測並補嵌 |

**FTS 三層查詢（`fts_search`，命中就停）：**

| 層 | 查法 | 為什麼需要 |
|---|------|-----------|
| 1 | 每個 chunk 一個 phrase，AND | 最精確。`跨專案付費策略` 只回那一筆 |
| 2 | 同樣的 phrase，OR | 多詞查詢部分命中也要有結果 |
| 3 | CJK chunk 拆成**重疊 bigram**，OR | **中文本來就不打空格**。`索引效能` 當成單一 phrase 會要求這四個字連著出現 → 撈不到任何東西。拆成 `"索 引" OR "引 效" OR "效 能"` 才找得到分別講「索引」和「效能」的 entry |

第 3 層是最後手段，只在前兩層都空的時候才跑，所以不會稀釋精確查詢。
跨詞邊界的 bigram（`引效`）幾乎不會命中，等於免費。混排 chunk（`為什麼用sqlite`）也在這層拆開。

**Rejected：**
- **FTS5 `trigram` tokenizer**：查詢 < 3 字就失效，中文兩字詞（索引 / 快取 / 效能）是大宗，直接出局
- **CJK bigram 當索引格式**：index 大一倍。改成「index 存 unigram、查詢端第 3 層才組 bigram」——
  同樣的 recall，index 不變大，而且精確查詢仍走 phrase 不受影響
- **中文斷詞庫（jieba 等）**：多一個 runtime dep + 詞典，而且斷錯詞會**降低** recall。逐字 + phrase 沒有這個風險
- **保留 FTS pre-filter 只是加大 LIMIT**：治標。pre-filter 當 gate 的設計本身就錯——語意搜尋的價值正是找出關鍵字漏掉的東西
- **韓文一起切**：韓文本來就有空格分詞，切開反而破壞詞界，`cjk.py` 明確排除 Hangul

**順帶修掉的：**
- `recall` 改用 **RRF 融合** BM25 + cosine，不再是「有 vector 結果就不看 FTS」的 cascade——
  精確關鍵字命中曾被含糊的 embedding 蓋掉
- `store.read_entry(id)` 原本 O(n) 掃全部 entry 做 YAML parse（每個 hit 都掃一次），改成直接組路徑；
  且原本 `status_filter` 預設 `active`，**superseded entry 會 raise KeyError 被靜默吞掉**，
  跟 D-026「superseded 是降權不是隱藏」矛盾。改成 `status_filter=None`
- `vein reindex` 改成**預設增量**（只補沒有 / 沒 vector / 維度不符的）。原本每次都全部重嵌 910 筆要十幾分鐘，
  所以沒人跑，所以缺口一直在。`--all` / `--force` 保留全量
- `vein status` 加 index 健康度一行：`{embedded}/{total} embedded`，讓漂移不再隱形
- vector 儲存從 JSON text 改成 **L2-normalized float32 BLOB**（cosine = dot product）。
  22MB → 索引體積與 parse 成本都降一個量級，全 corpus 掃描才划算。schema v2，開檔時就地遷移，不需要 ollama

**雷區（給未來的自己）：**
- **`zip()` 算 cosine 是靜默錯誤**。長度不等不會噴錯，只會算出一個「看起來合理」的分數。
  任何比對兩個向量的地方都要先檢查維度
- **`LIMIT` 沒有 `ORDER BY` 就是 rowid order**，在 append-only 的表裡等於「最舊的 N 筆」。
  這是本次最惡毒的一環：它讓系統看起來有在運作，只是永遠回答錯的東西
- **參數 default 寫死模型名是漂移的溫床**。default 應該指向設定來源，不是某個具體值

**Revisit when：** corpus 破 50K → 換 sqlite-vec ANN，全 corpus 掃描會開始有感
