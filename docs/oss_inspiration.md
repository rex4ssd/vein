# OSS 靈感 — 可抄的設計 & Vein 能幫的地方

> 來源：`github_io/ai/ai_resources/` 的四份筆記（2026-05-27 snapshot）
>
> 格式：每個專案先說「跟 Vein 有沒有交集」，再說「抄什麼」和「能幫什麼」。
> 標記：🟥 高優先 / 🟨 中優先 / 🟩 低優先（對 Vein roadmap 的影響程度）

---

## 快速總表

| 專案 | 與 Vein 關係 | 抄什麼 | 幫什麼 |
|---|---|---|---|
| gbrain | 🟥 最近似競品 | MCP 整合方式 | 精準定位差異 |
| Rapid-MLX | 🟥 直接替換 ollama | 4.2x 推論速度 | vein brief/recall 更快 |
| MarkItDown | 🟥 擴大 capture 來源 | 任意檔轉 MD | vein import 非程式碼決策 |
| andrej-karpathy-skills | 🟨 同類 CLAUDE.md | Goal-Driven 原則 | Vein lore 的品質守門 |
| GStack | 🟨 互補 | 角色化 prompt | vein recall 加 role 參數 |
| design-md-chrome | 🟨 驗證 D-012 | web→MD 擷取模式 | 互補定位 |
| caveman | 🟨 哲學相符 | terse 輸出模式 | vein log --terse |
| jt-live-whisper | 🟩 未來 capture 源 | 音訊→文字 pipeline | vein import --from-transcript |
| TimesFM | 🟩 fubon_stock 相關 | 時序預測 | 策略決策的 lore anchor |
| LangChain | 🟩 生態整合 | Retriever 介面設計 | VeinRetriever class |
| Printing Press | 🟩 已討論 | ecosystem play | 互補（已入 D-011） |
| Qdrant | 🟩 資料庫參考 | payload filter | fubon_stock scale 時備選 |
| Claude Design | 🟩 間接 | design→CLAUDE.md | 未來 Lode × Vein 整合 |

---

## 🟥 gbrain (garrytan/gbrain) — 最需要認清的對手

**它是什麼：** GStack 的記憶層。把 Obsidian 筆記 + 程式碼透過 nomic-embed-text 向量化存進 SQLite，
MCP 掛載後 Claude/Cursor 提問時自動檢索。

**和 Vein 的差異（必須說清楚）：**

```
                gbrain                    Vein
                ──────                    ────
記憶內容    raw notes / code          curated decision lore
捕捉方式    自動 index（被動）        主動 vein log（有意識）
品質控制    無（垃圾進，垃圾出）      ollama polish at capture time
格式        向量 DB（opaque）         markdown（人可讀，git-tracked）
跨工具      gstack 生態內             任何 MCP client + 任何 LLM
ownership   Obsidian 依賴             .vein/ 跟 .git/ 一樣是你的
```

**一句話區隔：**
> gbrain 記住你「寫了什麼」，Vein 記住你「為什麼這樣決定」。

**可以抄的：**
- gbrain 的 MCP `add` 安裝方式超簡單（`claude mcp add gbrain --vault-path ~/...`）
  → Vein Phase 3 的 `vein serve --install` 要做到同等一鍵體驗
- gbrain 把 Obsidian 當 vault → Vein 可以提供 `vein import --from-obsidian <vault>` 作為遷移路徑

**Vein 能幫 gbrain 用戶：**
gbrain 用戶的痛點是「raw notes 太雜，AI 召回品質不穩定」。
Vein 可以作為 gbrain 的精煉層：把重要的 gbrain note 手動 `vein log`，只讓 Vein 管最關鍵的 decision lore，其餘 raw notes 繼續留 gbrain。

---

## 🟥 Rapid-MLX — 把 ollama 的速度問題直接解掉

**它是什麼：** Apple Silicon 原生推論引擎，直接用 Metal API，unified memory zero-copy。
18 個模型中拿 16 個速度冠軍，比 ollama 快 **4.2x**。

**對 Vein 的直接影響：**

| 指令 | ollama（現在） | Rapid-MLX（如果換） |
|---|---|---|
| `vein brief` | ~5-8 秒 | ~1-2 秒 |
| `vein recall` | ~6-10 秒 | ~1.5-2.5 秒 |
| `vein log` polish | ~3-5 秒 | < 1 秒 |

`vein ask` 的互動感會從「等待感」變「秒回」。

**可以抄的：**
- Vein 的 model backend 應該抽象化，讓用戶選 ollama 或 rapid-mlx
- `config.yaml` 加 `backend: ollama | rapid-mlx`
- 安裝文件加「Apple Silicon 用戶推薦 Rapid-MLX」

**架構影響（Phase 1 就要做對）：**
```yaml
# .vein/config.yaml
model:
  backend: ollama          # 或 rapid-mlx
  embed_model: nomic-embed-text
  digest_model: llama3.2:3b
  polish_model: qwen2.5-coder:7b
  base_url: http://localhost:11434   # ollama
  # base_url: http://localhost:8080  # rapid-mlx（API 相容 ollama）
```

