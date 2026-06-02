# VS Code GUI 行為規格 vs Lode 對照

> Source: microsoft/vscode main branch（2026-06）
> 目的：Lode 學習 / 驗證用，標記 ✅ 已實作 / ⚠️ 部分 / ❌ 缺漏 / 📝 待評估

---

## 1. File Explorer 操作

### 1.1 新增檔案 / 資料夾

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 觸發新增檔案 | Toolbar 圖示 click 或右鍵選單 → "New File..." | ❌ |
| 觸發新增資料夾 | Toolbar 圖示 click 或右鍵選單 → "New Folder..." | ❌ |
| 輸入方式 | **Inline input** — 在 tree 節點旁直接展開 text field | ❌ |
| 輸入位置 | 新增後 focus 在父資料夾內的新節點 | ❌ |
| 確認 | Enter → 建立並在 editor 開啟（檔案）/ 展開（資料夾） | ❌ |
| 取消 | Escape → discard，tree 回到原始狀態 | ❌ |
| 空白名稱 | 不允許，input 維持 focus | ❌ |
| 重複名稱 | inline error message，input 維持 focus | ❌ |
| 路徑輸入 | 可輸入 `a/b/c.ts` 一次建立多層目錄 | 📝 |

### 1.2 Rename（重命名）

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 觸發 | **F2** 或右鍵 → "Rename..." | ⚠️ |
| 輸入方式 | Inline input，預填現有名稱，全選 | ❌ |
| 副檔名保留 | 全選但游標在副檔名前；按 Tab 跳到副檔名後 | 📝 |
| 確認 | Enter → 重命名，editor tab label 同步更新 | ❌ |
| 取消 | Escape → 維持原名 | ⚠️ |
| 衝突 | 若目標名稱已存在：提示是否 overwrite | ❌ |
| 影響 open editors | Tab 顯示新名稱；若有 import reference 不自動更新（TS 由 tsserver 另處理） | 📝 |

### 1.3 刪除

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 觸發 | **Delete / Backspace** 或右鍵 → "Delete..." | ⚠️ |
| 確認 dialog | "Are you sure you want to delete X?" + Move to Trash / Delete Permanently 按鈕 | ❌ |
| Undo 設定 | `explorer.confirmUndo` = `default/verbose/light` 控制確認粒度 | 📝 |
| 刪除開啟中的檔案 | Tab 顯示 file-deleted 狀態（title 變暗），不強制關閉 | ❌ |
| Multi-select 刪除 | 同時刪多檔，confirm dialog 顯示數量 | ❌ |
| 資料夾刪除 | 遞迴刪除；警告顯示子項目數量 | ❌ |

### 1.4 選取 / 多選

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 單選 | Click | ✅ |
| 連續多選 | Shift + Click | ⚠️ |
| 不連續多選 | Ctrl/Cmd + Click | ⚠️ |
| 全選（同層） | Ctrl+A | ❌ |
| 鍵盤導覽 | ↑↓ 移動；→ 展開資料夾；← 收合 / 跳到父層 | ⚠️ |

### 1.5 Drag & Drop

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 拖移到資料夾 | Move（預設） | 📝 |
| Ctrl + 拖移 | Copy | 📝 |
| 拖移時視覺回饋 | 目標資料夾 highlight + drop indicator line | 📝 |
| 拖出視窗 | 在 Finder/Explorer 產生實際檔案 | 📝 |
| 拖入視窗 | 從 Finder 拖入 → 複製到資料夾 | 📝 |

---

## 2. Search 行為

### 2.1 搜尋輸入與觸發

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 開啟 search panel | Ctrl+Shift+F | ✅ |
| 搜尋方式 | `search.searchOnType: true`（預設）— 每次 keystroke 觸發 | ⚠️ |
| 停用 searchOnType | Toggle 按鈕或設定 → 改為 Enter 觸發 | ❌ |
| 清除搜尋 | X 按鈕或 Ctrl+A + Delete | ✅ |

### 2.2 搜尋選項 toggles

