# Vein × IC FW / EDA / SystemC — 使用場景

> **Focus：Vein 能做什麼**（不是 lode 或 AI 通用功能）

## 背景：IC FW 開發的知識流失問題

IC 公司的 FW 開發有一個結構性痛點：知識不在程式碼裡。

- **HAL interface 選擇**（為什麼這個 DMA API 長這樣）→ 沒有 doc，問離職工程師
- **SystemC model 假設**（timing 是 cycle-accurate 還是 TLM 估算）→ 在工程師腦子裡
- **Chaos engineering seed**（Seed 0x42A3 能重現 race condition）→ 在 Slack 訊息裡
- **Pre/post-silicon 行為差異**（SystemC 這樣跑，真實 ASIC 卻不這樣）→ 只有老手知道

Vein 的定位：把這些「**為什麼**」從腦子 / Slack / email 搬到 `.vein/`，讓任何 AI 工具、任何工程師都能在 30 秒內問到答案。

---

## Scene 1 — HAL 介面設計決策 capture

### 背景

FW 開發常用 HAL（Hardware Abstraction Layer）做雙目標編譯：
- `TARGET=HOST` → 在 Mac / Linux 的 SystemC 上跑
- `TARGET=MP` → 在真實 SoC 上跑

每個 HAL function 的 signature 都有 trade-off。

### 沒有 Vein 的情況

```
新工程師 or 新 AI session：
  "為什麼 hal_dma_submit() 要帶 completion_cb 而不是 poll-based？"
       │
       ▼
   grep HAL source × 5  →  找到 function declaration
   read hal_dma.h        →  只有 @brief，沒有 why
   問 slack               →  原始作者已離職
   猜                     →  改錯，引入 race condition
```

### 有 Vein 的情況

```
當初設計 HAL 時，工程師 capture 一次：

  vein log decision \
    "hal_dma_submit 用 callback 不用 polling：SystemC 端的 DMA 模型
     是 event-driven（sc_event），poll-based 在 HOST build 會空轉
     浪費模擬時間；MP build 中 IRQ handler 天然對應 callback 語義。
     poll-based 只有在 bare-metal debug 時才有用，那時 HAL 不適用。"

之後任何 AI / 工程師問：

  vein ask "hal_dma_submit 為什麼用 callback？"
  → 立刻得到完整 rationale，0 grep ✓
```

### ASCII 流程圖

```
         [HAL 設計討論]
               │
               ▼
         決定 API signature
               │
               ▼
   ┌─────────────────────────┐
   │  vein log decision      │  ← capture-time，工程師自己或 AI 協助記
   │  "為什麼 X 不是 Y"       │
   └────────────┬────────────┘
                │
                ▼
           .vein/decisions/
                │
    ┌───────────┴────────────┐
    │                        │
    ▼                        ▼
 新工程師               新 AI session
 vein ask "<why>"       vein brief → 看到 HAL key decisions
    │                        │
    ▼                        ▼
 直接回答，無需 grep     直接開始工作，無需定向 grep
```

---

## Scene 2 — SystemC ↔ 真實 ASIC 行為差異 lore

### 背景

QEMU + SystemC co-simulation 讓工程師在 pre-silicon 驗證 FW。但 SystemC model 永遠是近似值：

- timing 是估算（TLM，非 cycle-accurate）
- 某些 corner case（電源序列、NAND ECC retry timing）在 model 裡不存在
- PCIe 錯誤注入 model 跟真實 silicon 行為不同

這些差異是高價值 lore，但通常只在 post-silicon 驗證時才被「發現」，然後口耳相傳。

### Vein 的角色

