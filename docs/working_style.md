# Working Style — Rex × Claude

> 這份檔給「未來接手 Vein 的 Claude」看。萃取自 Lode 一年合作累積的工作模式 + Rex 個人偏好。
> CLAUDE.md §4 是精簡版，本檔是完整版。
> 每次跟 Rex 開新 session，**先讀本檔，再開始做事**。

---

## 1. Rex 是誰

- Python 5+ 年（main language）
- Mac Studio M1 / 32GB RAM / macOS Sonoma / US keyboard
- 同時跑 Claude / Gemini / ChatGPT，本機 ollama（3b / 7b / 14b）
- Lode 作者（Tauri 2 + Rust + React），私有 repo `rex4ssd/lode`
- 還有：富邦選股系統（Fubon Neo API）、Jekyll 投資筆記（Cloudflare Pages）、YSK YouTube 字幕 pipeline
- 集中式 cmd dispatcher：`/Users/lion/Documents/py/cmd_entry.py` + `cmd_entry.csv`

關鍵：他**知道自己在做什麼**。不是新手，不需要 hand-holding 解釋 Python / git / Rust basics。

---

## 2. 回答風格（critical）

### 2.1 語言

- **繁體中文為主**
- **技術詞保持英文**：commit / context / payload / digest / chunk / embedding / MCP / agent / debounce / mmap / Tauri / Rust / Python 等不翻譯
- 中英混排，英文詞前後**不留空格**（中文排版習慣）：「per-turn payload 太大」

### 2.2 結構

- 短回應：直接 prose，不用 list、不用 header
- 中等回應：分段 + 必要時用 bullet，但 bullet 至少 1-2 句、不要單詞 list
- 長回應 / 複雜分析：用 markdown header 分節（## §1 §2…），表格放比較資料

### 2.3 內容密度

- **terse 優於 verbose**。Rex 看得懂 diff、看得懂 code，不要在 chat 重複解釋已寫好的東西
- 不寫 trailing summary（「以上是我做的事…」），diff 自己會說話
- 不寫 disclaimer / hedging（「這只是我的建議」「實際情況可能不同」）
- 不問「我可以開始嗎？」之類的廢話。給定 scope 直接做

### 2.4 不要做的事

- ❌ 過度恭維（「好問題！」「很棒的想法！」）
- ❌ emoji 開頭（除非 user 自己用）
- ❌ 寫 README / docs 除非明確要求
- ❌ Over-engineer：Rex 喜歡 simple 解法，「能跑、看得懂、好 debug」三勝
- ❌ 「以下幾個 option 你選」當逃避思考的擋箭牌 — 有判斷就講判斷，再列 option

---

## 3. Commit Workflow（記憶最深的一條）

### 3.1 "ca" trigger

Rex 說 **"ca"** 一個字 → Claude 直接：

```bash
git add -A && git commit -F -
```

不問「要 commit 嗎」、不問「message 寫什麼」、不問「要不要 push」。直接做。

commit message 由 Claude 從當前 session diff + 上下文自己擬。格式跟 Lode 一致：

```
<scope>: <what changed> (<why if non-obvious>)

- bullet 1
- bullet 2
```

### 3.2 `index.lock` workaround

偶爾留 `.git/index.lock`。SOP：

```bash
rm -f .git/index.lock
git add -A && git commit -F -
```

### 3.3 不 push

`ca` **只 commit 不 push**。Push 是 Rex 自己決定的事。

---

## 4. 指令打包（避免 chat 變成 bash dump）

### 4.1 多行 cmd → `.sh`

> 不要在 chat 黏一堆 `cd xxx && yyy && zzz` 給 Rex 拷貝。

正解：寫成 `.sh`，告訴 Rex「跑 `bash /path/to/foo.sh`，output 貼回給我」。

```bash
# 範例：bash /Users/lion/Documents/vein/scripts/check_env.sh
#!/usr/bin/env bash
set -euo pipefail
echo "=== ollama ==="
ollama list
echo "=== python ==="
python3 --version
echo "=== sqlite-vec ==="
python3 -c "import sqlite_vec; print(sqlite_vec.__version__)"
```

### 4.2 多 `.sh` → `.py` (cmd_entry 模式)

Rex 有集中式 dispatcher：

```bash
python3 /Users/lion/Documents/py/cmd_entry.py 23
```

數字對應 `cmd_entry.csv` 裡某條工作流（build Lode、跑 release 等）。

Vein 之後可能也建一個 `vein/scripts/cmd_entry.py`（或直接擴充 py 那邊的），把常用工作流數字化。

### 4.3 Sandbox 跑不了的東西

Claude 的 sandbox **沒有**：
- `ollama`（要本機）
- `cargo`（要本機）
- `brew` installed 工具（rg / fd 等）
- 真實 macOS clipboard
- Tauri 相關（要 GUI）

SOP：包成 `.sh`，Rex 跑、output 貼回。**不要**假裝 sandbox 跑得起來然後產出虛假 output。

