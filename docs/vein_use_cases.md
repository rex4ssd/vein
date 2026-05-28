# Vein 實用場景圖

> 用 ASCII diagram 呈現 Vein 在真實開發中解決了什麼問題。
> 每個場景都有「沒有 Vein」vs「有 Vein」的對比。

---

## 場景一：Autocompact Thrashing（最直接的痛點）

### ❌ 沒有 Vein — Context 爆炸

```
Session 開始
    │
    ▼
┌─────────────────────────────────────────┐
│  Claude Code context（200K token limit）│
│                                         │
│  CLAUDE.md        ████░░░░░  ~3K        │
│  decisions.md     ████████░  ~8K        │
│  competitive.md   ██████████ ~12K       │
│  spec/v0.1.md     ████████░  ~9K        │
│  changelog.md     ███████░░  ~7K        │
│  (還沒開始做事)   ──────────  ~39K       │
└─────────────────────────────────────────┘
    │ 做了幾個 tool call，讀了幾個檔案
    ▼
┌─────────────────────────────────────────┐
│  context 滿了                           │
│  ██████████████████████████████████ 97%│
└─────────────────────────────────────────┘
    │ autocompact
    ▼
┌───────────────────┐
│  context 壓縮     │  ← 細節丟失
│  ████░░░░░░  45%  │
└───────────────────┘
    │ 繼續工作，context 又快速填回來
    ▼
  [3 次後：Autocompact thrashing error 💥]
```

### ✅ 有 Vein — 精準 context 載入

```
Session 開始，說明 task scope："修 D-002 sqlite-vec 連線問題"
    │
    ▼
  vein recall "sqlite-vec connection"
    │
    ├─ ollama embed query
    ├─ sqlite-vec top-5 match
    └─ llama3.2:3b digest
    │
    ▼
┌─────────────────────────────────────────┐
│  Claude Code context                    │
│                                         │
│  CLAUDE.md index  ██░░░░░░░░  ~500      │
│  vein digest      ████░░░░░░  ~2K  ← ✓ │
│  target file      ████░░░░░░  ~2K  ← ✓ │
│  (大量空間留給工作) ──────────  ~4.5K    │
└─────────────────────────────────────────┘
    │
    ▼
  整個 session 在 15% context 以內完成 ✓
```

---

## 場景二：多 LLM 協作（跨工具不失憶）

### ❌ 沒有 Vein — 每個 AI 都是孤島

```
Monday
  Rex ──► Claude ──► "為什麼選 sqlite-vec？"
             │          Claude 解釋了 15 分鐘
             ▼
          [session 結束，記憶消失]

Tuesday
  Rex ──► Gemini ──► "我們的 vector DB 用什麼？"
             │          Gemini: "我不知道，你告訴我？"
             ▼
          [Rex 重新解釋 15 分鐘]

Wednesday
  Rex ──► ChatGPT ──► "為什麼不用 chromadb？"
              │           ChatGPT: "chromadb 很好啊..."
              ▼
           [Rex 又解釋一遍]

每週浪費 ~45 分鐘重複解釋同樣的 context
```

### ✅ 有 Vein — 共用長期記憶

```
Monday
  Rex ──► Claude ──► 討論 + 決定 sqlite-vec
             │
             ▼
          vein log decision "選 sqlite-vec 原因：..."
             │
             ▼
         .vein/decisions/20260527-sqlite-vec.md ← 永久存在

Tuesday
  Rex ──► Gemini
             │
             ▼
          vein recall "vector db" → digest (2K)
             │  貼進 Gemini context
             ▼
          Gemini 立刻知道背景，直接進入討論 ✓

Wednesday
  Rex ──► local ollama (deepseek-r1:14b)
             │
             ▼
          vein recall "vector db" → 同一份 digest
             │
             ▼
          本機 AI 也知道，不需要網路 ✓

.vein/ 是中性格式，所有 AI 都能讀
```

---

## 場景三：Web Clipper（Chrome 選字 → Vein Lore）