```
Pre-silicon 階段 (SystemC)
       │
       │  FW 在 SystemC 上通過所有 test
       │
Post-silicon 階段 (真實 ASIC)
       │
       │  某個 scenario 行為不同
       │
       ▼
  原因分析 → 找到 SystemC model 的 timing 假設
       │
       ▼
  vein log pitfall \
    "SystemC DMA completion latency = 固定 100ns (model 限制)；
     真實 ASIC = 50~300ns depending on NAND state。
     FW 的 timeout 設定必須以真實 silicon 最壞情況為準，
     不能照 SystemC 數字 tune。
     已知受影響路徑: hal_dma_submit, gc_trigger_wait。
     Tag: pre-post-silicon-delta"
       │
       ▼
  .vein/pitfalls/

之後所有 AI session 做 DMA timeout tune 時：

  vein recall "DMA timeout"
  → P-xxx: SystemC latency ≠ real silicon，給出正確範圍
```

### ASCII — 知識跨越 pre/post-silicon 邊界

```
  PRE-SILICON                    POST-SILICON
  (SystemC 環境)                 (真實 ASIC)
        │                               │
        │   FW 開發 + debug             │  驗證差異
        │                               │
        ▼                               ▼
  vein log pitfall ←──── 差異 ────── 原因分析
  "SystemC X ≠ ASIC Y"
        │
        ▼
   .vein/pitfalls/
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
  下一個 pre-silicon 專案           新工程師 onboard
  vein recall "timing delta"        vein brief → 看到 pitfall
  → 提前知道哪些不能信 SystemC      → 不用再踩同一個雷
```

---

## Scene 3 — Chaos Engineering Seed 保存

### 背景

IC FW 的 chaos engineering：對 SystemC 注入隨機 latency + IRQ storm，找 race condition。
關鍵工具：`random.seed()` — 能重現問題的 seed 必須記錄，否則無法 debug。

```python
# typical chaos test
import random
seed = random.randint(0, 0xFFFFFFFF)
random.seed(seed)

for _ in range(N_ITERATIONS):
    inject_random_latency(hal_layer)
    inject_irq_storm(probability=0.3)
    run_fw_scenario()
```

### 沒有 Vein — 重現靠 Slack

```
    CI / 自動測試 → 發現 race condition
    seed = 0x42A3F1B7
         │
         ▼
    工程師 post 到 Slack: "seed 0x42A3... 能重現"
         │
         ▼
    1 個月後，Slack 訊息消失在歷史裡
         │
         ▼
    這個 race condition 修好了嗎？沒人確定。
```

### 有 Vein — Seed 進 lore，AI 能找

```
    CI 發現 race condition
         │
         ▼
  vein log pitfall \
    "DMA + GC concurrent race condition：
     seed=0x42A3F1B7 在 N=500 iteration 必重現。
     root cause: gc_trigger_wait 沒有 lock DMA completion flag。
     fix: commit abc1234。
     regression test: test_chaos_dma_gc.py::test_seed_42A3
     Tag: race-condition, chaos-seed, dma, gc"
         │
         ▼
   .vein/pitfalls/

任何時候：
  vein recall "DMA GC race"
  → 找到 seed + root cause + fix commit + regression test
  → 不需要翻 Slack / git log / Jira
```

### ASCII — Chaos Seed 生命週期

```
  Chaos 測試跑出問題
        │
        ▼
  記錄 seed + scenario
        │
        ▼
  vein log pitfall (含 seed, root cause, fix)
        │
        ▼
    .vein/pitfalls/
        │
        ├─── vein recall "race condition" ──► 找到 seed，立刻重現
        │
        ├─── vein recall "DMA pitfall"   ──► 看到所有 DMA 相關雷
        │
        └─── vein brief                  ──► 新 session 自動看到 active pitfalls
```

---

## Scene 4 — Doxygen XML → vein import（自動化 lore capture）

### 背景

FW 大型專案通常已有 Doxygen 文件。Doxygen XML 包含：
- `@pre` / `@post`（前置 / 後置條件，這就是 architectural invariant）
- `@note`（特殊行為備忘，這就是 lore）
- `@warning`（已知危險，這就是 pitfall）

