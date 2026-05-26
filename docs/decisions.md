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
- 啟動時間 ~200ms（Python interpreter），ctx ask 整體要 6-10s（ollama 占大頭），200ms 不痛
- 將來如果 ctx 變 daemon（v0.3 MCP server），Python 也夠（aiohttp / fastmcp）

**Revisit when:**
- ctx ask 變成熱路徑、單次跑 < 1s（不太可能）
- 要 single-binary distribution（用 PyInstaller 或 Rust 重寫 core）

---

### D-002 — vector store 用 sqlite-vec，不用 chromadb / faiss / qdrant

**Date:** 2026-05-26

**Choice:** `sqlite-vec`（asg017 那個 extension）。

**Why:**
- **單檔**：`.ctx/index/embeddings.db` 一個檔，跨機器 rsync 就好
- **無 daemon**：chromadb 要起 server、qdrant 要 docker，sqlite 零配置
- **熟悉**：Python `sqlite3` stdlib，sqlite-vec 是 extension
- **夠用**：v0.1 預期專案 ≤ 10K chunks，sqlite-vec 在這 scale 表現好（< 100ms query）

**Rejected:**
- `chromadb`：要 daemon、有 telemetry default、檔散
- `faiss`：學術出身、Python binding 笨重、index 不易 inspect
- `qdrant`：太重、要 docker
- pure-numpy in-memory：每次 ctx ask 都 load 全部 vector，慢

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

### D-008 — Visibility: private 現在，v0.3 flip public（2026-05-26）

**Date:** 2026-05-26 (Session 0.11)

**Choice:** `rex4ssd/vein` 建為 **private repo**，達到以下三個條件後 flip 成 public：

1. **三個核心命令真的能跑：** `vein init` + `vein log` + `vein recall`
2. **Dogfood on Lode 至少 2 週：** 真實寫過 ≥ 10 條 decision/lore，retrieval 品質確認
3. **README / docs_cloudflare 完整：** 陌生人 30 秒能看懂、5 分鐘能上手

預期觸發時程：Phase 0 完成後、Phase 0.3（MCP server）之前。

**Why（為什麼選 B 不選 A/C）：**

| 路徑 | 採 / 拒 | 理由 |
|---|---|---|
| **A. Public from day 1** | ❌ 拒 | Spec 還在 churn（Path A/B/C/D、改名 3 次、thesis pivot 1 次）；public 看見 churn 觀感差；無 working product 給人試 |
| **B. Private now, v0.3 flip public** | ✅ 採 | 第一次接觸 Vein 的人看到 working product 而非流產 spec；spec breaking change 不受外部牽制；跟 Lode 私有 + public release 同 pattern |
| **C. Public + Alpha tag** | ❌ 拒 | 「Alpha」標籤對多數人沒擋；早期 issue noise 大於收穫 |

**參照 pattern：** Lode 自己也是 `rex4ssd/lode` private dev + `rex4ssd/lode-releases` public binaries 雙 repo。Vein 第一階段不需 release repo，直接 private → 將來 flip public。

**Public 之前要做的事（pre-flip checklist）：**

- [ ] `vein init` 能跑
- [ ] `vein log decision/lore "..."` 能存進 `.vein/decisions/` 或 `.vein/debug_lore/`
- [ ] `vein recall "<query>"` retrieval 跑得起來、品質可接受
- [ ] Dogfood on Lode ≥ 2 週、≥ 10 條真實 entries
- [ ] LICENSE 檔（MIT）
- [ ] `docs_cloudflare/index.md` polish 完整
- [ ] `docs_cloudflare/install.md` 真實可跑（不是 placeholder）
- [ ] README.md（從 `docs_cloudflare/index.md` 精簡版）
- [ ] CONTRIBUTING.md 雛形（先寫「目前 not accepting external contributions, 等 v0.3 後開放」）
- [ ] `.github/ISSUE_TEMPLATE/` 雛形

**Reserve `lodevein` GitHub org（順手做）：**

- Phase 0 checklist 加：**註冊 `lodevein` org**（5 分鐘的事，保 5 年）
- **不一定要用** — Lode 已經在 `rex4ssd/lode`（App Store / Direct Sale cert 簽這個），不要動
- 預留 namespace 給未來 family 擴張（如果真的有 Seam/Shaft）
- 預防別人註冊變蹭名

