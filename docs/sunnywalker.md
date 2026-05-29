# Sunnywalker — Multi-Agent Workflow System

> AI A codes → AI B validates → AI C reports → AI D reviews → loop until ship

---

## 概念

傳統開發循環的問題：每個步驟是孤立的，context 靠人工傳遞，AI 每次都從零開始。

Sunnywalker 的解法：把開發週期定義成 **可自動執行的步驟**，每一步的 input/output 都寫進 `.vein/`，下一步直接從 vein 讀上一步的 context。

```
你（架構決策）
  │
  ▼
sunnywalker.yaml  ← 定義步驟 + 路由規則

vein walk run
  │
  ├─▶ A: code        (human/AI coding step — 你或 AI 做)
  │       │ done ──▶ B
  │       │ fail ──▶ stop
  │
  ├─▶ B: validate    (自動跑 tests + lint，結果 pipe 給 vein)
  │       │ pass ──▶ C
  │       │ fail ──▶ A   (自動 goto code，附 error context)
  │
  ├─▶ C: report      (自動從 vein 生成本週 lore summary)
  │       │ pass ──▶ D
  │       │ fail ──▶ skip (non-critical)
  │
  └─▶ D: review      (AI 讀所有 vein entries → PASS / FAIL)
          │ PASS ──▶ E: git commit → done ✓
          │ FAIL ──▶ A   (帶 review 意見回到 coding)
```

---

## 快速開始

```bash
cd /path/to/your/project

# 1. 初始化 .vein/ 和 sunnywalker.yaml
vein init
vein walk init

# 2. 依你的 tech stack 選 template
vein walk init --template python    # pytest + ruff
vein walk init --template rust      # cargo check + cargo test
vein walk init --template tauri     # tsc + cargo check

# 3. 編輯 sunnywalker.yaml 和 b_validate.sh
# 4. 開始跑
vein walk run
```

---

## 命令一覽

```bash
vein walk init              — 產生 sunnywalker.yaml + 4 個 template scripts
vein walk run               — 跑（或繼續）workflow
vein walk run --dry-run     — 預覽每步驟，不實際執行
vein walk run --from-step validate  — 從特定 step 跳過 code 繼續
vein walk status            — 看目前 step + 歷史
vein walk step code pass    — 手動把 code step 標為 pass（人工完成）
vein walk reset             — 清除狀態，重新開始
```

---

## sunnywalker.yaml 格式

```yaml
name: my-feature
version: 1

steps:
  - id: code             # 唯一 step id
    name: "AI Coding"    # 顯示名稱
    human_step: true     # true = 暫停等人工/AI 完成
    on_pass: next        # pass 後去下一步
    on_fail: stop

  - id: validate
    name: "Validation"
    run: shell/sunnywalker/b_validate.sh   # 要執行的 script
    on_pass: next
    on_fail: "goto:code"   # fail → 回 code step
    max_retries: 3         # 最多 retry 3 次才放棄

  - id: report
    name: "Write Report"
    run: shell/sunnywalker/c_report.py
    on_pass: next
    on_fail: skip          # 失敗就跳過，不阻擋

  - id: review
    name: "AI Review"
    run: shell/sunnywalker/d_review.py
    on_pass: done          # pass = 整個 workflow done
    on_fail: "goto:code"   # fail → 重新 coding

  - id: commit
    name: "Git Commit"
    run: shell/sunnywalker/e_ca.sh
    on_pass: done
    on_fail: stop
```

### on_fail 指令

| 值 | 行為 |
|----|------|
| `stop` | 停止 workflow，等人介入 |
| `skip` | 跳過此 step，繼續下一步 |
| `retry:3` | 最多 retry 3 次，超過就 stop |
| `goto:code` | 跳到 id=code 的 step |
| `ai_decide` | 讓 ollama 決定跳去哪個 step |

---

## 四個 Template Scripts

### `b_validate.sh` — 驗證