### Vein D-017 的想法：parse Doxygen XML 作為 import source

```bash
# 從整個 HAL module 的 Doxygen XML 批量 import lore candidates
vein import --from-doxygen hal/doxygen/xml/hal__dma_8h.xml

# 內部流程：
# 1. parse @pre/@post/@note/@warning
# 2. ollama (qwen2.5-coder:7b) 判斷哪些是 lore-worthy
# 3. 列出候選，工程師確認後批量 vein log
```

### ASCII — Doxygen → .vein/ 流程

```
  現有 FW codebase
        │
        │  doxygen 指令
        ▼
  doxygen/xml/*.xml
        │
        │  vein import --from-doxygen
        ▼
  parse @pre @post @note @warning
        │
        │  ollama: "哪些是 decision/pitfall？"
        ▼
  候選 lore list (interactively 確認)
        │
        ▼
   .vein/decisions/
   .vein/pitfalls/
        │
        ▼
  vein ask "hal_dma_submit precondition？"
  → 立刻從 lore 回答，不需要 grep source
```

**價值**：存量 Doxygen 文件一次 import，瞬間讓 `.vein/` 有 lore 基礎，不需要從零開始 capture。

---

## Scene 5 — 00:00~07:00 自動化測試 → AI 分析 → Vein 記錄

### 背景

FW 開發晚間跑 overnight automated test pipeline：
1. 00:00：auto build + deploy to SystemC
2. 01:00~06:00：6 小時 chaos test + regression suite
3. 07:00：產出 test report

工程師 08:00 上班，30 分鐘內需要判斷：哪些失敗是 new bug，哪些是 known flaky test。

### Vein 的角色：讓 AI 看得懂 overnight 結果

```
  07:00 overnight report 產出
        │
        │  AI 分析腳本（Python）
        ▼
  gemini / claude 讀 report
        │
        │  搭配 vein recall "known flaky"
        ▼
  過濾已知問題 → 只 highlight 真正新問題
        │
        │  若發現新 bug：
        ▼
  vein log pitfall \
    "overnight 2026-05-27: test_nvme_io_qd32 fail
     seed=0x9A3C, latency_profile=heavy。
     suspected: QD=32 時 SQ doorbell overflow。
     需要 root cause。
     Tag: overnight, nvme, sq-doorbell"
        │
        ▼
  .vein/pitfalls/

  工程師 08:00 上班：
  vein brief → 看到新 pitfall，立刻知道今天要做什麼
```

### ASCII — Overnight Pipeline × Vein

```
  00:00                      07:00                   08:00
    │                           │                      │
    │  Auto build + test        │  Report 產出         │  工程師上班
    ▼                           ▼                      ▼
  SystemC                   AI 分析                vein brief
  chaos test            + vein recall               → 看到新 pitfall
  regression               "known issues"           → 知道今日重點
    │                           │
    │ 6 小時                    │ 過濾 known
    │                           ▼
    │                     真正新問題
    │                           │
    │                           ▼
    │                    vein log pitfall
    │                    (seed + scenario)
    │                           │
    └──────────────────────────►▼
                           .vein/pitfalls/
```

---

## Scene 6 — 新工程師 Onboarding：30 秒 vs 2 週

### 沒有 Vein 的 Onboarding

```
Day 1-3: 讀 FW spec（500 頁，部分過期）
Day 4-5: 問 mentor "為什麼 HAL 這樣設計？"
Day 6-7: 踩 SystemC 環境設 up 的雷
Day 8:   問 "為什麼 DMA callback 不能在 ISR context 呼叫？"
Day 9:   mentor: "喔，那是去年的 bug fix，要看 commit abc1234"
Day 10:  終於能開始工作
```

### 有 Vein 的 Onboarding

