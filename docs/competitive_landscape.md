# Competitive Landscape — 2026-05-26 snapshot

> 對「為什麼還沒人做 ctx」這個問題的誠實調查。
> 結論：**已經被做走了**，至少 7 個 project，名字也被搶了。
> 但「殘存的差異化」還有 — 取決於我們怎麼定位。

---

## 1. 直接競品（per-project AI context broker）

GitHub stars 實測（2026-05-26）。一句話結論：**市場熱但極度分散**，最大的也只有 304 stars，多數 < 10 stars。

| 工具 | GitHub | ⭐ Stars | Forks | Tech | 重點功能 | 我們有牠沒有 |
|---|---|---:|---:|---|---|---|
| **CTX** (context-hub/generator) | [link](https://github.com/context-hub/generator) | **304** | 20 | PHP, 單檔 binary 20MB | MCP server + multi-project + custom tools 跑 commands + context.yaml + Claude Desktop 首推；自己網站 docs.ctxllm.com + Discord + Telegram | Lode 整合、decision lore 切法、繁中 |
| **ctx-sys** (david-franz) | [link](https://github.com/david-franz/ctx-sys) | **6** | 2 | TypeScript, npm | Hybrid RAG (vec+FTS+graph)、tree-sitter、Ollama local、**12 MCP tools 含 decision / reflection / memory / checkpoint**、自己有 whitepaper + 網站 ctx-sys.dev | Lode、實際 user 採用率（6 stars 不算驗證） |
| **ContextFS** | [link](https://github.com/contextfs/contextfs) | **3** | 0 | Python, PyPI | `contextfs memory save "..." --type decision` 已有 decision type、semantic search、cloud sync via contextfs.ai、Claude plugin | Lode、繁中、長期 maintainer 紀錄（3 stars 風險高） |
| 多個其他 ctx / context 衍生 | (前一輪列表) | 多數 < 5 | - | 各種 | (多數重複造輪子) | 多數沒有實際 adoption |
| **adr-tools** (npryce) — ADR 老前輩 | [link](https://github.com/npryce/adr-tools) | (數百) | - | Bash | 純 ADR 寫作 + numbering，**沒有 AI、沒有 RAG** | AI 輔助、digest、MCP |
| **adr.github.io** 標準努力 | adr.github.io | n/a | - | 規格 + 工具列表 | ADR 知識庫，多個語言的工具 fragmented | 整合工作流的工具 |

**關鍵發現（更新 2026-05-26）：**
- **「ctx」名字被至少 3 個獨立 project 用了**（Vedantham / context-hub / ActiveMemory）
- **`.ctx/` 資料夾 convention 已被推**
- **最熱的競品 context-hub/generator 也才 304 stars** — 市場驗證**還非常早期**
- 多數其他工具 < 10 stars = **大家都還在試水溫**
- **ContextFS（3⭐）和 ctx-sys（6⭐）的 spec 都已經有 "decision" type / decision MCP tool** — Gemini 提的「decision lore」niche **也已經被觸碰**（但都不是核心 positioning）
- adr-tools 老 ADR 生態存在十年但**沒有 AI 化** — 這是真實 gap

---

## 2. 鄰近競品（不同 shape 但解類似問題）

### 2.1 Chat app with local RAG

牠們是 chat UI，不是 broker，但搶用戶心智：

- **AnythingLLM** — 完整桌面 chat + RAG，OSS-ish (LGPL/SSPL)，MCP 支援 via Agent framework
- **LibreChat** — webapp，agents + MCP + persistent memory default
- **Open WebUI** — webapp，Ollama 整合，MCP via mcpo proxy
- **PrivateGPT** — RAG over local docs
- **GPT4All** — desktop chat
- **Khoj** — desktop search/chat (org-mode bias)
- **5ire** — cross-platform desktop AI assistant，MCP 整合

### 2.2 IDE-locked context

- **Cursor `.cursor/rules`** — IDE-locked
- **Continue `.continue/`** — IDE-locked
- **Cody (Sourcegraph)** — enterprise, server-required

### 2.3 Convention-only（非工具）

- **`CLAUDE.md`** — 純 markdown 慣例
- **`AGENTS.md`** — 同上，跨 vendor 標準努力
- **`SKILL.md`** — Anthropic Skills format

---

## 3. 為什麼「沒被做」是錯的判斷

我（Claude）在 Session 0 寫 spec 時假設「OSS 缺口很明確」。**這個假設錯了。** 實際上：

| 我以為的 | 真實狀況 |
|---|---|
| 「沒人做 per-project AI context CLI」 | 至少 4 個在做 |
| 「`.ctx/` 是 fresh idea」 | 已被使用 |
| 「local-first + Ollama + MCP 組合是 fresh」 | ctx-sys 已經做 |
| 「LangChain/LlamaIndex crowded the space, no one else builds」 | 過去 6 個月有 OSS 直接 fill 這個 niche |
| 「ctx 名字沒衝突」 | 至少 2 個直接撞名 |

**為什麼我會錯？**
- 我（前一個 session 的 Claude）training cutoff 是 2025-05；landscape 從 2025 Q4 → 2026 Q2 變化非常快
- Anthropic MCP 標準化、Claude Code 普及、Cursor 競爭白熱化 → 「per-project context」變成熱門 niche
- "ctx" 這 3 個字母太通用，名稱碰撞高機率

**lesson：** 任何「市場 thesis」必須 web search 驗證，不能靠 LLM 腦補 landscape。

---

## 4. 殘存的差異化（嚴格 audit）

把我們 spec 寫的 features 對照競品看，**真正 unique 的只剩這些**：

| Feature | 我們 | ctx-Vedantham | ContextFS | ctx-sys | context-rag |
|---|---|---|---|---|---|
| Per-project `.ctx/` folder | ✓ | ✓ | ✓ | ✓ | ✓ |
| Local-first | ✓ | ✓ | ? | ✓ | ? |
| Ollama 整合 | ✓ | ? | ? | ✓ | ? |
| MCP server | 🟡 v0.3 | ? | ✓ | ✓ | ? |
| Hybrid retrieval (vector+keyword) | ✓ | ? | ✓ | ✓ | ✓ |
| Time-travel / session memory | ✓ spec'd | ✗ | ✗ | ✗ | ✗ |
| **GUI for context debugging** | ✓ (via Lode) | ✗ | ✗ | ✗ | ✗ |
| **桌面 app 整合（Tauri）** | ✓ Lode | ✗ | ✗ | ✗ | ✗ |
| **Open Core (Lode 付費 GUI)** | ✓ planned | ✗ | ✗ | ✗ | ✗ |
| Per-chunk encryption (cloud sync 預留) | ✓ planned | ✗ | ✗ | ✗ | ✗ |

**結論：技術層面我們已經沒有差異化。**

**唯一明確 unique 的：**
1. **Lode 整合** — Context Time Travel + Diff UI（這是我們完全控制的東西）
2. **Open Core 商業模式 with Lode** — 不是產品差異，是商業模式
3. （soft）真實 no-telemetry / 嚴格 local-first 紀律
4. （soft）Rex 個人 brand + dogfood 深度

**更新 2026-05-26（看完 stars 之後）：**

**「做得好」的標準 — 競品評估：**
- **context-hub/generator（304⭐, 685 commits, 57 releases）** = **「做得好但定位不同」**。它做的是 multi-project MCP context generator + 跑 commands 給 AI，不做 decision lore 或 visualization。可以**借鑑**它的 multi-project config 和 release pipeline；不直接威脅 Lode 整合的價值
- **ctx-sys（6⭐, 234 commits）** = **「概念對但太早期」**。它把 hybrid RAG / decision / reflection / checkpoint 包成 12 個 MCP tool，technically 完整，但 6 stars = 沒人在用。我們可以**借鑑它的 MCP tool 分類**（特別是 decision / reflection / memory 三組 tool 命名）
- **ContextFS（3⭐）** = **「Memory + cloud 切法但沒人用」**。它已經有 `--type decision` 的 memory tag，但 3 stars + 0 forks = 跟我們一樣都還沒被驗證

Rex 的「做得好就拿來用，做不好就拿來改」原則具體執行：
- **不抄 context-hub** — PHP stack、跟 Lode 整合不順
- **可以借鑑 ctx-sys 的 MCP tool 分類** — 它的 `decision` / `reflection` / `memory` 三組 tool 切得很合理
- **不依賴 ContextFS** — 太早期，賭風險高

---

## 5. 重新評估「護城河」

Rex 的直覺：「user 多 = 護城河高」。

**在 crowded 市場，這句話需要修正。**

User 數**本身**不是 moat — 它是某些 moat 的 leading indicator：

| Moat 類型 | 來源 | 我們在 crowded 市場能取得？ |
|---|---|---|
| **Network effect** | 用戶互相提升價值 | ❌ ctx 主要 single-user，弱 |
| **Switching cost** | 累積資料離不開 | 🟡 `.ctx/` 格式競品也讀得到，弱 |
| **Data moat** | 獨家資料 | ❌ local-first，故意沒這個 |
| **Standard moat** | 格式被廣泛採用 | ❌ 至少 4 個競品在競爭「`.ctx/` standard」 |
| **Brand/Trust** | 信任積累 | 🟡 慢、需時間，所有人都能爭 |
| **Lode integration** | 我們唯一控制的東西 | ✅ **強** — 競品 fork ctx engine 也做不出 Lode |
| **Maintainer presence** | Rex 個人投入深度 | 🟡 需要 Rex 願意當公開 maintainer |

**Rex 的「user 多」直覺哪裡對：** user 數差距會放大 brand / standard / network effect — 在白紙市場成立。

**在現在的 crowded 市場：** user 數差距我們**從第一天就落後**（競品已經有 stars / users）。**追 user 數不可能贏。**

**所以真實的護城河只剩兩條：**
1. **Lode + ctx 整合的 visualization 體驗** — 技術上競品可以仿，但需要他們自己做 Tauri app（高成本，且偏離他們的核心）
2. **Rex 自己的執行品質 + dogfood 深度** — 競品 maintainer 不會比 Rex 更懂 Rex 的工作流

第 2 點翻譯成可執行：**ctx 要存活，不是因為「user 多」，是因為「對 Rex 自己無可取代」**。如果 Rex 自己每天用，那 ctx 對 Rex 至少永遠值得做。其他人用不用都是 bonus。

---

## 6. 三條 Path（Rex 要選的決定）

### Path A — Pivot 名字 + 重新 niche

**做什麼：**
- 改名（ctx 已被多人用）
- 找一個還沒被搶的 niche：例如「Tauri 專案專用」「投資 / 量化專案」「solo founder 多專案 context broker」
- 保持 OSS + MIT + 本機 + MCP

**Pros：** 維持原始 vision、有獨立 brand
**Cons：** 名字難挑、niche 太小可能 sustain 不下去、跟 5 個競品中至少 1-2 個仍會撞

### Path B — Pivot 定位：lead with Lode + Context Time Travel

**做什麼：**
- ctx 本身**不**作為獨立 promote 的產品
- 主打 **Lode**（已存在、已付費、已上架）+ Lode 內建的 Context Visualization mode
- ctx-the-engine 仍開源 + MIT，但定位成「Lode 的開源 backend」，類似 `git` + GitHub Desktop 的關係
- README / 行銷不打「per-project AI context broker」（紅海），打「Visual AI context debugging in your file viewer」（藍海）

**Pros：**
- 用 Rex 唯一不可取代的 asset（Lode）當主角
- 避開 OSS 紅海，進入「桌面 GUI for context」這個目前沒人做的 niche
- Lode 本身有付費基礎，不靠 ctx 賺錢
- ctx engine 還是 OSS，credibility 不掉

**Cons：**
- 「ctx is OSS standard」這個願景退場
- 進不了「.git 級」moat 的可能性（其實本來就低）

### Path C — Abort + 整合既有 OSS

**做什麼：**
- 不寫 ctx engine。改用 **ctx-sys** 或 **ContextFS** 當 backend
- Lode 直接整合那一個的 MCP server / API
- 我們只專注做 visualization layer

**Pros：**
- 完全不做白工
- 借力既有社群 momentum
- 工程量降到只剩 Lode 內的 UI 整合

**Cons：**
- 受制於別人的 roadmap / breaking change
- 那個 OSS 死掉我們陪葬
- 沒有自己的 protocol control

---

## 7. 我推薦 Path B

理由：

1. **Rex 真正不可取代的 asset 是 Lode**，不是「再做一個 OSS CLI」
2. Path A 風險高（再 niche 也容易撞），Path B 用 Rex 已有 brand
3. Path C 太被動，且 ctx-sys / ContextFS quality 還沒驗證
4. Path B 把工程力量集中在「沒人做的東西」（context visualization），而不是「7 個人在做的東西」（CLI broker）
5. ctx engine 仍 OSS 但「subordinate to Lode」，credibility + 控制權兼得

**Path B 下，ctx 開發要怎麼調整：**

| 項目 | 原計畫 | Path B 調整 |
|---|---|---|
| ctx 名字 | 保留 | **改名**（撞名 → 信任問題） |
| OSS marketing 強度 | 中高 | 低 — 不主打 |
| 主要 user-facing 產品 | ctx CLI | Lode（含 ctx engine） |
| Phase 0 工程焦點 | CLI + spec 完整 | engine 必要功能 + Lode 整合早做 |
| Spec 公開時程 | OSS release | 內部用，Lode 整合穩了再公開 |
| Lode + ctx 命名 | 兩個 brand | 一個 brand（Lode），ctx 是 Lode 內部組件 |

---

## 8. 不論選哪條，立即要做的事

1. **驗證 ctx-Vedantham / ContextFS / ctx-sys 實際使用體驗** — 跑跑看，確認牠們的 quality（可能比想像差，也可能很好）
2. **驗證我們的「Context Time Travel」想法在競品中真的沒有** — 再 deep search 一次
3. **如果 Path B：** 把 strategy.md §1.4 Lode integration 升級為 §1 main thesis，重寫 TL;DR
4. **如果 Path A：** 開始 brainstorm 新名字（短、未撞、好記、可註冊）
5. **如果 Path C：** Rex 親自跑 ctx-sys / ContextFS，評估 fit