**Revisit when:**
- Lode 自己 dogfood Vein 一個月後，如果發現需要外部視角才能改進，可考慮提早 flip
- 若有人在 2026 下半年宣布類似 "decision lore" product 搶 first-mover 名分，可考慮提早 flip 搶 mindshare

---

### D-007 — 專案改名為 **vein**，採「Lode Vein」product family 命名（2026-05-26）

**Date:** 2026-05-26 (Session 0.8 拍板 vein，0.9 升級為 product family)

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

每個 product 都有**獨立 CLI 短名 + 獨立識別**，但 marketing 上強 family 包裝。`Word` 的 CLI 不是 `office-word`；`vein` 的 CLI 也不是 `lode-vein`。

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
- `ctx` 至少撞 3 個獨立 OSS 名字（context-hub / Vedantham / ActiveMemory）
- 從 20 個候選收斂到 Top 3：vein / crux / etch
- Rex 選 vein，理由：跟 Lode 同 brand family、未來可擴 Lode/Vein/Seam 系列、CLI 順
- vein 在 software namespace 不擁擠（mining 比喻少見）
- Session 0.9 Rex 提 `lode-ctx` 替代案，但會 undo Path D 跳脫 ctx 紅海的核心目的；改採「Lode Vein」product family 框架滿足「強 Lode 關聯」需求而不犧牲跳脫**

**Rejected：`lode-ctx` 為什麼不行（Session 0.9 review）：**
- 「ctx」是被 7+ 個競品擠爆的紅海 namespace，加 `lode-` 前綴不會改變 SEO / 用戶分類
- 用戶看到 `lode-ctx` 腦中分類「another ctx tool」→ 跟 context-hub 304⭐ 同框
- Path D thesis 整個失效（我們不是 code RAG broker）
- 連字號 CLI 命令痛（`lode-ctx log "..."` 每次手指要找橫線）
- 暗示 sub-product feel，OSS standalone 故事弱

**Rejected：`vein-ai` / `vein-cli`：**
- `-ai` 是 2024 era cliché，會老化
- `-cli` 暗示只有 CLI，將來加 MCP server 名字錯

**Availability check（2026-05-26）：**
- 🟢 npm `vein`：空
- 🟢 GitHub `rex4ssd/vein`：可建
- 🟡 PyPI `vein`：被 squat（Josh Breidinger 2025-06-26 上傳 placeholder package，內容只有 `vein.hello()` 1.6kB，無後續）
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

理由：split naming 是業界常態（`python-dotenv` 安裝後叫 `dotenv`、`httpx[cli]` 安裝後叫 `httpx`），用戶體驗不痛。PyPI squat 透過 PEP 541 claim 太慢，不值得為它換掉 brand fit 最強的名字。

**Architectural implications:**
- 所有檔名 / config key / env var 從 `CTX_*` / `ctx.*` 改成 `VEIN_*` / `vein.*`
- `.ctx/` folder convention 改 `.vein/`
- repo 目錄要不要 rename 從 `/Users/lion/Documents/ctx/` 到 `/Users/lion/Documents/vein/` 待 Rex 決定

**Future namespace 預留：**
- **Lode** — desktop GUI / file viewer / compare（已存在）
- **Vein** — decision lore archive CLI + MCP（本專案）
- **Seam** — 預留（mining: 礦層 / 縫；可能 future 整合層）
- **Shaft** — 預留（mining: 礦坑；可能 future 跨專案 / 跨機器 sync）

Phase 0 只做 Vein。Seam / Shaft 是 namespace 保留，沒實作計畫。

**Revisit when:**
- 確認 PyPI claim 有沒有機會（如果簡單就嘗試）
- 確認 `.dev` / `.app` domain 有沒有撞
- 出現另一個 mining-themed AI tool 強競品（不太可能）

---

### D-006 — 採 Open Core 商業模式（ctx OSS + Lode 付費 + 未來 Cloud 訂閱）

**Date:** 2026-05-26

