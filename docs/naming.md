# Naming Brainstorm — Path D 改名候選

> Session 0.8 brainstorm。`ctx` 已被至少 3 個 OSS 撞名，必改。
> Path D (decision lore archive) positioning 下要選一個能撐 5+ 年的名字。

---

## 0. 命名原則

1. **短**（≤ 6 字母最佳，CLI 命令會被打很多次）
2. **真實英文字**（Lode 是真詞，這專案應同樣風格；不要 invented）
3. **語意有 anchor 但不過度限定**（不要像 "adr-tools" 那樣鎖死）
4. **跟 Lode 共生**（同 brand family 加分）
5. **發音零歧義**（國際 OSS audience）
6. **可註冊**（GitHub org、PyPI、npm、`.dev` domain）— 待後續實測

---

## 1. 候選總表（5 分類，20 候選）

### A. 礦業意象（跟 Lode 同族）

| 名 | 字數 | meaning | CLI 範例 | 評分 |
|---|---:|---|---|:---:|
| **vein** | 4 | 礦脈分支 | `vein log "..."` | ⭐⭐⭐⭐⭐ |
| **seam** | 4 | 煤層 / 沉積層 | `seam add "..."` | ⭐⭐⭐⭐ |
| **trove** | 5 | 寶藏堆 | `trove keep "..."` | ⭐⭐⭐ |
| **relic** | 5 | 古物 / 遺跡 | `relic log "..."` | ⭐⭐⭐ |
| **shaft** | 5 | 礦坑通道 | `shaft log "..."` | ⭐⭐ |

### B. 「核心 / 重點」意象

| 名 | 字數 | meaning | CLI 範例 | 評分 |
|---|---:|---|---|:---:|
| **crux** | 4 | 關鍵 / 癥結 | `crux log "..."` | ⭐⭐⭐⭐⭐ |
| **pith** | 4 | 本質 / 要點 | `pith add "..."` | ⭐⭐⭐ |
| **nub** | 3 | 核心要點 | `nub keep "..."` | ⭐⭐ |
| **gist** | 4 | 大意 | （**GitHub 已佔**） | ❌ |

### C. 古代刻寫意象（永久記錄）

| 名 | 字數 | meaning | CLI 範例 | 評分 |
|---|---:|---|---|:---:|
| **etch** | 4 | 蝕刻 / 銘刻 | `etch decision "..."` | ⭐⭐⭐⭐ |
| **rune** | 4 | 古老符文 | `rune log "..."` | ⭐⭐⭐⭐ |
| **glyph** | 5 | 銘刻符號 | `glyph add "..."` | ⭐⭐⭐⭐ |
| **stele** | 5 | 石碑 | `stele log "..."` | ⭐⭐⭐ |
| **vellum** | 6 | 羊皮紙 | `vellum log "..."` | ⭐⭐⭐ |

### D. 記憶 / 召回（語源、典籍）

| 名 | 字數 | meaning | CLI 範例 | 評分 |
|---|---:|---|---|:---:|
| **mnemo** | 5 | Mnemosyne 記憶女神 | `mnemo recall "..."` | ⭐⭐⭐⭐ |
| **tome** | 4 | 大部頭典籍 | `tome add "..."` | ⭐⭐⭐⭐ |
| **yore** | 4 | 久遠之前 | `yore log "..."` | ⭐⭐⭐ |
| **attic** | 5 | 閣樓 / 存儲老物 | `attic stash "..."` | ⭐⭐⭐ |
| **kept** | 4 | 保留下來的 | `kept "..."` | ⭐⭐ |

### E. 直接描述型

| 名 | 字數 | meaning | CLI 範例 | 評分 |
|---|---:|---|---|:---:|
| **debrief** | 7 | 任務後檢討 | `debrief log "..."` | ⭐⭐⭐⭐ |
| **dbrief** | 6 | 同上 abbr | `dbrief "..."` | ⭐⭐⭐ |
| **adrly** | 5 | ADR-derived | `adrly new "..."` | ⭐⭐⭐ |
| **whyfile** | 7 | 顯式 why | `whyfile add "..."` | ⭐⭐ |

---

## 2. Top 5（綜合排名）

### 🥇 #1 vein

**為什麼第一：**
- **跟 Lode 同 mining brand family** — 沒有競品有這個 asset
- 4 字母，跟 Lode 同 footprint
- 「Vein of lore」「Vein of decisions」語感對
- 「礦脈」隱喻自然：「Lode 是大礦脈、Vein 是支脈」
- Mining 在 software namespace 很少用 → adoption 衝突低

