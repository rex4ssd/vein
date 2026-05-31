# Vein — Flowchart Diagrams
> 兩張流程圖：Lode+Vein 協作、Vein+AI session 循環。
> Mermaid 版（Jekyll 可直接 render）+ SVG embed 版（見 flowcharts.svg）。

---

## Flow 1 — Lode + Vein（Sunnywalker 協作）

```mermaid
flowchart TD
    Q([Developer has a question\n'why does this code look like this?'])

    Q -->|finds the code| L
    Q -->|remembers the why| V

    L["📦 Lode\nBrowse · Diff · Search code"]
    V["🌿 Vein\nvein recall 'sqlite'"]

    L --> L2[Spot decision point or bug\nwhile viewing code in Lode]
    V --> V2[Instant answer\nno grep, no archaeology]

    L2 --> LOG["vein log decision / lore / pitfall\none-line capture"]
    LOG --> ENTRY[.vein/ entry created\npolished by local AI via ollama]

    ENTRY --> ANS
    V2    --> ANS

    ANS(["✅ Question answered\nLode shows the code · Vein explains the why"])
```

---

## Flow 2 — Vein + Claude / Gemini（AI session 循環）

```mermaid
flowchart TD
    START([New AI session starts\nClaude · Gemini · GPT · Cursor])

    START --> BRIEF["vein brief\n&lt;800 token session primer"]
    BRIEF --> PASTE["Paste primer → AI is oriented\nNo re-explaining. No re-loading. No tax."]
    PASTE --> WORK["🔧 Work session\ndecisions made · bugs fixed · quirks found"]
    WORK  --> LOG["vein log — capture the knowledge\n.vein/ updated · committed to git"]
    LOG   -->|next session| START
```

---

## SVG 版

見同目錄 `flowcharts.svg`，可直接 `<img src="flowcharts.svg">` 或 `{% include flowcharts.svg %}` 內嵌。

---

## 使用建議（網頁）

| 情境 | 用法 |
|------|------|
| Jekyll + mermaid plugin | 直接用上面的 code block |
| 靜態 HTML embed | `<img src="flowcharts.svg" alt="Vein workflow">` |
| Dark mode 支援 | SVG 使用 CSS variable，跟隨 `prefers-color-scheme` |
| OG image / social | 截圖 SVG，export 為 1200×630 PNG |
