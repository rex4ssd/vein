# VEIN REPORT 2026-05-31

## TL;DR

三個新 command（mcp / debrief / hooks）+ cross-project lore 架構建立 + Lode 2 個月 App Store 經驗入庫。

---

## 新 Command

### `vein mcp`
FastMCP server，4 tools：`vein_brief()` / `vein_recall(query)` / `vein_log(type, msg)` / `vein_status()`。

Claude Desktop 設定：
```json
{
  "mcpServers": {
    "vein-lode": {
      "command": "vein",
      "args": ["mcp"],
      "cwd": "/Users/lion/Documents/lode"
    }
  }
}
```
設定後 Claude 在對應 project session 自動呼叫，user 不需打任何指令。

### `vein debrief`
```bash
vein debrief              # 掃 last commit diff，ollama 提取 lore
vein debrief --since HEAD~5
vein debrief --dry-run    # 預覽不寫入
```
解決「自動捕獲 = 雜訊太多、手動 = 沒人做」的核心矛盾：
- commit 後觸發（自然節點）
- ollama 當 filter（AI 判斷值不值得記，不是 dumb rule）
- 無 ollama → graceful skip，不影響工作流

### `vein hooks`
```bash
vein hooks install    # 裝 post-commit hook（跑 vein debrief --silent）
vein hooks remove     # 移除
vein hooks status     # 確認狀態
```
Pure Python，zero deps，不需手動寫 shell script。

---

## Bug Fixes

| Bug | 修法 |
|-----|------|
| `hooks remove()` skip loop 從未 reset → 搬移 appended hook 整個消失 | 改用 string replace |
| `debrief` 第一次 commit HEAD~1 不存在 | fallback to `git show HEAD` |
| ollama 回傳 `{}` 被判定為「unavailable」 | `{}` = nothing found，連線失敗才是 None |
| `mcp_setup.md` Claude Code 路徑不對 | 修正為 `~/.claude.json` + `.claude/settings.local.json` |

---

## Cross-Project Lore 架構

**設計：** Cross-project lore 住在 Vein 自身 `.vein/`，不放各 source project repo。

**Tagging convention：**
```yaml
tags: [project:lode, apple-store, notarize, cloudflare]
      ^^^^^^^^^^^^^^                                     ← 永遠第一個
```

**Recall：**
```bash
vein recall "project:lode"           # 只看 Lode lore
vein recall "apple-store"            # 任何 project 的 apple-store lore
vein recall "project:fubon twse"     # 未來富邦的 lore
```

---

## Lode App Store 經驗入庫（24 條）

從 Lode 2 個月、4 次 App Store rejection 提取。目標：下次重來 2-7 天上架而非 2 個月。

**5 decisions：**
- Direct Sale first 6 months（30% vs 3% 抽成）
- CF Pages stuck-state → rebuild not repair
- notarytool store-credentials 一次性設定
- Developer ID Application cert（不是 Mac App Distribution）
- Universal Binary from day 1

**16 pitfalls（關鍵）：**
- App Store Sandbox/SSB 改造（Lode core feature 在 Sandbox 完全壞掉，4-6 天重寫）
- App Store 永遠拿不到 buyer email
- CF Pages CAS corruption → layout change 全站 500
- CF Pages Worker 1MB limit → silent runtime 500
- venv symlink in git → CF build fail
- robots.txt `Disallow: /` 封鎖 Googlebot
- GSC Domain property 只接 DNS TXT

**3 lore：**
- macOS 上架 checklist（必須在 submit 前建好的清單）
- notarize 驗證指令（spctl + codesign）
- CF Pages routing rules + debugging

---

## Strategy 更新（D-027/028/029）

- **D-027：** capture hierarchy — debrief（主力）> MCP（AI session）> hooks（背景）> manual
- **D-028：** Vein 的真正護城河 = AI-agnostic shared memory layer（Claude 記的 Gemini 也能讀）
- **D-029：** Core 7 commands 對外（init/log/recall/brief/debrief/mcp/hooks），walk/run/pipe 降級

---

## 待辦（下次接手）

1. `README.md` 補完（public flip 條件 3 — 陌生人 5 分鐘可上手）
2. `vein init` 加互動問「是否裝 hooks？」降低 onboarding 摩擦
3. PyPI 上架 `lode-vein`
4. Homebrew tap `rex4ssd/tap/vein`
5. 跑幾次 `vein debrief` 驗 ollama 提取品質（目前 qwen2.5-coder:7b，看夠不夠準）
6. `vein global brief` — 跨所有 project 的 orientation digest（multi-project power feature）
