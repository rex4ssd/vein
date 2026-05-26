# Changelog — ctx

> Session-by-session 開發日誌。每個 session 結束寫一條。
> 格式：`## Session N — YYYY-MM-DD — short title`

---

## Session 0 — 2026-05-26 — 專案啟動 + docs scaffold

**What:**
- 在 `/Users/lion/Documents/ctx/` 建立專案骨架
- 寫完 5 份 docs：`CLAUDE.md` / `docs/spec/v0.1.md` / `docs/working_style.md` / `docs/decisions.md` / `docs/changelog.md`
- 尚未寫任何 code（Python package、CLI、test 都待 Session 1 才開始）

**Why:**
- 兩個 session 之前 Rex 連續吃 autocompact thrashing（context 3 turn 內被塞滿 3 次）
- 早上花時間整理 Lode CLAUDE.md，意識到需要 systemic solution
- 對話討論完，決定 ctx 不是 Lode 的延伸而是獨立工具
- Rex 要求「要做就做最好的，no game」，所以從 spec + working style 開始而不是隨便寫 code

**Files created:**
- `CLAUDE.md` — 專案 brief（仿 Lode 結構），給未來 Claude session 看
- `docs/spec/v0.1.md` — Phase 0 完整 technical RFC，含 problem statement、goals/non-goals、.ctx/ schema、CLI commands、model routing、dogfood plan、open questions
- `docs/working_style.md` — Rex 個人偏好 + Lode 一年合作萃取出的 anti-pattern 清單，給未來 Claude 看
- `docs/decisions.md` — 已記 D-001~D-005（語言、vector store、chunking、embedding、gitignore 策略）+ 4 條 invariant（I-001~I-004）
- `docs/changelog.md` — 本檔

**Key decisions made (see decisions.md for full reasoning):**
- D-001: Python 3.11+，非 Rust
- D-002: sqlite-vec，非 chromadb / faiss
- D-003: fixed-token chunking（400/50），semantic split 之後再說
- D-004: nomic-embed-text local embedding，非雲端
- D-005: `.ctx/cache/` 不進 git、`config.yaml` + `digests/` 進 git

**Open questions still pending:**
- Q4: per-file digest vs per-topic digest 哪個是 primary（dogfood 第二週決）
- Q6: ollama 失敗的 fallback 機制（v0.1 ship 前決）
- Q7: 是否支援 lm-studio / mlx 後端（v0.2）

**Lessons / Pitfalls:**
- 還沒寫 code，沒踩雷
- 預期：Session 1 開工會先在 `src/ctx/` 建 package skeleton + 一個 `ctx init` 能跑

**Next session entry point:**
1. 確認 spec v0.1 是否要動（Rex 可能在 dogfood 開始前再 review 一輪）
2. 建 Python package：`src/ctx/__init__.py` / `src/ctx/cli.py` / `pyproject.toml`
3. 寫第一個指令：`ctx init`（建 `.ctx/` + 預設 `config.yaml`）
4. 寫 `tests/test_init.py`
5. 設 ruff + mypy + pytest CI baseline

**Time spent:** 1 session（純 docs，無 code）

---

## Session 0.5 — 2026-05-26 — Gemini 戰略 review + strategy.md 誕生

**What:**
- Rex 帶來 Gemini 給的戰略建議（護城河、Lode 帶動銷量、ctx Cloud 訂閱模式）
- Claude 對 9 條建議做 critical review，逐條 buy / push-back
- 新增 [`docs/strategy.md`](strategy.md)：完整商業 / 戰略 / 競爭定位文件
- 新增 D-006（Open Core 模式）+ I-005（不可依賴 Lode）+ I-006（無 telemetry）
- spec/v0.1.md 加 Q8（license）+ Q9（cloud sync 加密粒度）
- CLAUDE.md 加 strategy.md link

**Why:**
- Rex 主動問「怎麼做到單人免費、企業收費的高品質」——這是戰略問題，比技術 spec 更上游
- 早期把商業模型、Open Core constraints、Lode 整合定位寫清楚，才不會 v0.1 寫到一半發現 architectural decision 卡死未來
- Gemini 的建議方向正確但細節有翻車風險（特別是 cloud sync 跟 local-first 的張力），需要 push back 並補正解

