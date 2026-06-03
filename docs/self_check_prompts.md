# Self-check prompts — copy / paste 用

> 在任一專案的 **Cowork session**（工作資料夾選該專案）貼這些 prompt，
> 讓 Claude 從 vein 撈該專案的雷、對著 code 自我檢查。
> 流程細節見 [`self_check_playbook.md`](self_check_playbook.md)。

**前提：**
- vein MCP plugin 已裝（user-level，每個 Cowork session 自動可用 `vein_recall` / `vein_brief` / `vein_log`）。
- 該專案的 lore 已進中央 store（tag `project:<slug>`）。lore 薄就先 import / 邊做邊 `vein_log`。

---

## A. 通用版（把 `<PROJECT>` 跟關鍵字換掉）

**① 驗證接得到 vein**
```
先 call vein_status 跟 vein_brief()，確認這個 session 接到 vein 中央 store、
撈得到 project:<PROJECT> 的 lore。把結果摘要給我。
```

**② 自我檢查這次改動（最常用）**
```
照 vein/docs/self_check_playbook.md 對我這次的改動做 self-check：
1. vein_brief()
2. vein_recall 撈 project:<PROJECT> 的雷 + 通用 <STACK 關鍵字>
3. 對著 git diff 逐條比對有沒有重蹈，標 🔴違反 / 🟡風險 / ✅對齊，給 檔案:行 + 修法
4. 發現沒記過的新雷就 vein_log 寫回 project:<PROJECT>
```

**③ 改 code 前先學**
```
我要改 <功能/檔案>。先 vein_recall 相關的雷跟決策（project:<PROJECT> + <STACK>），
列成 checklist 再開始，避免重踩。
```

**④ 針對特定檔案**
```
讀 <檔案路徑>，對照 vein 裡 project:<PROJECT> + <STACK> 的 pitfalls，
逐條檢查這支有沒有命中，給 🔴/🟡/✅ 跟修法。
```

---

## B. 各專案填好版（直接複製）

### lode（macOS Tauri，TS + Rust）
```
照 vein/docs/self_check_playbook.md 對我這次的改動做 self-check：
vein_brief() → vein_recall 撈 project:lode 的雷 + 通用
"monaco react ref useEffect tauri ipc rust read_to_end mmap querySelector"
→ 對著 git diff 逐條比對，標 🔴/🟡/✅ 給 檔案:行 + 修法
→ 發現新雷就 vein_log 寫回 project:lode
```

### lode-iphone（Swift / iOS）
```
照 vein/docs/self_check_playbook.md 對我這次的改動做 self-check：
vein_brief() → vein_recall 撈 project:lode-iphone 的雷 + 通用
"swift autolayout memory cell reuse regex Info.plist validate.sh simulator"
→ 對著 git diff 逐條比對，標 🔴/🟡/✅ 給 檔案:行 + 修法
→ 發現新雷就 vein_log 寫回 project:lode-iphone
```

### sunnywalker（Python orchestrator + Swift app）
```
照 vein/docs/self_check_playbook.md 對我這次的改動做 self-check：
vein_brief() → vein_recall 撈 project:sunnywalker 的雷 + 通用
（Python 面 "python asyncio subprocess retry race"；Swift 面 "swift ios alarm background audio"）
→ 對著 git diff 逐條比對，標 🔴/🟡/✅ 給 檔案:行 + 修法
→ 發現新雷 / 新決策就 vein_log 寫回 project:sunnywalker
```

---

## C. 新增一個專案要做什麼

1. 在該專案 root 放一份最小 `CLAUDE.md`，含 §Vein self-check 區塊（參考 lode_iphone / SunnyWalker 的）。
2. 有 pitfalls/decisions doc → 用通用 importer 灌進去：
   ```bash
   cd /Users/lion/Documents/vein && python3 shell/import_project_lore.py \
     --project <slug> --type pitfall --heading "##" --file ~/Documents/<proj>/docs/<file>.md
   ```
3. 在 B 區照樣複製一段，把 `<PROJECT>` 換成 `<slug>`、stack 關鍵字換成該專案的。

---

## 小提醒

- recall 撈空：多半是該專案還沒 import lore，或用中文問英文 entry（參雜英文關鍵字）。
- 檢查品質 = 該專案 lore 厚度。每次自檢發現新雷就 `vein_log` 回去——越用越準（複利）。
- 最高品質是 Claude 在 session 內直接讀真 code；自動化 / CI gate 走 `vein walk` 的 `d_review.py`（需先把 recall 接進去）。