**Product narrative:**
> Lode finds the code. Vein remembers the why.
> Lode 找到檔。Vein 記住決定。

**CLI feel:**
```bash
vein log decision "drop sqlite for parquet — single-writer scale fail"
vein log lore "API rate limit 回 200 not 429 — see api/client.rs:142"
vein recall "sqlite"
vein review --since 7d
vein link --to-file src/main.rs:42
```

**風險：** mining 比喻會不會太特定？反例：Linear (project mgmt) / Sentry (errors) / Vercel (deploy) 都是抽象名字 + 強 brand，不靠字面意義生存。Vein 一旦立住，自然有意義。

---

### 🥈 #2 crux

**為什麼第二：**
- **語意完美** — decision = crux of the matter
- 4 字母，clean CLI 命令
- 全球發音一致（krʌks）

**CLI feel:**
```bash
crux log "..."
crux recall "..."
crux review
```

**風險：**
- "crux" 是 Rust workshop 同名（Bryan Cantrill team），PyPI 可能被佔
- 攀岩運動「crux move」也是同詞 — 不衝突但搜尋會 noise
- 跟 Lode 沒 brand pairing

---

### 🥉 #3 etch

**為什麼第三：**
- 動詞性強：「etch into history」
- 4 字母
- 少撞名（不是常見專案名）
- 隱喻好：「決策被 etch 進永久記錄」

**CLI feel:**
```bash
etch "decision: drop sqlite"
etch lore "API quirk"
etch recall "sqlite"
```

**風險：**
- "Etch app" / "Etch 工具" 聽起來像繪圖工具
- 動詞變名詞略 awkward

---

### 4️⃣ mnemo

**為什麼第四：**
- 字源好：Mnemosyne（希臘記憶女神，繆思的母親）
- 5 字母
- 有故事可講

**CLI feel:**
```bash
mnemo log "..."
mnemo recall "..."
```

**風險：**
- 發音歧義（NEE-mo / meh-MOH / MEM-no）
- 字源 anglo 不熟的人不會聯想
- mnemonic / mnemonist 一堆衍生詞，namespace 擁擠

---

### 5️⃣ debrief

**為什麼第五：**
- **語意 100% match**（軍事 / 飛行員「debrief」= 任務後回顧 = exactly what we capture）
- 已是常用英文，零學習成本

**風險：**
- **7 字母太長**當 CLI 主命令（每次 `debrief log "..."` 痛）
- 「dbrief」變體又失去明確性
- 跟 Lode 沒 brand pairing

---

## 3. 黑馬候選（值得保留視野）

- **seam** — 跟 Lode 同 mining、4 字、`seam log "..."` 順、不如 vein 強但備案
- **rune** — 古老 + 編碼 雙重意象、gaming 觸發但專案名占地不多
- **glyph** — 同 rune 但更「符號 / 數位」感
- **tome** — 「tome of lore」很有畫面、Path D 後期 archive 概念合
- **trove** — 「treasure trove」 適合「找回寶貴決策」narrative

---

## 4. 已知排除

- ❌ `ctx` — 撞 3 個 OSS
- ❌ `gist` — GitHub 註冊商標
- ❌ `lore` — 太通用、Twitch 用語、必撞
- ❌ `codex` — OpenAI Codex
- ❌ `vault` — 1Password / HashiCorp Vault
- ❌ `ledger` — blockchain 太多
- ❌ `archive` — 太通用
- ❌ `memo` — 太通用

---

## 5. 待 Rex 決：方向收斂

四個方向二選一 / 三選一：

**方向 1：Lode 同 brand family（mining）** → vein / seam / trove
**方向 2：核心 / 重點抽象** → crux / pith
**方向 3：古代刻寫永久感** → etch / rune / glyph / mnemo
**方向 4：直接描述** → debrief / adrly

我推方向 1（vein），但 Rex 內心可能對某個方向有更強感覺。

---

## 6. Availability 實測（待 Rex 收斂方向後做）

下一步要查的：

```bash
# GitHub
# https://github.com/<NAME>?type=repositories
# https://github.com/search?q=<NAME>&type=repositories

# PyPI
pip search <NAME>   # (search deprecated, 改用 https://pypi.org/search/?q=<NAME>)

# npm
npm search <NAME>

# Cargo
# https://crates.io/search?q=<NAME>

# Domain
whois <NAME>.dev
whois <NAME>.app
whois <NAME>.so
```