**Files changed:**
- `docs/strategy.md`（新檔，~440 行）— 10 個 section：TL;DR / Gemini review / 護城河 / 雙軌 / Monetization matrix / local-first × cloud / Lode 殺手 feature / reality check / Phase 0 commitments / 未決議
- `docs/decisions.md` 加 D-006 + I-005 + I-006
- `docs/spec/v0.1.md` 加 Q8 + Q9 + cross-ref 到 strategy.md
- `CLAUDE.md` 加 strategy.md 引用

**Key strategic commitments:**
- Open Core: ctx OSS (MIT) + Lode 付費 + 未來 ctx Cloud（v1.x+）
- 個人功能 100% 不鎖
- Local-first 是 brand promise；cloud sync 是 opt-in、e2e encrypted
- Lode 殺手 feature 推薦：Context Time Travel + Diff（reuse Lode 既有 compare UI）
- Phase 0 不寫 cloud / billing / RBAC 任何一行 code

**Lessons / Pitfalls:**
- 戰略文件跟技術文件分開檔。混在一起會讓技術 spec 變成 pitch deck
- Gemini 給「資深工程師 .ctx 自動同步給菜鳥」這建議 naive 實作會違反 local-first（明文上雲、server 倒了就死）。正解是 e2e encrypted relay。早抓到這條
- 「.ctx 變 standard」這話千萬不能在 README 寫——LangChain 早期的錯。要被採用出來、不是宣告出來

**Next session entry point（不變，沿用 Session 0）：**
1. 確認 spec + strategy 是否要動
2. 建 Python package：`src/ctx/` + `pyproject.toml`
3. 寫 `ctx init`
4. 設 ruff + mypy + pytest baseline

**Time spent:** 0.5 session（純 docs + 戰略思考，無 code）

---

## Session 0.6 — 2026-05-26 — Competitive landscape reality check

**What:**
- Rex 問「為什麼還沒人做 ctx，或是已經被做走了」
- Claude 跑 3 次 web search，找到**至少 7 個直接競品**在做 per-project AI context broker
- 名字「ctx」**已被至少 2 個獨立 OSS 用**：Lakshmi Sravya Vedantham 的 Python CLI + ActiveMemory 的 single-binary
- `.ctx/` 資料夾 convention 已被多個 project 推
- 新增 [`docs/competitive_landscape.md`](competitive_landscape.md)（~260 行）：競品清單 + 殘存差異化 audit + 三條 path 推薦
- spec/v0.1.md 加 Q10（rename）/ Q11（standalone vs Lode-led）/ Q12（kill criteria）
- decisions.md D-006 加 caveat：原始 OSS adoption funnel 前提失效

**Why:**
- Rex 問了正確的 skeptical question — 在投入工程之前必須驗證 market thesis
- Session 0 寫 strategy.md 時 Claude 假設「OSS 缺口很明確」，這個假設**錯了**
- 早知道好，比寫完 800 行 code 才發現好

**Critical findings:**
- **直接競品 7+ 個**：ctx (Vedantham)、ContextFS、ctx-sys、context-rag、ContextVault、context (neuledge)、ctx (ActiveMemory)、rag-cli
- 多數都已支援 Ollama + MCP + Claude Code / Cursor
- 「local-first per-project AI context」這個 niche **已是紅海**
- 我們殘存的真實 unique 只有 2 條：**Lode 整合 (Context Time Travel UI)** + **Open Core 商業模式**
- Rex「user 多 = 護城河高」直覺在白紙市場成立，**在 crowded 市場 user 數差距我們從第 1 天就落後 → 不可能用 user 數贏**

**Three paths surfaced（待 Rex 決定）：**
- **Path A**：改名 + 重 niche，維持 standalone OSS（風險中等）
- **Path B**：定位轉成 Lode 的開源 backend，主打 Lode + Context Time Travel（推薦）
- **Path C**：abort，改用 ctx-sys / ContextFS 當 backend，只做 Lode visualization 層