**Choice:** ctx CLI 100% MIT 開源、Lode 維持付費 GUI、ctx Cloud (v1.x+) 訂閱。Solo 功能完全不鎖。

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
6. ctx CLI **絕對不能對 Lode 有 hard dependency**：OSS 用戶完全不需碰 Lode 也能跑全功能

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
D-006 寫的時候假設「沒人在做 ctx 這個 niche」。Session 0.6 web search 後發現至少 7 個直接競品在做 per-project AI context broker（見 [`competitive_landscape.md`](competitive_landscape.md)）。Open Core 模式本身仍然成立，但**「ctx 作為獨立 OSS adoption funnel」這個前提失效**。Path 選擇進 D-007（待決）。

---

### D-005 — `.ctx/cache/` 進 .gitignore，`.ctx/config.yaml` 進 git

**Date:** 2026-05-26

**Choice:** 預設 `.gitignore`：

```
.ctx/cache/
.ctx/index/embeddings.db
.ctx/memory/
```

進 git：

```
.ctx/config.yaml
.ctx/digests/
.ctx/.gitignore        ← 自己
```

**Why:**
- `config.yaml` 是 source of truth，要跟 code 一起 version
- `digests/` 是人寫 / 半自動產的高價值產出（週報、topic digest），值得 commit
- `cache/` / `embeddings.db` 是 derived view，重建成本可接受，不該膨脹 repo
- `memory/sessions.jsonl` 含個人 query history，可能含敏感 keyword，預設不 commit

---

## Pitfalls（雷區）

### P-001 — placeholder：第一個踩到的雷請寫這裡

ctx 還沒寫 code，雷區待累積。

預期會踩的：
- ollama timeout / connection refused 怎麼降級
- sqlite-vec 在 macOS 上 load extension 路徑問題
- pbcopy 在 SSH session 失效
- digest 結果含 markdown fenced code block 被剪貼簿吃掉換行

---

## Invariants（不可違反）

### I-001 — `.ctx/cache/` 永遠不可進 git

**Why:** cache 會變大（GB 級），含 query 結果可能有敏感 keyword。

**How to enforce:** `.ctx/.gitignore` 預設寫好；validator 加 check：`git check-ignore .ctx/cache/foo.json` 必須 exit 0。

---

### I-002 — ollama 失敗時必須明確報錯，不可 silent fallback

**Why:** 如果 ollama 跑不起來，靜默 fallback 到 grep 會讓 user 以為 ctx 在用 local AI（其實沒），digest 品質爛還不知道為什麼。

**How to enforce:** `OllamaError` raise to top；CLI 印明確「ollama 連不上 http://localhost:11434」+ 退出 code 2。

---

### I-003 — `ctx ask` 輸出永遠不超過 config.ask.digest_budget_tokens

**Why:** spec G1（context 省 60%）的核心。如果 brief 自己就 5K token，意義盡失。

**How to enforce:** digest 後 tiktoken count；超過直接 truncate + 警告。

---

### I-004 — config.yaml schema 必須 version 化

**Why:** 將來改 schema 不能讓舊 `.ctx/` 直接壞。

**How to enforce:** `config.yaml` 必有 `version:` 欄；ctx 讀取時 check `version` 並走對應 migrator。

---

### I-005 — ctx CLI 不可對 Lode（或任何商業產品）有 hard dependency

**Why:** Open Core 戰略（D-006）的信任基礎。OSS 用戶必須 100% 不需 Lode 也能跑全功能。

**How to enforce:**
- `pyproject.toml` 的 `dependencies` 不可出現 Lode-related package
- 任何「Lode 整合」功能必須走 well-defined data format（讀 `.ctx/` 即可），不可走 RPC 進 Lode binary
- validator 加 check：`ctx --help` 不可提到 Lode（避免「沒裝 Lode 看到推薦覺得被綁」）
- 唯一允許的：`ctx --version` 末尾可有一行 marketing footer，可被 `--quiet` 關閉

---

### I-006 — ctx 永遠不可預設 telemetry / phone-home

**Why:** D-006 brand promise。一旦預設打開過一次，社群信任就回不去（Sentry / GitLab 都吃過虧）。

**How to enforce:**
- 任何 outbound HTTP 必須明確 user action 觸發
- 不可有「匿名統計」「使用情況回報」「auto-update check」default-on
- 如果未來要加 opt-in telemetry，必須：
  1. CLI 明顯 prompt（不是 dialog 預設打勾）
  2. 開源 telemetry endpoint server 程式碼
  3. 文件清楚列出每個 event 內容

---

## 已知 Known Issues

(空 — 還沒寫 code，待累積)