```
Rex 在 Chrome 讀文章
"sqlite-vec: A vector search SQLite extension..."
    │
    │ 選取關鍵段落
    ▼
┌─────────────────────────────────────────────┐
│  Chrome 瀏覽器                              │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ "sqlite-vec achieves <1ms query on  │   │
│  │  10K vectors, zero daemon needed"   │   │
│  └──────────┬──────────────────────────┘   │
│             │ 選取後點 bookmarklet           │
└─────────────┼───────────────────────────────┘
              │
              ▼
    fetch('localhost:3747/log', {
      message: "selected text",
      source_url: "https://...",
      source_title: "sqlite-vec docs"
    })
              │
              ▼
    vein serve 收到請求
              │
              ├─ ollama: "這跟哪個決策有關？" → 建議 tag: [D-002, database]
              │
              ▼
    .vein/decisions/20260527-ref-sqlite-vec-perf.md
    ┌─────────────────────────────────────────┐
    │ ---                                     │
    │ type: reference                         │
    │ source_url: "https://..."               │
    │ source_title: "sqlite-vec docs"         │
    │ tags: [database, D-002, performance]    │
    │ ---                                     │
    │ "sqlite-vec achieves <1ms query..."     │
    └─────────────────────────────────────────┘
              │
              ▼
    下次 vein recall "sqlite performance"
    → 這條 reference 出現在 digest 裡 ✓

來源可追溯，不只是文字片段
```

---

## 場景四：Git Commit → 自動 Lore 提示

```
Rex 寫完一個複雜的修改
    │
    ▼
  git add -A && git commit -m "fix: sqlite-vec load path on macOS"
    │
    ▼
┌── post-commit hook（vein 安裝）──────────────┐
│                                              │
│  diff size: 87 lines  > threshold(50)       │
│                                             │
│  deepseek-r1:14b 分析 diff...               │
│                                             │
│  "這個 commit 修了 macOS extension 載入路徑，│
│   有 trade-off：hardcode vs dynamic detect" │
│                                             │
└──────────────────────────────────────────────┘
    │
    ▼
  提示：
  "🌿 vein: 要記錄這個決策嗎？
   建議：'macOS sqlite-vec load path 用 dynamic detect 不 hardcode'
   [Y/n/edit]"
    │
    ├─ Y → vein log 自動存入
    ├─ n → 跳過
    └─ edit → 開啟編輯器修改訊息後存入
    │
    ▼
  決策在 commit 當下就被捕捉，不會遺忘 ✓
```

---

## 場景五：台股 AI 下單 Audit Trail

```
每日 09:00 — AI 策略掃描
    │
    ▼
┌─────────────────────────────────────────┐
│  fubon_stock 策略引擎                   │
│                                         │
│  RSI(2330) = 27  ← oversold            │
│  法人買超 = +5000 張 (連3日)            │
│  MACD golden cross = True               │
│                                         │
│  → 訊號強度：HIGH                       │
└──────────────────┬──────────────────────┘
                   │ 下單前
                   ▼
    vein log decision \
      "買進 2330 100張 @ 920 — RSI=27, 法人連買3日,
       MACD golden cross; stop_loss=874(-5%);
       strategy=v3.2"
                   │
                   ▼
    [Fubon Neo API 下單]  →  成交 @ 921
                   │
                   ▼
    vein log lore "成交 @ 921 (滑點+1), 09:03:42"

─────────────── D+3，股價下跌 ──────────────────

    觸發 stop_loss @ 874
                   │
                   ▼
    vein log lore \
      "2330 停損 @ 875 (-4.9%); 
       事後分析：法人買超是主力出貨假象，
       D+2 融券暴增是預警訊號（當時策略未納入）"

─────────────── 事後 debug ──────────────────────

    vein recall "2330 trade 2026-05-28"
                   │
                   ▼
    ┌─────────────────────────────────────┐
    │  Digest:                            │
    │  • 進場邏輯：RSI+法人+MACD (v3.2)  │
    │  • 執行：921 成交                   │
    │  • 出場：875 停損                   │
    │  • 教訓：融券變化未納入策略         │
    └─────────────────────────────────────┘
                   │
                   ▼
    下一版策略（v3.3）加入融券過濾條件 ✓
    決策脈絡完整保留，不靠記憶
```

---

## 場景六：新 Claude Session — 冷啟動 vs 暖啟動