| 行為 | VS Code 規格（快捷鍵） | Lode 狀態 |
|------|----------------------|-----------|
| Case Sensitive | Alt+C（macOS: ⌥C） | ⚠️ |
| Whole Word | Alt+W | ❌ |
| Regex | Alt+R | ⚠️ |
| Preserve Case（replace 用） | Alt+P | ❌ |
| Toggle Query Details（include/exclude） | Ctrl+Shift+J | ❌ |

### 2.3 結果顯示

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 結果分組 | **File node** → **Match lines**（兩層樹）| ✅ |
| File node 顯示 | 路徑 + 右側 match count badge | ⚠️ |
| Match line 顯示 | 行號 + context + **highlight** match 字串 | ✅ |
| 展開 / 收合 | File node 可 click 收合 | ⚠️ |
| 空結果 | "No results found." 提示 | ✅ |
| 搜尋中 | loading spinner | ⚠️ |
| 結果計數 | panel title 顯示 "X results in Y files" | ❌ |

### 2.4 鍵盤導覽（結果樹）

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 下一個結果 | **F4** | ⚠️ |
| 上一個結果 | **Shift+F4** | ⚠️ |
| 開啟 match | **Enter** | ✅ |
| 開啟到側邊 | Ctrl+Enter（mac: Ctrl+Enter） | ❌ |
| 收合 file node | Enter on folder match | ❌ |
| 從結果跳回 input | Ctrl+↑ | ❌ |
| input → 結果樹 | Ctrl+↓ | ❌ |

### 2.5 Replace in Files

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 開啟 replace box | Ctrl+Shift+H 或 toggle 按鈕 | ❌ |
| 關閉 replace box | **Escape**（當 replace input focused） | ❌ |
| 單一 match replace | Replace 按鈕（每個 match 右側） | ❌ |
| File-level replace | Replace all in file 按鈕 | ❌ |
| Global replace | "Replace All" 按鈕 + confirm dialog | ❌ |
| Preserve Case | 替換時保留大小寫模式 | ❌ |
| Undo | Ctrl+Z 可 undo replace | 📝 |

### 2.6 進階操作

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| Multi-cursor | Ctrl+Shift+L → 所有 match 加游標 | ❌ |
| Remove from results | X 按鈕（match / file 層） | ❌ |
| 複製 path | 右鍵 → Copy Path | 📝 |
| include / exclude glob | 下方 filter fields | ❌ |

---

## 3. Tab / Editor 行為

### 3.1 Preview Tab（預覽模式）

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 觸發 | 單 click 開啟檔案 → **preview tab**（italic 標題） | ❌ |
| Preview 替換 | 再次單 click 另一檔 → 覆蓋同一 preview tab | ❌ |
| Pin（轉正式 tab） | 雙 click / 開始編輯 / 明確 pin | ❌ |
| Preview 識別 | Tab 標題為 *italic*，hover tooltip 顯示 "(preview)" | ❌ |
| 關閉 preview | Escape or close X | ❌ |

### 3.2 Dirty（未儲存）狀態

| 行為 | VS Code 規格（源自 multiEditorTabsControl.ts） | Lode 狀態 |
|------|----------------------------------------------|-----------|
| 判斷條件 | `editor.isDirty() && !editor.isSaving()` | ✅ |
| Tab 視覺 | Close X 被替換為 **●**（filled dot） | ✅ |
| CSS class | `tab.dirty` 加上 `dirty-border-top`（可選） | ❌ |
| Top border highlight | `highlightModifiedTabs` 設定控制，active/inactive 顏色不同 | ❌ |
| Saving 中 | dot 不顯示（避免誤以為仍 dirty） | ❌ |
| Close dirty tab | dialog: **Save / Don't Save / Cancel** | ⚠️ |
| Close multiple dirty | dialog 顯示所有未儲存清單 | ❌ |

### 3.3 Tab 互動

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 關閉 | X 按鈕（hover 顯示） / Ctrl+W | ✅ |
| 關閉其他 | 右鍵 → "Close Others" | ❌ |
| 關閉右側 | 右鍵 → "Close to the Right" | ❌ |
| 關閉已儲存 | 右鍵 → "Close Saved" | ❌ |
| Reopen closed | Ctrl+Shift+T | ❌ |
| Tab 排序 | **Drag to reorder**（within group） | ❌ |
| 拖到新 group | Drag to editor edge → split | ❌ |
| 拖到新視窗 | Drag out → new window（default）；Alt+drag = copy | ❌ |
| Sticky tab | Pin to left side，不隨 scroll 消失 | ❌ |
| Tab 高度 | Normal: 35px / Compact: 22px（可設定） | 📝 |
| 中鍵 click | 關閉 tab | ❌ |

