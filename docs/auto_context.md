# Automated Context Passing — 設計文件

> 未來不是精通「如何下超長 Prompt」，而是精通「自動化上下文傳遞」。  
> 把 AI 當成函數節點，讓程式碼、錯誤日誌自動在 API 之間流動。

---

## 問題定義：手動 copy-paste 循環

現在開發中最浪費時間的 pattern：

```
┌─────────────────────────────────────────────────────────────┐
│  1. 執行指令 → FAIL                                          │
│  2. 手動 copy error message                                  │
│  3. 切換到 Claude / Gemini tab                               │
│  4. paste error                                             │
│  5. 等 AI 回應，copy fix command                             │
│  6. 切回 terminal，paste                                     │
│  7. → FAIL again，repeat                                    │
│                                                             │
│  每個循環：30-90 秒，一天 10-20 次 = 5-30 分鐘純 overhead   │
└─────────────────────────────────────────────────────────────┘
```

更深層的問題：
1. **Context 斷裂**：AI 每次拿到的都是孤立的 error snippet，沒有「這個專案的特殊背景」
2. **重複解同一個問題**：同一個 pitfall 在 3 個月後又找 AI 問一次
3. **Knowledge 流失**：fix 成功後沒有記錄，下個人（或三個月後的自己）再踩雷

---

## Vein 的解法：讓 context 自動流動

```
                        ┌─────────────────────────┐
                        │    開發者的大腦           │
                        │   （只做架構決策）        │
                        └────────┬────────────────┘
                                 │ 決策 / 確認
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
    capture                   route                  consume
         │                       │                       │
┌────────▼──────────┐  ┌────────▼──────────┐  ┌────────▼──────────┐
│  vein log / pipe  │  │   vein ask/recall  │  │   vein brief      │
│  捕捉知識到 .vein/ │  │   搜尋已知解法    │  │   注入 AI session │
└────────┬──────────┘  └────────┬──────────┘  └────────┬──────────┘
         │                       │                       │
         └───────────────────────┴───────────────────────┘
                                 │
                        .vein/ (project lore DB)
                        decisions/ lore/ pitfalls/ references/
                        index/ (FTS5 + embedding)
```

---

## 三個層次的自動化

### 層次 1：現在就能用（Phase 0 — 已實作）

**`vein pipe`** — 把 shell 輸出接到 vein，不需要手動 copy

```bash
# BEFORE: 手動 copy error → 貼到 Claude
cargo check 2>&1    # fail，手動 copy...

# AFTER: pipe 直接 triage
cargo check 2>&1 | vein pipe           # 搜尋 .vein/ 已知解法
cargo check 2>&1 | vein pipe --ai      # 搜不到時再問本機 AI
cargo check 2>&1 | vein pipe --ai --log  # 同時記錄這筆 pitfall
```

**`vein run`** — 更完整的 wrapper，run + fail + triage 一條龍

```bash
vein run cargo check
vein run pytest tests/ --ai
vein run "make build" --ai --log
```

**內部流程：**

```
指令失敗
  │
  ▼ extract_error_terms()   ← 從 noisy log 提取關鍵 signal
  │ (過濾 Compiling/warning 等 noise，留 Error/FAILED/note)
  │
  ▼ store.grep_entries(error_digest)   ← 先查 .vein/
  │
  ├─ 命中 ──▶ 顯示 pitfall entry（含 Fix section）   ← 不需 AI
  │
  └─ 未命中 ──▶ [--ai] call_ollama_triage()
                  │  input: cmd + error + lore context
                  │  model: qwen2.5-coder:7b (local)
                  ▼
                  顯示 Root cause / Fix / Why
                  [--log] 自動存為 pitfall entry（待填 root cause）
```

### 層次 2：Shell Hook（install 後自動啟用）

在 `~/.zshrc` 加入 hook，讓任何指令 fail 都能一鍵 triage：

```zsh
# ~/.zshrc — vein shell integration

_VEIN_LAST_CMD=""
_VEIN_LAST_CODE=0

# 每次 prompt 出現前記錄上一條指令 + exit code
_vein_precmd() {
    _VEIN_LAST_CODE=$?
    _VEIN_LAST_CMD=$(fc -ln -1 2>/dev/null || true)
}
add-zsh-hook precmd _vein_precmd

# vt = vein triage：對上一條失敗的指令呼叫 vein pipe --ai
vt() {
    if [[ $_VEIN_LAST_CODE -eq 0 ]]; then
        echo "Last command succeeded (exit 0). Nothing to triage."
        return 0
    fi
    echo "[vein] Triaging: $_VEIN_LAST_CMD (exit $_VEIN_LAST_CODE)"
    eval "$_VEIN_LAST_CMD" 2>&1 | vein pipe --cmd "$_VEIN_LAST_CMD" "${@}"
}

# vr = vein run shorthand
alias vr='vein run'

# vp = vein pipe shorthand
alias vp='vein pipe'
```