```
─────────────── ❌ 沒有 Vein ───────────────────

Rex: "幫我改 Lode 的 DualTree 元件"

新 Claude: "好的，Lode 是什麼？DualTree 是什麼？
            你們的設計原則是什麼？
            之前有哪些相關決策？"

  Rex 需要解釋 ~10 分鐘才能讓 Claude 進入狀態
  每次換 session / 換 AI 都重來

─────────────── ✅ 有 Vein ─────────────────────

Rex: "幫我改 Lode 的 DualTree 元件"
       │
       │ (session 開始，自動或手動)
       ▼
  vein recall "DualTree component"
       │
       ▼
  ┌────────────────────────────────────────┐
  │  Digest (≤2K token):                  │
  │                                        │
  │  D-015: DualTree 用 virtual scroll     │
  │         不用 react-window，因為...     │
  │  D-018: pane resize 用 ResizeObserver  │
  │         不用 onMouseMove，原因...      │
  │  P-003: tree node expand 在 1000+      │
  │         nodes 時 re-render 問題，解法…│
  └────────────────────────────────────────┘
       │ 貼進 context
       ▼
  新 Claude 立刻知道所有背景
  直接說："好，DualTree virtual scroll 的
           部分要怎麼改？"

  冷啟動時間：~30 秒（而不是 10 分鐘）✓
```

---

## 場景七：大記憶 AI Server（未來）

```
現在 (2026)                    未來 (~2028)
─────────────                  ──────────────────

Mac Studio M1 32GB             Mac Studio Ultra 192GB
ollama: llama3.2:3b            ollama: Llama-4 70B+
context: 8K effective          context: 1M+ token

┌──────────────────┐           ┌──────────────────────────┐
│ vein recall      │           │ vein recall --raw        │
│ digest ≤ 2K      │           │ 全量 lore，不壓縮         │
│                  │           │                          │
│ .vein/ 有        │           │ .vein/ 同一份，格式不變  │
│ 1000 條 lore     │     →     │                          │
│ 輸出 top-5 摘要  │           │ AI 直接讀所有 1000 條    │
│                  │           │ 自己做 cross-reference   │
└──────────────────┘           └──────────────────────────┘

.vein/ 的 markdown 格式不變
budget 參數讓同一工具適應不同算力

vein recall "query"              → 2K  (省錢 mode)
vein recall --budget 32k "query" → 32K (本機 13B)
vein recall --raw "query"        → 全量 (未來 405B)
```

---

## 場景八：新視窗 / 小問題的 Grep Waste

### ❌ 沒有 Vein — 每次定向都要重新探索

```
Rex: "為什麼 DualTree 用 virtual scroll 不用 react-window？"

新 Claude session 開始
    │
    ▼
Claude: 讓我先了解一下這個專案...
    │
    ├─ grep "DualTree" src/        [tool call 1]  ~300 token
    ├─ read src/components/DualTree.tsx            ~2K  token
    ├─ grep "react-window" package.json            ~100 token
    ├─ grep "virtual" src/          [tool call 4]  ~400 token
    ├─ read src/hooks/useVirtual.ts                ~1K  token
    ├─ grep "performance" docs/     [tool call 6]  ~200 token
    └─ read docs/decisions.md (全文)               ~8K  token
    │
    ▼
  [7 個 tool call，消耗 ~12K token]
    │
    ▼
Claude: "根據我的分析，DualTree 使用了..."

─────────── 下次開新視窗，一樣的問題 ────────────

Rex: "DualTree 為什麼這樣設計？"  ← 同類問題
    │
    ▼
Claude: 讓我先了解一下這個專案...  ← 重來一遍
    │
  [又是 7 個 tool call，~12K token]

每次新 session = 重新繳定向稅
小問題 = 大代價
```

### ✅ 有 Vein — brief 一次，ask 秒答