**Claude 推薦 Path B**，理由：
1. Rex 唯一不可取代 asset 是 Lode
2. 避開 7 競品紅海，進「context visualization GUI」藍海
3. Lode 已有付費基礎，不靠 ctx 賺錢
4. ctx engine 仍 OSS、credibility 不掉，但「subordinate to Lode」工程量集中

**Lessons / Pitfalls:**
- **市場 thesis 必須 web search 驗證**，不能靠 LLM 腦補 landscape（特別是 LLM training cutoff 5+ 個月前的）
- AI 生態變化太快（MCP 標準化 + Claude Code 普及 + Cursor 競爭 → "per-project context" 從藍海變紅海只花 6 個月）
- **未來任何戰略 doc 開頭必須先 web search competitive landscape**

**Next session entry point（已改）：**
1. **Rex 拍板選 Path A / B / C**
2. 若 Path B：strategy.md 大改寫（§1 升級為 main thesis、TL;DR 重寫）
3. 若 Path A：brainstorm 新名字
4. 若 Path C：Rex 親自跑 ctx-sys / ContextFS 評估

**還未做的事：**
- sustainability.md（維護紀律）—— 等 path 決了再寫，內容依 path 而異
- strategy.md 大改寫 —— 等 Rex 拍 path

**Time spent:** 0.6 session（web research + competitive landscape doc + spec/decisions update，無 code）

---

## Session 0.7 — 2026-05-26 — GitHub stars 實測 + Gemini "decision lore" pivot

**What:**
- Rex 問「公開作品下載次數高嗎」+ 給規則「做得好就用，做不好就拿來改」
- 跑 WebFetch 抓 3 個競品的真實 GitHub stars：
  - **context-hub/generator: 304⭐, 20 forks, 685 commits, 57 releases** — 唯一接近「做得好」的
  - **ctx-sys: 6⭐, 2 forks, 234 commits** — spec 漂亮但無 adoption
  - **ContextFS: 3⭐, 0 forks** — 早期 + cloud 取向