```
Day 1：
  vein brief
  → 看到：top 5 HAL decisions, active pitfalls, last week lore
  → 30 秒定向完成

  vein ask "為什麼 DMA callback 不能在 ISR context？"
  → 立刻從 lore 回答

  vein ask "SystemC 環境怎麼 setup？"
  → 找到 setup lore（踩過的坑都記著）

Day 2：可以開始有意義的工作
```

### ASCII 對比

```
  WITHOUT VEIN                    WITH VEIN
  ─────────────────────           ─────────────────────
  Day 1  Read 500-page spec       Day 1  vein brief (30s)
  Day 2  Ask mentor x10           Day 1  vein ask × N
  Day 3  Hit setup pitfalls       Day 1  vein ask "setup pitfalls"
  Day 4  Ask "why DMA..."         Day 2  Start real work
  ...
  Day 10 Start real work
```

---

## Scene 7 — ELF 靜態分析 + DES 模擬決策記錄

### 背景

IC FW 開發晚期會用靜態分析（pyelftools / angr）驗證 binary，以及 DES（Discrete Event Simulation）估算 FW performance 數字。這兩個工具的使用決策（為什麼選這個工具、為什麼這個參數）同樣需要 lore。

```bash
# 典型 ELF 分析 lore
vein log decision \
  "不用 angr symbolic execution 做全自動分析：
   FW binary 有 self-modifying code（OTA update path），
   angr 在這條路徑 exponential state explosion。
   改用 pyelftools 靜態 section analysis + 手動 angr 定點分析。
   Tag: elf-analysis, angr-limitation"

# DES 模型 lore
vein log decision \
  "DES latency model 用 log-normal distribution 而非 uniform：
   NAND read latency 實測資料符合 log-normal（長尾）。
   uniform model 低估 tail latency，導致 timeout 設定太短。
   Source: internal characterization report 2025-Q3.
   Tag: des-model, nand-latency, performance-estimation"
```

---

## 總結：Vein 在 IC FW 開發的核心價值

```
  FW 知識流失的四個洞
  ┌────────────────────────────────────────────────┐
  │                                                │
  │  1. HAL interface 設計 rationale               │
  │     → vein log decision at design time         │
  │                                                │
  │  2. SystemC ≠ 真實 ASIC 的 delta               │
  │     → vein log pitfall at post-silicon         │
  │                                                │
  │  3. Chaos seed + race condition 重現資訊        │
  │     → vein log pitfall (含 seed, fix commit)   │
  │                                                │
  │  4. 工程師離職時帶走的 know-how                  │
  │     → vein import --from-doxygen 搶救存量       │
  │                                                │
  └────────────────────────────────────────────────┘
                         │
                         ▼
                    .vein/ 專案記憶
                         │
           ┌─────────────┼────────────┐
           ▼             ▼            ▼
       vein brief    vein ask     vein recall
       30s 定向      點問題回答    語意搜尋
           │             │            │
           ▼             ▼            ▼
     任何 AI tool、任何工程師、任何 session
     都能在 30 秒內得到「為什麼」的答案
```

### Vein 具體指令對應表

| FW 開發場景 | Vein 指令 | 效果 |
|---|---|---|
| HAL 設計完成後 | `vein log decision` | 記錄 API 選擇的 trade-off |
| Chaos test 找到 race | `vein log pitfall`（含 seed） | 讓 bug 可重現、可搜尋 |
| Post-silicon 發現差異 | `vein log pitfall`（含 delta）| 跨 pre/post 知識傳承 |
| 新工程師 / 新 session | `vein brief` | 30 秒定向 |
| 問具體 why | `vein ask "..."` | 0 grep，直接回答 |
| 深入某個 domain | `vein recall "dma timing"` | 語意搜尋相關 lore |
| 搶救 Doxygen 存量 | `vein import --from-doxygen` | 批量 capture 既有文件 |
| overnight AI 分析後 | `vein log pitfall`（自動化）| pipeline 自動記錄新問題 |

---

*See also: D-017 (Doxygen import), D-018 (cross-environment lore), vein_use_cases.md*