收斂到 2-3 個 finalist 之後，跑這個檢查並記錄。

---

## 7. Lode Vein product family（已確認，2026-05-26 Session 0.9）

採 **Microsoft Office pattern**：family suite 包多個獨立 product，每個 product 有獨立短名。

| Family / Suite | **Lode Vein** |
|---|---|
| Product A — Lode | desktop GUI / file viewer / compare（已存在，付費）|
| Product B — Vein | decision lore archive CLI + MCP（本專案，OSS）|
| (預留) Product C — Seam | mining: 礦層 / 縫，可能 future 整合層 |
| (預留) Product D — Shaft | mining: 礦坑，可能 future 跨機器 sync |

整套品牌 thesis：「mining your own codebase for value」。
網站架構：rexcode.app/lode + rexcode.app/vein 同根。

### Marketing 講法分通路

| 場景 | 用詞 |
|---|---|
| Blog 標題 / 主視覺 | **Lode Vein** — Decision & debug lore for AI-assisted dev |
| Homepage hero | "**Lode Vein**: the missing decision history for your AI" |
| Vein 自己的 README | "**Vein** (part of the **Lode Vein** suite) — local-first decision lore archive" |
| 對話介紹 | 「我做了 **Lode Vein**，Lode 找到檔，Vein 記住為什麼」 |
| Lode 用戶圈 | 「Lode 旁邊那個 Vein」 |
| OSS / HN / Reddit | 「Vein — decision lore archive for AI coding」（不依賴 Lode 也講得通）|

### 關鍵原則

- **CLI 永遠是 `vein`**（短、無連字號），不是 `lode-vein`
- **PyPI 是 `lode-vein`**（避 squat、明示 family）
- **對話 / 行銷講「Lode Vein」**（family 包裝）
- **README 第一行明示 part of Lode Vein suite**（給社群 context）
- **Vein 必須 standalone 講得通**（OSS 信任，不靠 Lode 才有用）

---

## 8. 我（Claude）個人傾向

**vein** > crux > etch > 其他。

但這是 Rex 一輩子要打 `vein log` 幾百萬次的事，**直覺投票權在 Rex**。我寫到這份是讓你晚上睡前心裡反覆唸三個名字，看哪個自然冒出來。

---

## 9. 最終決定：vein + Lode Vein family ✅（2026-05-26 Rex 拍板）

**Rex 選擇：**
- **產品名：** vein（Session 0.8，方向 1：mining brand family）
- **Family marketing 包裝：** Lode Vein（Session 0.9，Microsoft Office pattern）

**Rejected 的替代案（Session 0.9 review）：**
- `lode-ctx` — undo Path D 跳脫 ctx 紅海的核心目的，連字號 CLI 痛
- `lode-vein` 當 CLI 名 — 連字號痛、9 字過長
- `vein-ai` — `-ai` 2024 cliché 會老化
- `vein-cli` — 將來加 MCP server 名字錯

### 9.1 Availability check 結果

| 通路 | 狀況 | 處理 |
|---|---|---|
| **npm `vein`** | 🟢 空 | OK |
| **GitHub `rex4ssd/vein`** | 🟢 可建 | OK |
| **GitHub `vein` 同名 org** | 🟡 `Vein-API` org 存在但不擋我們 repo | OK |
| **PyPI `vein`** | 🔴 **被 squat** — Josh Breidinger 2025-06-26 上傳 placeholder（1.6 kB、`vein.hello()`，無後續） | Split naming |
| **`.dev` / `.app` domain** | ❓ 未測 | 待測 |

### 9.2 Split naming 策略（避開 PyPI squat）

| 通路 | 名稱 |
|---|---|
| Brand / 對外名 | **vein** |
| CLI 命令 | `vein` |
| GitHub repo | `rex4ssd/vein` |
| PyPI package | `lode-vein`（暫定） |
| Homebrew | `vein` via `rex4ssd/tap` |
| Domain | `rexcode.app/vein` subdirectory |

業界常態（`python-dotenv` / `httpx[cli]` 都這樣做）。CLI 名仍是 `vein`，用戶日常無感。

詳見 [`decisions.md` D-007](decisions.md#d-007--專案改名為-vein2026-05-26)。