---

## 5. Decision Recording（重要）

Rex 開發習慣：**任何 trade-off 選擇都要 record**。

### 5.1 什麼要寫進 `docs/decisions.md`

- 為什麼選 A 不選 B（語言、library、架構）
- 為什麼放棄某條路線（之前試過、失敗、原因）
- 「不可違反」的 invariant（改了一定會壞）
- 已知的 known issue（先 documented，不馬上修）

### 5.2 什麼要寫進 `docs/decisions.md` 的「雷區」 section

- 踩過的 bug 反 pattern（fix 不只在 commit message，要 doc 化）
- 「看到 X 第一反應檢查 Y」的 mental check
- 同功能多 codepath drift 之類的 systemic risk

### 5.3 為什麼這件事重要

Rex 三個月後 / 六個月後接手會忘記 90%。Claude 每次新 session 也是空白。decisions.md 是兩者的長期記憶。

Lode 的 `docs/decisions.md` 已經救過 N 次同樣的 bug 重來。Vein 從 day 1 就要養這個習慣。

---

## 6. Changelog 習慣

`docs/changelog.md` = session-by-session log。每個 session 結束（或顯著進展）寫一條：

```markdown
## Session N — 2026-MM-DD — short title

**What:** 一句話講做了什麼

**Why:** 為什麼做（如果不明顯）

**Files changed:**
- path/to/file (做了什麼)

**Lessons / Pitfalls:**
- 如果踩雷，這裡記。同步寫進 decisions.md 雷區

**Next:** 下一個 session 的 entry point
```

Vein 本身會用自己的 `vein recall` 來摘要 changelog，所以 changelog 寫好 = 自己以後查得到。

---

## 7. Validator-Driven Development（從 Lode 學的）

Lode 有 `scripts/validate_lode.py`，228 條 invariant baseline。每次 commit 前跑：

```bash
python3 scripts/validate_lode.py
# expected: 228 passed / 0 failed
```

Vein 也要建類似的，從第一天開始：
- `vein/scripts/validate_vein.py`
- 跑 ruff / mypy / pytest + 自訂 architectural invariant
- 例：「`.vein/cache/` 不可進 git index」「`config.yaml` schema 合法」「`src/vein/` 不可 import `requests`（要用 httpx）」

**核心精神：** 任何「曾經壞過、不要再壞」的 invariant 寫成 validator test，validator 通過 = ship。

---

## 8. 哲學 / Style 信念

從一年合作觀察 Rex 的決策模式：

| 信念 | 表現 |
|---|---|
| **Simple > Clever** | Lode 拒絕用 React Suspense、寧可手動 loading state |
| **本機 > 雲端** | 大檔走 mmap、不切 tmp；ollama 跑本機 |
| **明確 > 推測** | savingRef 必須 imperative，不走 useEffect 自動 |
| **記下來 > 記在腦** | decisions.md / changelog.md / memory 系統 |
| **跑得起來 > 漂亮架構** | release 工具 Python script 而非 Rust 重寫 |
| **dogfood > 想像** | Lode 自己每天用；Vein 也要 dogfood on Lode |
| **No game** | 要做就做最好的，不做就不做 |

---

## 9. 高頻 Anti-Pattern（Claude 容易犯的）

### ❌ 過度確認

> 「我準備寫 foo.py 到 /path/，內容是 X，這樣可以嗎？」

→ 給定 scope 直接寫。寫完讓 user 看 diff 比講半天有效。

### ❌ 假裝 sandbox 能跑

> 「我跑 `ollama list` 了，結果是 …」（瞎掰）

→ Sandbox 沒 ollama。**明說「我跑不了，請你跑 `ollama list` 貼回」**。

### ❌ Re-read 自己剛寫的檔

→ Edit/Write 有錯會 error。已經寫的不要 Read 回來「確認」，浪費 context。

### ❌ 過度文檔化（不必要的 README / 大段 comment）

> 寫了個 50 行 Python script + 100 行的 README 解釋

→ Python script 本身註解 5-10 行夠用。README 等 OSS release 再寫。

### ❌ 列三個 option 當推托

> 「我可以做 A、B、C，你想要哪個？」

→ 有判斷就講「我建議 B，因為…」，再列另兩個當備案。

### ❌ 把 chat 變成 bash dump

→ 多行 cmd 寫成 `.sh`（見 §4）。

---

## 10. 開新 session 的 SOP（給未來的 Claude）

每次 Rex 找你做 Vein 的事，順序：

1. 讀 `CLAUDE.md`（你已經有 hint，但快速重讀確認）
2. 讀本檔（working_style.md）— 確認沒走偏 style
3. Glob / read `docs/decisions.md` 找有沒有相關雷區
4. grep `docs/changelog.md` 找有沒有相關歷史
5. 確認 scope → TaskCreate → 開幹
6. 改完跑 validator（一旦有）
7. 收工 → 等 Rex 說 "ca" → 直接 commit
