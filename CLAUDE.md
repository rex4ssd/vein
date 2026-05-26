# Vein — Project Brief

> 部分屬於 **Lode Vein** product family（Lode = file viewer 已存在；Vein = decision lore archive 本專案）。
> 曾用名 ctx，2026-05-26 改名 → vein，2026-05-26 升級為 product family，見 [`docs/decisions.md` D-007](docs/decisions.md#d-007--專案改名為-vein採lode-vein-product-family-命名2026-05-26)。
>
> **Decision & debug lore archive**，給人類 + 多個 LLM 協作用。
>
> > **Lode finds the code. Vein remembers the why.**
>
> CLI + (未來) MCP server。Local-first，**markdown-based**，git-friendly。

## 1. 專案概況

- **產品名：** Vein
- **Family marketing 名：** Lode Vein（對外講話 / blog / homepage 用）
- **Split naming：** CLI = `vein`、PyPI = `lode-vein`、GitHub = `rex4ssd/vein`、Homebrew = `vein` via `rex4ssd/tap`
- **位置：** `/Users/lion/Documents/vein/`（Session 0.10 已從 `ctx/` rename 完成）
- **狀態：** Phase 0（docs scaffold 完成、改名 + family 命名拍板、Path D 確認，code 未開始）
- **Positioning：** Path D — decision lore niche，**不是** code RAG broker（避開 7+ 競品紅海）
- **Stack 預定：** Python 3.11+、Click（CLI）、ollama HTTP API、sqlite-vec、(後續) MCP SDK
- **License 預定：** MIT（OSS 友善）
- **Dogfood 對象：** Lode 專案（`/Users/lion/Documents/lode/`），同時驗證 generic Python project

## 2. 為什麼存在（vision）

每個專案有大量 docs / decisions / changelog / code，每個 LLM session 都重新讀。三個痛點：

1. **Claude context 容易爆**：per-turn payload 太大，autocompact thrashing
2. **多 LLM 重複載入**：Claude / Gemini / GPT / local 各自重啃同樣的 docs
3. **沒有 portable 的「專案 AI 記憶」格式**：換工具 / 換電腦 / 換 model 就丟

Vein 解法：把專案的 **decision & debug lore** 存進 `.vein/`（像 `.git/`），由 **local AI 預處理 + capture-time polish**，cloud LLM 只看 ≤ 2K token 的 digest。

完整 vision + 技術細節見 [`docs/spec/v0.1.md`](docs/spec/v0.1.md)。
商業策略 / Open Core 模式 / 護城河見 [`docs/strategy.md`](docs/strategy.md)。

## 3. Phase 0 scope（Path D 形態）

- [ ] CLI skeleton: `vein init / log / recall / review / status`
- [ ] `.vein/` schema 設計與實作（decisions/*.md + debug_lore/*.md + links/）
- [ ] ollama integration（capture 時 polish + 小規模 RAG retrieval）
- [ ] Lode v0.2 整合「Send to vein」按鈕（從 diff 抓 decision/lore）
- [ ] dogfood on Lode 一個月，驗證決策 capture / recall 工作流

**Visibility（D-008）：** **private repo `rex4ssd/vein` 現在**，三條件達成後 flip public：
1. `vein init` + `vein log` + `vein recall` 能跑
2. Dogfood on Lode ≥ 2 週、≥ 10 條 entries
3. README / docs_cloudflare 完整、陌生人 5 分鐘可上手

**順手做（Phase 0 checklist）：**
- [ ] 註冊 `lodevein` GitHub org（namespace 保留，5 分鐘的事）
- [ ] 測試 `vein.dev` / `vein.app` domain availability

**不做（明確 out-of-scope）：**
- MCP server（Phase 0.3）
- web UI（Phase 0.4）
- multi-project sync
- framework / SDK 抽象
- 任何「給別人用」的 polish（先自用）

## 4. 工作原則（給接手的 Claude）

完整版見 [`docs/working_style.md`](docs/working_style.md)。最關鍵的：

🔴 **Commit workflow：**
- user 說 "ca" → Claude 直接 `git add -A && git commit -F -`，**不問**
- 遇到 `index.lock`：`rm -f .git/index.lock` 後再 commit

🔴 **指令打包：**
- 多行 cmd → 寫成 `.sh` 給 user 跑
- 多行 `.sh` → 集合成 `.py`（參考 `/Users/lion/Documents/py/cmd_entry.py`）
- sandbox 沒有的東西（ollama call、brew tool）→ 包成 .sh，user 跑、output 貼回

🔴 **回答風格：**
- 繁體中文、技術詞英文
- 清楚、有邏輯、正確
- terse 優於 verbose，user 看得懂 diff，不要在 chat 重複解釋已寫好的程式碼
- 沒必要的 postamble 不寫

🔴 **決策有 trade-off 就 record：**
- 任何「為什麼選 A 不選 B」的選擇 → 寫進 [`docs/decisions.md`](docs/decisions.md)
- 任何踩過的雷 → 一樣寫進 decisions.md 雷區 section
- 這份檔不是裝飾，是給三個月後 / 別人接手用的

🔴 **本檔自己也要 dogfood：**
- Vein 自己要建 `.vein/`
- Vein 跑出來的 brief 要回灌到 Vein 開發本身
- 「Vein 不能解決 Vein 自己的開發痛點」= 設計失敗

## 5. 檔案結構

```
vein/
  CLAUDE.md                    ← 這份（精簡 index）
  docs/                        ← 內部開發 docs（繁中 + 英術語）
    spec/
      v0.1.md                  ← Phase 0 technical RFC（Path A/B 形態，待依 Path D 改寫）
    strategy.md                ← 商業 / 戰略 / Open Core / Path D thesis（§11）
    competitive_landscape.md   ← 競品 audit（2026-05-26 snapshot）
    naming.md                  ← 改名 brainstorm + 拍板 vein + Lode Vein family
    working_style.md           ← Rex 偏好 + 工作模式（給 Claude 看）
    decisions.md               ← 決策 log + 雷區（D-001~D-007）
    changelog.md               ← session-by-session 開發日誌
    architecture.md            ← (待寫，code 開工後補)
  docs_cloudflare/             ← 公開網站內容（英文為主，deploy 到 rexcode.app/vein）
    _README.md                 ← 不 publish，內部說明
    index.md                   ← homepage（hero + tagline + feature 卡片）
    about.md                   ← What is Vein / Lode Vein family
    why.md                     ← problem / 我們的解 / vs 競品
    features.md                ← 功能列表（placeholder，等 code）
    install.md                 ← Get started（placeholder，等 code）
  src/                         ← (Phase 0 開始寫 Python package)
  .vein/                       ← (dogfood 自己建)
```

**內部 vs 公開 docs 分工：**
- `docs/` 對 Rex + Claude（內部 session）— 開發歷程、決策、雷區、繁中
- `docs_cloudflare/` 對外部讀者（OSS 社群、HN、Reddit）— polish 過的行銷文案、英文為主
- **互引規則：** 公開 docs 不引內部；內部可引公開。共享素材（tagline / feature 短描述）公開先定，內部跟著用
- 細節見 [`docs_cloudflare/_README.md`](docs_cloudflare/_README.md)

## 6. 接手 SOP

1. 讀本檔（你正在做這件事）
2. 讀 [`docs/strategy.md`](docs/strategy.md) **§11 Path D thesis** — 知道現在的方向（decision lore archive）
3. 讀 [`docs/spec/v0.1.md`](docs/spec/v0.1.md) — 知道技術初稿（Path A/B 形態，待依 Path D 改寫）
4. 讀 [`docs/competitive_landscape.md`](docs/competitive_landscape.md) — **知道我們進的是紅海還是藍海**
5. 讀 [`docs/naming.md`](docs/naming.md) — 為什麼叫 vein
6. 讀 [`docs/working_style.md`](docs/working_style.md) — 知道怎麼跟 Rex 共事
7. 摸決策 / 雷區前讀 [`docs/decisions.md`](docs/decisions.md)（D-007 名字、D-006 商業模式）
8. 要找歷史 → grep [`docs/changelog.md`](docs/changelog.md)
9. 摸公開網站內容前讀 [`docs_cloudflare/_README.md`](docs_cloudflare/_README.md)
10. 改完跑 sanity check（一旦有 code 之後補）：
    ```bash
    ruff check .
    pytest -q
    ```
11. 收工自行 commit（見 §4）

## 7. 使用者 Context

**R (Rex)**，Python 5+ 年，Mac Studio M1 32GB RAM，US keyboard。

同時用 Claude / Gemini / ChatGPT，本機跑 ollama（llama3.2:3b / qwen2.5-coder:7b / deepseek-r1:14b）。

Lode 作者（Tauri 2 + Rust + React，私有 repo `rex4ssd/lode`），同期還有富邦選股系統、Jekyll 投資筆記站、YSK 字幕 pipeline。Python project group 在 `/Users/lion/Documents/py/`。

偏好：**暗色主題、繁體中文、技術詞英文、清楚有邏輯、no game**。