Rapid-MLX API 跟 ollama 相容，所以切換幾乎零成本。這個抽象層 Phase 1 就要建，不然之後要改 hardcode。

**Vein 能幫 Rapid-MLX：**
Rapid-MLX 沒有 project memory。用戶在調 inference 參數時踩的雷（quantization 選擇、batch size trade-off）可以用 Vein 記錄。

---

## 🟥 MarkItDown (Microsoft) — 打開 vein import 的大門

**它是什麼：** `pip install markitdown`，把 PDF / Word / Excel / PPT / HTML / 圖片全轉成 Markdown。

**對 Vein 的直接影響：**

沒有 MarkItDown 之前，`vein log` 只能處理文字輸入（你自己打）。
有了 MarkItDown，Vein 可以從任何文件擷取 lore：

```bash
# 你有一份 API spec PDF，裡面有影響架構的設計決策
vein import --from-file spec.pdf
→ 內部：markitdown spec.pdf → markdown
→ ollama 分析：「這份文件有哪些 trade-off / architectural choice？」
→ 建議要記的 lore，Rex 確認後 vein log

# 你有一個會議紀錄 Word 檔
vein import --from-file meeting_notes.docx
→ 同上流程，自動找出「決定了什麼」
```

**這個功能重要在哪：**
很多 decision 不是在寫 code 時產生的，而是在讀規格書、開會、看技術文章時產生的。
MarkItDown 讓 Vein 可以從這些「非程式碼來源」捕捉 lore。

**Phase 1+ 加入 `vein import` 子命令，依賴 MarkItDown。**

---

## 🟨 andrej-karpathy-skills (forrestchang) — CLAUDE.md 行為契約的業界標準

**它是什麼：** 把 Karpathy 對 AI coding 常見問題的洞見，轉成 CLAUDE.md 行為規範。
15K stars。核心四原則：Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven。

**跟 Vein 的關係：**
- Vein 的 `working_style.md` 和 `CLAUDE.md` 已經涵蓋了這四原則的精神
- 但「Goal-Driven Execution」這個原則值得更明確寫進 lore 品質標準

**可以抄的：Goal-Driven lore format**

lore 不只記錄「做了什麼」，要記錄「可驗證的目標 + 達成標準」：

```
❌ 弱 lore：
"選 sqlite-vec"

✅ 強 lore（Goal-Driven 格式）：
goal: 向量搜尋在 10K chunks 內 < 100ms，零 daemon
choice: sqlite-vec
verify: pytest test_recall_latency.py（< 100ms pass）
trade-off: > 100K chunks 時需 revisit
```

這個格式加進 `vein log` 的 polish prompt：讓 ollama 幫你把 raw message 補成這個結構。

**Vein 能幫 karpathy-skills 用戶：**
karpathy-skills 規範了 AI 的行為，但沒有記憶。
「為什麼這個專案要用 surgical changes 而不是 big refactor」這類 meta-decision 應該 `vein log`，下次換 Claude 接手仍然有效。

---

## 🟨 GStack (garrytan/gstack) — 角色化 prompt 的價值

**它是什麼：** 23 個 Claude Code 角色（CEO, QA, CSO, Designer...），讓 AI 從不同視角看問題。

**可以抄的：vein recall 加 `--role` 參數**

不同角色需要不同的 lore 組合：

```bash
vein recall "DualTree 效能" --role engineer
→ 找 D-015（technical trade-off）+ P-003（perf pitfall）

vein recall "DualTree 效能" --role qa
→ 找 P-003（known failure）+ P-007（edge case）+ 測試相關 lore

vein recall "sqlite-vec 選擇" --role architect
→ 找 D-002（選型原因）+ D-011（scale 考量）+ 相關 invariant
```

role 影響的是 lore 的排序權重和 digest 的敘述角度，不是過濾哪些 lore 看得到。

**Vein 能幫 GStack 用戶：**
GStack 的 `/qa` 跑測試前，先 `vein recall "known pitfalls" --role qa` 可以讓 QA agent 優先檢查歷史已知問題。
GStack 的 `/cso` 做安全審查前，`vein recall "security invariants"` 直接給 I-005/I-006 等不可違反規則。

---

## 🟨 design-md-chrome (Bergside) — 驗證 D-012 方向

**它是什麼：** Chrome extension，一鍵把網站的 design system 提取成 `DESIGN.md` 給 AI 讀。

**跟 Vein 的關係：**
這個工具捕捉「what the design looks like」，Vein 捕捉「why we chose this design」。
完全互補，不競爭。

**可以抄的：**
- 它的 Chrome extension 架構是 D-012 bookmarklet 升級版的參考
- 「zero privacy leak，純本地瀏覽器運算」這個 positioning 跟 Vein 一致，值得在 `docs_cloudflare/why.md` 用同樣的語氣說