```bash
# 自動跑 tests，失敗 exit 1 → workflow 回到 code step
pytest tests/ -q || exit 1
ruff check src/ || exit 1
```

修改這個檔案讓它符合你的專案：
- Python：`pytest tests/ -q`
- Rust：`cd src-tauri && cargo check && cargo test`
- Tauri：`npx tsc --noEmit && cd src-tauri && cargo check`
- JS/TS：`npm test`

### `c_report.py` — 生成報告

自動從 `.vein/` 讀取本週 entries，生成 `WALKER_REPORT.md`。同時把報告 summary 存進 vein 作為 lore entry，下次 AI reviewer 可以讀到。

輸出範例：
```markdown
# Sunnywalker Report — 2026-05-29 14:30
Total entries: 15  |  This week: 8

## Decisions (3)
- Use WAL mode to avoid SQLite write locks — 2026-05-28
- ...

## Pitfalls (2)
- HAL timer not re-entrant — 2026-05-27
- ...
```

### `d_review.py` — AI Reviewer

讀取近 7 天的所有 vein entries，送給 `deepseek-r1:14b`（或 config 裡的 `analyze_model`），請 AI 給出：

```
VERDICT: PASS
REASON: All critical pitfalls have known fixes documented
RISK: none
```

或：

```
VERDICT: FAIL
REASON: DMA callback re-entrancy issue unresolved
RISK: Production deadlock under heavy load
GOTO: validate
```

exit 0 = PASS → workflow 繼續  
exit 1 = FAIL → workflow 按 `on_fail` 路由（通常回 code）

### `e_ca.sh` — Git Commit

```bash
git add -A
git commit -m "feat: sunnywalker cycle ${VEIN_WALKER_CYCLE} — 2026-05-29"
```

---

## 狀態持久化

Workflow 狀態存在 `.vein/WALKER.json`（gitignored）：

```json
{
  "workflow_name": "my-feature",
  "cycle": 3,
  "current_step_id": "validate",
  "status": "running",
  "history": [
    {"step_id": "code",     "status": "pass", "ts": "2026-05-29T10:00:00Z"},
    {"step_id": "validate", "status": "fail", "ts": "2026-05-29T10:05:00Z", "exit_code": 1},
    {"step_id": "code",     "status": "pass", "ts": "2026-05-29T11:00:00Z"},
    {"step_id": "validate", "status": "pass", "ts": "2026-05-29T11:10:00Z"}
  ]
}
```

中途 ctrl-C 或 crash 都可以 `vein walk run` 繼續。

---

## 真實場景：一週開發 feature

```
Day 1
  vein walk run
  → [A] code: 你/AI coding（press Enter when done）
  → [B] validate: pytest fails（3 tests）
  → ↩ goto code
  → [A] code: fix tests
  → [B] validate: pass ✓
  → [C] report: WALKER_REPORT.md written
  → [D] review: FAIL — 缺 pitfall 記錄
  → ↩ goto code
  → [A] code: vein log p "timer callback re-entrancy"
  → [B] validate: pass ✓
  → [C] report: updated
  → [D] review: PASS ✓
  → [E] commit: feat: sunnywalker cycle 3

Day 2-5: repeat
Day 7: vein walk status → all cycles passed, app done
```

---

## 與 vein pipe / vein run 整合

```bash
# b_validate.sh 裡可以直接用 vein pipe
pytest tests/ -q 2>&1 | vein pipe --ai --log || exit 1
# fail 時：自動 triage + 記錄為 pitfall → d_review 能讀到 → 下次 review 知道哪裡有問題
```

---

## 環境變數（script 裡可用）

| 變數 | 值 | 說明 |
|------|-----|------|
| `VEIN_WALKER_STEP` | `validate` | 當前 step id |
| `VEIN_WALKER_CYCLE` | `3` | 當前是第幾個循環 |
| `VEIN_PROJECT_ROOT` | `/path/to/project` | 專案根目錄 |
| `VEIN_BATCH` | `1` | 表示在 batch/walker 模式下 |