### 3.4 Tab 鍵盤快捷鍵

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 切換 tab | Ctrl+Tab / Ctrl+Shift+Tab | ⚠️ |
| 跳到第 N 個 tab | Ctrl+1…9（macOS: Cmd+1…9） | ❌ |
| 移至下一個 group | Ctrl+K → Ctrl+→ | ❌ |
| 分割 editor | Ctrl+\ | ❌ |

### 3.5 Editor Group（Split）

| 行為 | VS Code 規格 | Lode 狀態 |
|------|-------------|-----------|
| 水平分割 | Ctrl+\（新增右側 group） | ❌ |
| 垂直分割 | Ctrl+K → Ctrl+\ | ❌ |
| 移動 tab 到 group | Drag or "Move Editor into..." | ❌ |
| 複製 tab 到 group | Alt+drag | ❌ |
| 關閉 group | 關閉所有 tabs → group 消失 | 📝 |
| Group focus 指示 | Active group border 或 highlight | ⚠️ |

---

## 4. 綜合 UX 模式整理

### 4.1 統一 UX 原則（VS Code 遵循的）

1. **Inline editing 優先**：rename、new file 都在 tree 原地 inline input，不彈出 modal dialog
2. **Escape = 取消一切**：任何 inline 輸入、replace widget、filter 都用 Escape 取消
3. **Enter = 確認 / 開啟**：search result Enter 開啟；inline input Enter 確認
4. **Dirty indicator 優先於 close button**：有未儲存變更時，X → ●（dot）
5. **Preview tab 消費單一 slot**：避免 explorer 瀏覽時爆炸性開啟 tabs
6. **Non-blocking confirm**：刪除確認使用 dialog，不使用 blocking prompt
7. **Context menu 一致性**：右鍵選單項目在所有 tree（explorer/search/SCM）有共同結構
8. **Keyboard-first**：所有操作都有對應快捷鍵，toolbar 是快捷鍵的 visual alias

### 4.2 Lode 優先實作建議（依 ROI 排序）

| 優先 | 功能 | 說明 |
|------|------|------|
| 🔴 高 | Tab dirty dot | 已有 isDirty 邏輯，補 CSS ● 及 saving 判斷即可 |
| 🔴 高 | Search F4 / Shift+F4 | 結果樹 next/prev 跳轉，User 最常用 |
| 🔴 高 | Search 結果計數 | panel title "X results in Y files" |
| 🟡 中 | Inline rename（F2） | tree 中 input field，不彈 modal |
| 🟡 中 | Delete confirm dialog | "Move to Trash" vs "Delete Permanently" |
| 🟡 中 | Close dirty tab dialog | Save / Don't Save / Cancel 三選一 |
| 🟡 中 | Preview tab mode | single-click = preview，避免 tab 爆炸 |
| 🟢 低 | Replace in Files | 大工程，Phase 後期 |
| 🟢 低 | Tab drag reorder | UX polish，不影響核心 |
| 🟢 低 | Multi-cursor at results | 進階功能 |

---

## 5. Source 參考

| 功能 | VS Code 檔案 |
|------|-------------|
| Search keyboard actions | `src/vs/workbench/contrib/search/browser/searchActionsNav.ts` |
| Tab dirty state | `src/vs/workbench/browser/parts/editor/multiEditorTabsControl.ts` → `doRedrawTabDirty()` |
| Tab drag / context menu | `src/vs/workbench/browser/parts/editor/editorTabsControl.ts` → `onTabContextMenu()` / `onGroupDragStart()` |
| File operations | `src/vs/workbench/contrib/files/browser/fileActions.ts` |
| Explorer viewer | `src/vs/workbench/browser/parts/explorer/explorerViewer.ts` |

> 抓取時間：2026-06-02。VS Code 版本：main branch（持續更新）。
