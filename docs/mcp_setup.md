# Vein MCP Server — Setup Guide

## 安裝

```bash
pip install 'lode-vein[mcp]'
```

---

## Claude Desktop 設定

編輯 `~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "vein-lode": {
      "command": "vein",
      "args": ["mcp"],
      "cwd": "/Users/lion/Documents/lode"
    },
    "vein-vein": {
      "command": "vein",
      "args": ["mcp"],
      "cwd": "/Users/lion/Documents/vein"
    }
  }
}
```

每個專案一個 entry，`cwd` 指向那個專案的 root（有 `.vein/` 的地方）。

重開 Claude Desktop，左下角出現 🔌 就代表 MCP 上線。

---

## Claude Code / Cowork 設定

在專案的 `.claude/settings.json`（或 global `~/.claude/settings.json`）：

```json
{
  "mcpServers": {
    "vein": {
      "command": "vein",
      "args": ["mcp"]
    }
  }
}
```

Claude Code 會用 project root 當 cwd，自動找到 `.vein/`。

---

## 確認上線

在 Claude 對話框試這個：

```
call vein_status
```

應該回傳：`lode (Phase 0) — 13 lore entries: 5 decisions, 4 pitfalls, ...`

---

## 四個工具

| Tool | 用途 | 何時呼叫 |
|------|------|---------|
| `vein_brief()` | 拿 session primer | 每次 session 開始 |
| `vein_recall(query)` | 查 lore | 改 code 前先查 why |
| `vein_log(type, message)` | 寫 lore | 做決定後馬上記 |
| `vein_status()` | 看 entry 數量 | 確認 server 正常 |

---

## 直覺用法（不用記任何指令）

設定好 MCP 之後，Claude 在這個專案就自動知道要：
- session 開始 → 呼叫 `vein_brief()` 拿 context
- 改架構 → 先 `vein_recall()` 確認沒有衝突的舊決定
- 決定後 → 自動 `vein_log()` 記錄

**用戶完全不用打任何 vein 指令。**

---

## Troubleshooting

**`MCP package not installed`**
→ `pip install 'lode-vein[mcp]'`

**`No .vein/ found`**
→ 在專案 root 跑 `vein init`，或確認 `cwd` 設對了

**SSE mode（遠端 / 瀏覽器）**
```bash
vein mcp --transport sse --port 8765
# → http://localhost:8765/sse
```
