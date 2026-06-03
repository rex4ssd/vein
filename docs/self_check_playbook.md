# Self-check playbook — 用 vein lore 檢查專案自己的缺陷

> 給任一專案的 Cowork/Claude session 用（lode / lode_iphone / SunnyWalker / 任何接了 vein MCP 的專案）。
> 目標：寫/改 code 時，先從 vein 撈出「這個專案 + 這個 stack 走過的雷」，對著實際 code 檢查有沒有重蹈覆轍，發現新雷再寫回 vein。

---

## 前提

- vein MCP plugin 已裝（user-level，**所有 Cowork session 共用**）→ 每個專案的 session 都能 `vein_recall` / `vein_brief` / `vein_log`。
- lore 全在中央 store（`/Users/lion/Documents/vein/.vein/`），用 `project:<slug>` tag 區分：
  `project:lode` / `project:lode-iphone` / `project:sunnywalker`，外加跨專案的
  `swift` / `macos` / `coding-style` / `gui` 等。
- **檢查品質 = 該專案 lore 的厚度。** lore 薄就先長 lore（見 §4）。

---

## 流程（session 內跑）

**1. Orient**
`vein_brief()` — 拿這個專案近期決策 + active pitfalls。

**2. 撈相關的雷**
針對要改的東西 `vein_recall("<改動主題>")`，並補一發 stack 通用的：
- lode_iphone（Swift/iOS）→ `vein_recall("swift autolayout memory cell reuse")`
- lode（Tauri）→ `vein_recall("monaco react ref tauri")`
- 任何 → recall 後挑 `project:<slug>` + 同 stack tag 的 entry 當 checklist。

**3. 鎖定要檢查的 code**
- 預設：`git diff`（這次改了什麼）。
- 或指定檔案 / 模組。

**4. 逐條比對（核心）**
對每一條撈到的 pitfall，問：
> 「這段 diff/code 有沒有重蹈這條雷？」

輸出每個發現：`檔案:行` → 命中哪條 pitfall → 為什麼 → 怎麼改。
分三級：🔴 違反（會炸/已知雷）、🟡 風險（可能踩）、✅ 對齊。

**5. 把新雷寫回 vein（讓 lore 複利）**
檢查過程發現「沒被記過的新雷 / 新決策」→ 立刻：
`vein_log("pitfall", "症狀 + root cause + 修法", tags=["project:<slug>"])`
下次（含別的 LLM session）就查得到。

---

## 兩種執行方式

| 方式 | 誰 review | 品質 | 何時用 |
|---|---|---|---|
| **Session 內（建議）** | Claude 直接讀真 code + recall | 高（看得到實際 code） | 日常開發、改完馬上自檢 |
| **自動化（SunnyWalker walk）** | `shell/sunnywalker/d_review.py` 走 ollama | 中 | CI/排程 gate；需先把 recall 接進 d_review.py |

自動化版要把 `d_review.py` 改成：`git diff` + recall `project:<slug>` pitfalls → 丟給 ollama 問「違反哪條」。lore 夠厚再接才有料可查。

---

## 各專案現況（2026-06-03）

| 專案 | stack | lore 覆蓋 | 自檢可用度 |
|---|---|---|---|
| lode | Tauri (TS+Rust) | 63 pitfalls (project:lode) | ✅ 強，現在就能自檢 |
| lode_iphone | Swift/iOS | 4 真雷 + 10 條通用 Swift/macOS | 🟡 可檢通用面，iOS 專屬雷待長 |
| SunnyWalker | Python orchestrator (+Swift) | 幾乎無專屬 lore | 🔴 先長 lore 再自檢 |

---

## 長 lore 的工具

```bash
# 把專案的 pitfalls/decisions doc 匯進 vein（通用，任何專案）
python3 shell/import_project_lore.py --project <slug> --type pitfall \
    --heading "##" --file ~/Documents/<proj>/docs/PITFALLS.md

# 日常開發中即時記（session 內）
vein_log("pitfall", "...", tags=["project:<slug>"])
```

每次自檢發現新缺陷就 `vein_log` 回去——lore 越用越厚，自檢越來越準。這就是複利。
```