```
場景 A：開新 session（任何問題規模）

Rex 開啟新對話視窗
    │
    ▼
  vein brief                        [1 個指令，~3 秒]
    │
    ▼
┌──────────────────────────────────────────────────┐
│  Project Brief — Lode (2026-05-27 14:30)         │
│                                                  │
│  What: macOS file viewer/compare (Tauri+Rust+React)│
│  Phase: v0.4, DualTree refactor active           │
│                                                  │
│  Key Decisions:                                  │
│  D-015: DualTree → virtual scroll (not           │
│         react-window): 10K+ nodes perf           │
│  D-018: pane resize → ResizeObserver             │
│         (not onMouseMove): Safari jank           │
│  D-022: file watch → notify crate (FSEvents)     │
│                                                  │
│  Active Pitfalls:                                │
│  P-003: expand 1000+ nodes → re-render           │
│  P-007: Windows path sep → use Path::join        │
│                                                  │
│  Recent: monaco flicker fix (2026-05-26)         │
└──────────────────────────────────────────────────┘
    │ ~800 token，貼進 context
    ▼
Claude 已知所有背景，直接開始工作

Token cost: 800  vs  12,000  (節省 93%)
Tool calls: 0    vs  7

─────────────────────────────────────────────────

場景 B：小問題秒答

Rex: "為什麼 ResizeObserver？"
    │
    ▼
  vein ask "ResizeObserver pane resize"
    │
    ▼
  llama3.2:3b 查 .vein/ index
    │
    ▼
┌──────────────────────────────────────────────────┐
│  D-018 (2026-05-15):                            │
│  用 ResizeObserver 不用 onMouseMove，因為        │
│  Safari 的 onMouseMove 在 cross-iframe 情境下    │
│  有 50ms lag，ResizeObserver 是 native API       │
│  無此問題。代價：IE 不支援（可接受）             │
└──────────────────────────────────────────────────┘
    │ 直接貼給 Claude，0 grep
    ▼
Claude: "好，D-018 已說明原因，你想改什麼部分？"

Tool calls: 0  (之前需要 4-5 個)

─────────────────────────────────────────────────

場景 C：vein 沒答案 → 自動補強

Rex: "為什麼 cargo build 要加 --release 才夠快？"
    │
    ▼
  vein ask "cargo release build"
    │
    ▼
  [.vein/ 沒有這條 lore]
    │
    ▼
  "沒有相關 lore，建議 grep 後記錄"
    │
    ▼
  Claude grep / read → 找到答案
    │
    ▼
  vein log lore "cargo --release 原因：debug build
    包含 debug symbols，執行速度慢 10x，
    Tauri 的 file watcher 在 debug mode 下
    有額外 overhead"
    │
    ▼
  下次同類問題 → vein ask 直接回答 ✓

.vein/ 越用越聰明，定向稅越來越低
```

---

## 全景：Vein 在開發生命週期中的位置

```
                    開發生命週期
┌──────┬──────────┬──────────┬──────────┬──────────┐
│ 設計 │ 實作     │ Debug    │ Review   │ 交接     │
└──┬───┴────┬─────┴────┬─────┴────┬─────┴────┬─────┘
   │        │          │          │          │
   ▼        ▼          ▼          ▼          ▼
vein log  vein log   vein log   vein       vein
decision  lore       pitfall    review     recall
"為什麼   "git hook  "踩到的    "這個      "給新人
選 A      提示"      雷"        PR 有      / 新 AI
不選 B"               │         沒有跟     的完整
   │         │         │         D-005     背景"
   └─────────┴─────────┘         衝突？"
             │
             ▼
        .vein/ (git-tracked markdown)
             │
    ┌────────┼────────┐
    ▼        ▼        ▼
  Claude   Gemini   ollama
  (cloud)  (cloud)  (local)
             │
             ▼
     任何 MCP client (Phase 3)
```

---

## 一句話總結各場景

| 場景 | Vein 解決的問題 |
|---|---|
| Autocompact thrashing | context 只載入需要的 lore，不全量讀 |
| 多 LLM 協作 | 共用 `.vein/`，AI 不再各是孤島 |
| Web Clipper | 網頁資訊捕捉時記錄「為什麼重要」，不只存文字 |
| Git Hook | commit 當下問你要不要記 lore，不靠事後回憶 |
| 台股 AI 下單 | 每筆 AI 決策都有 audit trail，debug 有據可查 |
| 新 session 冷啟動 | 30 秒暖機 vs 10 分鐘重新解釋 |
| 大記憶 AI Server | 同一份 `.vein/`，budget 調大就能用，格式不變 |