**Vein 能幫 design-md-chrome 用戶：**
用戶用 design-md-chrome 捕捉了設計系統後，需要記錄「為什麼選這個設計系統而不是自己做」。
`vein log reference "為什麼 copy Vercel 的設計語言..." --source-url <url>` 補捉決策理由。

---

## 🟨 caveman (JuliusBrussee/caveman) — Vein 的 terse mode 靈感

**它是什麼：** 讓 AI 只輸出結果，不輸出廢話。原本 100 token 的回應壓成 20 token。

**可以抄的：`vein log --terse` 模式**

```bash
# 一般模式（ollama 幫你把 raw message 擴寫成完整 lore）
vein log decision "選 sqlite-vec"
→ ollama 補充背景、trade-off、revisit 條件
→ ~300 字的完整 lore entry

# terse 模式（只記關鍵，不讓 ollama 廢話）
vein log decision "選 sqlite-vec" --terse
→ 直接存原始訊息，最多加 tags
→ ~50 字，適合快速捕捉、事後再補
```

這跟 Vein working_style「terse > verbose」完全一致，應該在 Phase 1 就加。

---

## 🟩 jt-live-whisper — 未來的 meeting lore capture

**它是什麼：** 100% local AI 即時語音轉錄，支援 macOS Apple Silicon，有 speaker diarization。

**未來 Vein 整合方向：**

```bash
# Phase 4+ 功能
vein import --from-transcript meeting_2026-05-27.txt
→ ollama 找出「在這次會議中做了什麼決定」
→ 列出候選 lore entries，Rex 確認哪些要存
→ vein log 批量捕捉

# 更遠的未來
vein capture --from-audio meeting.m4a
→ 內部：whisper 轉錄 → 同上
```

**現在不做，但 schema 要預留：**
lore entry 的 `source` 欄位要支援 `meeting-transcript` type（D-012 已預留 source 欄位，OK）。

---

## 🟩 Google TimesFM — fubon_stock × Vein 的連接點

**它是什麼：** Google 開源的時序預測基礎模型（zero-shot forecasting）。

**跟 Vein 的關係：** 不影響 Vein 開發，但跟 D-013（fubon_stock audit trail）高度相關。

**如何串：**
```python
# TimesFM 預測「明日 2330 最高點」
prediction = timesfm_predict(ticker="2330", horizon=1)

# 決策時記錄 TimesFM 的 input + output 作為 lore
vein log decision \
  f"2330 進場依據包含 TimesFM 預測 {prediction.high} \
    (confidence: {prediction.conf}); 搭配 RSI={rsi}, 法人={inst_flow}"
```

TimesFM 的 prediction 本身不是 lore，但「為什麼相信這個 prediction、在什麼條件下忽略它」才是 Vein 要記的。

---

## 🟩 LangChain — Phase 3+ 的生態整合

**它是什麼：** AI 應用框架，提供 Memory、Agents、Retrievers、Chains。

**Vein 能提供 LangChain 生態一個 Retriever：**

```python
# 概念 code（Phase 3+）
from langchain.retrievers import BaseRetriever
from vein import VeinRetriever

retriever = VeinRetriever(
    project_path="/Users/lion/Documents/lode",
    budget_tokens=2000
)

# 在任何 LangChain chain 裡使用
chain = RetrievalQA.from_chain_type(
    llm=your_llm,
    retriever=retriever  # 底層呼叫 vein recall
)
```

`VeinRetriever` 讓 Vein 的 lore 可以插入任何 LangChain pipeline，不需要 vein serve。

---

## 🟩 Qdrant — fubon_stock 的 scale 備選

**它是什麼：** Rust 寫的現代向量 DB，API 友善，視覺化 Dashboard。

**跟 Vein 的關係：**
D-002 選了 sqlite-vec（single file, zero daemon），在 Vein 自身的規模（< 10K chunks）完全夠。
但 fubon_stock 的歷史行情 + 策略 lore 如果長到幾十萬條，Qdrant 是 upgrade path。

**現在不換，schema 要相容：**
lore entry 的格式（frontmatter YAML + markdown body）要設計成可以機械性 migrate 到 Qdrant，不需要人工轉換。

---

## 對 Vein Roadmap 的直接影響

根據以上分析，需要新增或修改的 decisions：

| Decision | 內容摘要 | 影響 Phase |
|---|---|---|
| D-015 | Rapid-MLX 作為 ollama 替代後端，config 抽象化 | Phase 1 |
| D-016 | MarkItDown 整合，新增 `vein import` 子命令 | Phase 2 |
| D-012 更新 | gbrain 是最近似競品，明確差異化定位 | Phase 0 docs |

---

## 最重要的一句話結論

從 13 個專案看下來，**Vein 的定位沒有被任何一個重疊取代**。
gbrain 最近似，但方向完全不同（raw notes vs curated decisions）。
Rapid-MLX 和 MarkItDown 是最值得直接整合的兩個，能讓 Vein 的核心功能更強。