- Rex 同 turn 帶來 Gemini 新 pivot：「程式碼 vs 決策歷史」切法 + Auto-bootstrap + Context-As-Code + Lode "Send to ctx" + 觸發機制問題
- 更新 [`competitive_landscape.md`](competitive_landscape.md)：加實測 stars + 修正「殘存差異化」+ 加 Rex 規則的具體執行
- strategy.md 加 [`§11`](strategy.md#11-alternative-thesis-decision--debug-lore-archive)：「Decision Lore Archive」alternative thesis 完整 review + Path D + 觸發機制三層設計

**Why:**
- Rex 規則需要實測數據才能套用（哪個算「做得好」）
- Gemini 的「程式碼 vs 決策歷史」切法是這幾輪討論中**最尖銳的差異化**，值得認真評估
- 既然要紙上談兵，把每個 thesis 寫完整再決，比動 code 划算

**Key findings:**
- 市場**熱但極度分散** — 最大競品 304⭐，多數 < 10⭐，「做得好」的閾值很低
- 「做得好」唯一接近的 context-hub 是 PHP / MCP context generator + multi-project，**不打 decision lore**
- ctx-sys 跟 ContextFS 都已有 `decision` 概念但都不是核心 positioning，仍有空間
- adr-tools 老 ADR 生態存在十年但**完全沒 AI 化** — 真正的 gap

**Gemini pivot critical review:**
- 核心 insight「程式碼 vs 決策歷史」**買單** — 真實差異化、避開紅海
- Auto-bootstrap from git log **半買** — 想法對但需要 draft → 人 review，不能直接入 archive
- Context-As-Code via git **完全買** — 規避 cloud sync 跟 local-first 的張力
- 黃金 schema `decisions/` + `debug_lore/` **大致買** — 比原 spec embeddings.db 簡單很多
- 觸發機制 auto-on-commit vs Lode button：**兩個都不對**，正解是 `ctx log` CLI 主、Lode button 次、commit tag fallback

**New Path D added:**
- Decision Lore niche，取代或補強 Path B
- ctx engine 變成 ADR + 踩坑筆記 + AI 輔助 capture + RAG retrieval
- Lode 整合：「Send to ctx」+「決策時間軸」+ diff 旁 surface 相關 lore
- 仍需改名（但 angle 更明確，namespace 候選 lore / adrly / debugbook 等）
- Phase 0 spec 改動：核心動詞 `ctx log` / `ctx recall` / `ctx review`、archive scale 小、ollama 用量降

**Updated recommendation (Path 排序):**
1. **Path D** — Decision Lore（Path B 升級版，positioning 最清晰）⭐
2. Path B — Lode-led + Time Travel
3. Path C — abort & 整合既有
4. Path A — standalone OSS 改名

**Lessons / Pitfalls:**
- 任何「市場機會」判斷必須真實去抓 GitHub stars，文字描述會誤導（context-hub 304⭐ vs ctx-sys 6⭐ 是 50x 差距，文章上看起來差不多）
- 「決策歷史」這個切法 LLM 真的猜不到，這是 Gemini 的真實洞察
- 觸發機制設計要尊重「explicit semantic action」原則：noise 越少越好，user 主動才寫

**Next session entry point（更新）：**
1. Rex 拍板 **Path A / B / C / D**（D 是新選項）
2. 若 Path D：spec/v0.1.md 大改寫（核心動詞、schema、Lode 整合時程）
3. 不論哪 path：改名 brainstorm（ctx 已撞名 + adoption 風險）
4. 仍未做：sustainability.md（維護紀律）

**Time spent:** 0.7 session（3 個 GitHub fetch + landscape 更新 + strategy §11 加 + 觸發機制設計，無 code）

---

## Session 0.8 — 2026-05-26 — 改名 brainstorm + 拍板 vein

**What:**
- 寫 [`docs/naming.md`](naming.md)：20 個候選、5 分類、Top 5 排名（vein / crux / etch / mnemo / debrief）
- Rex 拍板 **vein** — Lode 同 brand family、mining 意象（"Lode finds the code. Vein remembers the why."）
- Availability check：
  - 🟢 npm `vein`：空
  - 🟢 GitHub `rex4ssd/vein`：可建
  - 🔴 **PyPI `vein` 被 squat**（Josh Breidinger 2025-06 placeholder package，1.6 kB，無後續）
- 採 **split naming 策略**避開 PyPI squat：brand = vein、CLI = `vein`、PyPI = `lode-vein`、repo = `rex4ssd/vein`
- 新增 D-007（vein 命名 decision + architectural implications）
- CLAUDE.md 改名 + 加 Path D 形態的 Phase 0 scope + 更新檔案結構 + 更新 SOP

**Why:**
- ctx 撞 3 個 OSS 名字、不能繼續用
- Rex 規則「做就做最好的」→ 一輪定案不留尾巴
- split naming 是業界常態（`python-dotenv` / `httpx[cli]` 都這樣），CLI 名仍是 `vein` 用戶無感

**Files changed:**
- `docs/naming.md`（新檔，含 20 候選 + availability check + 最終決定）
- `docs/decisions.md` 加 D-007
- `CLAUDE.md` 改名 ctx → vein、結構說明、SOP 順序

**Brand narrative locked:**
> Lode finds the code. Vein remembers the why.
> Lode 找到檔。Vein 記住決定。
> 未來可擴：Lode / Vein / Seam / Shaft 整套 mining product family。

**Lessons / Pitfalls:**
- PyPI 名字檢查必須在腦補品牌之前做 — 但這次也學到「PyPI squat 不擋 brand 選用」，split naming 是 escape hatch
- 4 字母真實英文字在 PyPI 幾乎都會被 squat（甚至連 `vein` 這種非主流字也被佔），預期未來任何短名都要走 split naming
- 改名雖然必要但需要時間滲透：所有 docs 不會一次改完，後續每 session 看到 ctx 順手改 vein

**未做 / 待後續 session：**
- `docs/spec/v0.1.md` 仍是 Path A/B 形態（核心動詞 `ctx ask` / `ctx index`），**待改寫為 Path D**（`vein log` / `vein recall` / `vein review`）— 是 Session 1 的事
- 資料夾 `/Users/lion/Documents/ctx/` 是否 rename 為 `/Users/lion/Documents/vein/` 待 Rex 決
- `.dev` / `.app` domain 待測
- `sustainability.md` 維護紀律未寫
- 仍未開始寫任何 code

**Next session entry point（Session 1）：**
1. 改寫 `docs/spec/v0.1.md` 為 Path D 形態（核心動詞 vein log / recall / review、archive schema、Lode v0.2 整合時程）
2. 資料夾 rename 決定
3. 寫 Python package skeleton：`src/vein/__init__.py` + `pyproject.toml`（PyPI name `lode-vein`）
4. 寫第一個指令：`vein init`（建 `.vein/` + 預設 config）
5. dogfood：在 `/Users/lion/Documents/lode/` 跑 `vein init` + 手動寫第一條 decision

**Time spent:** 0.8 session（naming brainstorm + 3 availability checks + 4 個檔的 lock-in 更新，無 code）

---

## 📊 Session 0.x 累計總結（2026-05-26 一天）

8 個 sub-session 做完的事：

| Session | 核心產出 |
|---|---|
| 0 | docs scaffold 5 份（CLAUDE.md / spec/v0.1.md / working_style / decisions / changelog） |
| 0.5 | Gemini 戰略 review + strategy.md 誕生 |
| 0.6 | 競品 landscape reality check：發現 7+ 競品已存在 |
| 0.7 | GitHub stars 實測 + Gemini decision lore pivot + Path D 提出 |
| 0.8 | 改名 brainstorm + 拍板 vein + split naming |

**累計：**
- 8 份 docs，**~2300+ 行**
- 7 個 decisions (D-001~D-007) + 6 個 invariants (I-001~I-006)
- 12 個 open questions (Q1~Q12) + 多個 path candidates
- 改名 1 次：ctx → vein
- 策略 pivot 1 次：code RAG broker → decision lore archive
- **Code：0 行**（按 plan，這是「做就做最好的」紙上談兵階段）

**整體判斷：** 在沒寫一行 code 的情況下，把 product positioning / 商業模式 / 競品 / 命名 / 護城河 / 觸發機制 全跑過一輪。下一輪可以動 code。

---

## Session 0.9 — 2026-05-26 — 「Lode Vein」product family 包裝確認

**What:**
- Rex 提替代案 `lode-ctx` / `lode-vein` / `vein-ai` / `vein-cli` 重新評估
- Claude push back `lode-ctx` — 會 undo Path D 跳脫 ctx 紅海的核心目的
- 拍板採 **「Lode Vein」product family** 包裝（Microsoft Office pattern）：
  - 對話 / blog / homepage 講 **「Lode Vein」**
  - CLI 仍是 `vein`（4 字、無連字號）
  - PyPI 仍是 `lode-vein`
  - 滿足「強 Lode 關聯」訴求 + 不犧牲 Path D 跳脫
- 升級 D-007：加 product family 區塊 + marketing 講法分通路矩陣 + 拒絕替代案的理由 + namespace 預留（Seam / Shaft）
- 更新 CLAUDE.md 開頭：標示 Lode Vein product family 身分 + family marketing 名 + tagline
- 更新 naming.md §7：Microsoft Office pattern 對照 + marketing 講法分通路

**Why:**
- 「lode-ctx 不錯」這個直覺對的部分是「強 Lode 關聯」，錯的部分是把 ctx 塞回紅海 namespace
- 正解：marketing 包裝強 family、CLI 保持 distinctive — 不是 either/or
- Microsoft Office 為什麼這樣命名：family 包裝賣品牌、product 短名給用戶日常使用，不衝突

**Marketing 模板鎖定：**
- Blog 標題：「Lode Vein — Decision & debug lore for AI-assisted dev」
- Homepage hero：「Lode Vein: the missing decision history for your AI」
- Vein README 第一行：「Vein (part of the Lode Vein suite) — local-first decision lore archive」
- 對話：「我做了 Lode Vein，Lode 找到檔，Vein 記住為什麼」

**Lessons / Pitfalls:**
- 命名 trade-off 不一定要 sacrifice 一邊：family marketing + product 短名是常見的解 (MS Office / Apple Pro Apps / Adobe Creative Cloud)
- Rex 直覺反覆來回是 signal — 但 signal 通常指向「我想要 X 屬性」而非「我想要這個具體名字」。我們的工作是找出能滿足 X 屬性的更好設計
- 連字號 CLI 命令真的會被討厭 — `lode-ctx log` 每次手指要找橫線
- 「ctx」這詞已經被 7+ 競品消費過，不可能再用任何形式 reuse

**Files changed:**
- `decisions.md` D-007 加 ~50 行 family 區塊 + marketing 講法矩陣 + rejected alternatives
- `CLAUDE.md` 標題加 Vein、開頭加 family 身分、§1 加 family marketing 名
- `naming.md` §7 改寫為 Lode Vein family + Office pattern；§9 加 rejected alternatives

**Next session entry point（不變）：**
1. 改寫 `docs/spec/v0.1.md` 為 Path D 形態（核心動詞 vein log / recall / review、schema、Lode v0.2 整合時程）
2. 資料夾 rename 決定（`/Users/lion/Documents/ctx/` → `/Users/lion/Documents/vein/`）
3. dogfood 先行 (option C)：在 `/Users/lion/Documents/lode/` 手動建 `.vein/decisions/` 寫 3-5 個真實決策驗證 schema
4. Python package skeleton + `vein init`

**Time spent:** 0.1 session（review + 升級 family 包裝 + 4 個檔 lock-in，無 code）

---

## Session 0.10 — 2026-05-26 — 資料夾 rename + 公開網站 scaffold

**What:**
- **資料夾 rename 完成**：`/Users/lion/Documents/ctx/` → `/Users/lion/Documents/vein/`（Rex 執行）
- Rex 新增 `docs_cloudflare/` 資料夾規格給 Claude 一拼 track
- Scaffold 6 個公開網站 markdown 檔（英文為主，準備之後 deploy 到 rexcode.app/vein）：
  - `_README.md` — 內部說明（不 publish），雙 track docs 分工
  - `index.md` — homepage，含 hero + tagline + problem + quick example + Lode Vein family
  - `about.md` — What is Vein / 設計原則 / suite 介紹
  - `why.md` — placeholder + 兩種知識的 thesis + vs 競品表 + 適不適合使用
  - `features.md` — placeholder + CLI / MCP / Lode 整合 / storage / what Vein doesn't do
  - `install.md` — placeholder + 預定 install 流程（`pip install lode-vein` + Ollama + MCP setup）
- CLAUDE.md 更新：
  - §1 位置改 vein/、加註 rename 完成
  - §2 文案 ctx → Vein
  - §4 dogfood 段 ctx → Vein
  - §5 結構新增 docs_cloudflare/ + 雙 track 分工說明
  - §6 SOP 加第 9 條（碰公開內容前看 docs_cloudflare/_README.md）+ 修 numbering

**Why:**
- 內部 docs（繁中 / 開發歷程）跟公開 docs（英文 / 行銷文案）目標讀者不同，混在一起兩邊都做不好
- 用 docs_cloudflare/ 分開等於早期就劃出邊界、Cloudflare Pages 部署 pipeline 也乾淨

**雙 track docs 規則（鎖在 docs_cloudflare/_README.md）：**
| 資料夾 | 對象 | 語言 | commit 頻率 |
|---|---|---|---|
| `docs/` | Rex + Claude（內部）| 繁中 + 英術語 | 高 |
| `docs_cloudflare/` | OSS 社群、HN、Reddit | 英文為主 | 低（polish 後動）|

互引規則：**公開不引內部；內部可引公開；共享素材（tagline / 短描述）公開先定**。

**Public content lock-in（給未來 sessions reference）：**
- Hero tagline: **Lode finds the code. Vein remembers the why.**
- One-liner: "Local-first decision & debug lore archive for AI-assisted development"
- Differentiation pitch: "Two kinds of knowledge — what code does (LLM can derive), why it's this way (LLM cannot). Vein indexes the second."

**Lessons / Pitfalls:**
- 公開 docs 寫第一輪會自動曝露很多模糊：例如「vs ctx-sys」具體差在哪 — 寫到 why.md 才發現要再 reverify 一次
- 「pip install lode-vein」這個 split-naming 寫進 install.md 才發現一定要在 README 第一行解釋（避免「為什麼包名跟 CLI 名不一樣」的疑惑）
- 公開 docs 寫得太早會空洞（features.md / install.md 多數是 placeholder） — Phase 0 階段這 OK，但要明說「Phase 0 / early access」避免 oversell

**Files changed:**
- `docs_cloudflare/_README.md`（新）
- `docs_cloudflare/index.md`（新）
- `docs_cloudflare/about.md`（新）
- `docs_cloudflare/why.md`（新，多數 placeholder）
- `docs_cloudflare/features.md`（新，多數 placeholder）
- `docs_cloudflare/install.md`（新，多數 placeholder）
- `CLAUDE.md` §1 / §2 / §4 / §5 / §6 各小段更新

**未做（仍然 carry over 到 Session 1）：**
- `docs/spec/v0.1.md` Path D 改寫（核心動詞 / schema）
- Python package skeleton
- 第一個 `vein init` 命令
- `.dev` / `.app` domain 測試
- `sustainability.md` 維護紀律
- features.md / install.md polish（等 code 之後）

**Next session entry point：**
1. 寫 `docs/spec/v0.1.md` Path D 改寫
2. dogfood 先行（C）：手動在 Lode 建 `.vein/decisions/` 寫 3-5 條真實決策
3. Python package skeleton

**Time spent:** 0.1 session（資料夾 rename 確認 + 6 個公開 markdown scaffold + CLAUDE.md 同步，無 code）

---

## Session 0.11 — 2026-05-26 — OSS 確認 + repo 名 + visibility timing

**What:**
- Rex 問「這要做 OSS 嗎、repo 名」→ 答案早在 D-006 / D-007 已決（OSS MIT、`rex4ssd/vein`）
- 順帶結了一直懸著的 S3「visibility timing」未決問題
- 新增 **D-008**：private now, v0.3 flip public（三條件 trigger）
- 加 Phase 0 順手 checklist：**註冊 `lodevein` GitHub org**（保險、5 分鐘）
- strategy.md §9 S3 標已決議、§8 加「順手做」區塊
- CLAUDE.md §3 加 visibility 段 + Phase 0 順手 checklist

**Why:**
- 三個問題 chained：OSS? → 名? → 何時開？— Rex 問前兩個我順手結第三個
- visibility timing 早期定好避免日後拖延 / 反覆 second-guess
- `lodevein` org 保險：今天 5 分鐘 vs 將來被蹭名要打 trademark 戰爭

**Public flip 三條件（pre-flip checklist 寫在 D-008）：**
1. `vein init` + `vein log` + `vein recall` 能跑
2. Dogfood on Lode ≥ 2 週、≥ 10 條真實 decision/lore entries
3. README + docs_cloudflare 完整、陌生人 5 分鐘可上手

**為什麼選 B（private now）而非 A/C：**
- A (public day 1)：spec 還在 churn（10 個 sub-session 看到 Path A/B/C/D + 改名 3 次 + thesis pivot 1 次），public 觀感差
- C (public + alpha tag)：「alpha」對多數人沒擋，noise 大於收穫
- B：第一次接觸 Vein 的人看到 working product，跟 Lode 的 private dev + public release 同 pattern

**Files changed:**
- `decisions.md` 加 D-008（visibility 決定 + pre-flip checklist + lodevein org 預留）+ title 改 ctx → Vein
- `strategy.md` §9 S3 標已決 + §8 加 5-min insurance 段
- `CLAUDE.md` §3 加 visibility 段 + Phase 0 順手 checklist

**Next session entry point（不變）：**
1. spec/v0.1.md 改寫 Path D 形態
2. dogfood 先行（C path）：手動建 `.vein/decisions/` 寫 3-5 條 Lode 真實決策
3. Python package skeleton
4. **順手：去 GitHub 註冊 `lodevein` org（5 分鐘事，越早越好）**

**Time spent:** 0.1 session（D-008 + S3 收尾 + Phase 0 checklist 更新，無 code）