**使用流程：**

```bash
cargo check     # 失敗，exit 1
vt              # 重跑 + pipe 給 vein，等同 cargo check 2>&1 | vein pipe
vt --ai         # 找不到答案時再問 AI
vt --ai --log   # 問完 + 記錄
```

### 層次 3：MCP + API 流水線（Phase 0.3）

當 vein 有 MCP server 後，AI client 可以直接：

```
Claude Code / Cursor
  │
  ├── mcp:vein:recall("DMA timeout")       ← AI 自己查 vein
  ├── mcp:vein:brief()                     ← AI 自己讀 project brief
  └── mcp:vein:log(type, title, body)      ← AI 自己記錄決策
```

不再需要人工把 vein brief 貼到 chat，AI 工具會自動注入 context。

---

## AI 當作函數節點

核心思維轉變：

```
舊思維：  使用者 ──── prompt ──── AI ──── answer ──── 使用者
新思維：  程式碼 → 錯誤 → vein(搜尋) → 命中? → done
                                    → 未命中 → ollama(triage) → fix
                                                              → vein.log(pitfall)
                                                              → 下次命中
```

AI 在這個架構裡是：
- `qwen2.5-coder:7b` = 本機 error triage 函數（输入: cmd+error, 输出: fix）
- `nomic-embed-text` = 語意搜尋 embedding 函數（输入: text, 输出: vector）
- `llama3.2:3b` = brief 壓縮函數（未來，输入: entries, 输出: digest）
- `deepseek-r1:14b` = 深度分析函數（未來，recall 綜合）
- Claude / Gemini = 最終架構決策（你只在 AI 答不了或需要 trade-off 時介入）

---

## Vein 處理的 context 流動表

| 流動方向 | 工具 | 說明 |
|----------|------|------|
| terminal error → vein | `vein pipe` / `vein run` | 錯誤自動被搜尋 + triage |
| vein → new AI session | `vein brief` | 開 session 時注入 ≤2K context |
| existing docs → vein | `vein import` | 歷史決策批量吸收 |
| AI session → vein | `vein log` | 新決策即時記錄 |
| vein → AI search | `vein recall` | 語意搜尋，AI 得到 rich context |
| vein → Lode MCP | (Phase 0.3) | code diff → vein lore 雙向 |

---

## 實際使用場景

### 場景 A：Rust cargo 踩雷（現在就能用）

```bash
# 傳統（手動 copy-paste 循環，~60 秒）
cargo build        # E0308: mismatched types
# copy error → 貼到 Claude → copy fix → 貼回 terminal

# Vein 方式（~5 秒）
vein run cargo build --ai
# vein 搜 .vein/ pitfalls → 命中？顯示 fix
#                         → 未命中 → qwen2.5 triage → show fix → --log 記錄
```

### 場景 B：pytest 失敗（現在就能用）

```bash
pytest tests/ 2>&1 | vein pipe --ai
# 若是已知 pattern（e.g., "multiple values for keyword argument"）→ 直接顯示
# 若是新錯誤 → AI triage → 記錄為 pitfall
```

### 場景 C：新 AI session 快速上手（現在就能用）

```bash
# 開 Claude Code / 打開新 chat
vein brief        # 印出 ≤2K context
# copy 給 AI，說 "read this brief, then..."
# → AI 立刻知道這個 project 的 phase、focus、active pitfalls
```

### 場景 D：深夜 pipeline fail，早上 triage（現在就能用）

```bash
# 昨晚跑的 batch 失敗了
cat /path/to/build.log | vein pipe --ai-always
# AI + vein 自動分析，不用你 manually 讀 5000 行 log
```

---

## 實作狀態

| 功能 | 狀態 | 指令 |
|------|------|------|
| error term extraction | ✅ Phase 0 | `vein/core/triage.py` |
| vein lore search | ✅ Phase 0 | `vein ask` / `vein recall` |
| pipe triage | ✅ Phase 0 | `vein pipe` |
| run wrapper | ✅ Phase 0 | `vein run` |
| shell hook (zsh) | ✅ snippet | 見本文 §層次 2 |
| project brief inject | ✅ Phase 0 | `vein brief` |
| MCP server | 🔲 Phase 0.3 | `vein mcp serve` |
| auto-capture on log | 🔲 Phase 0.3 | Claude MCP tool |
| multi-AI routing | 🔲 Phase 1 | `config/ai_providers.yaml` |
