# docs_cloudflare/ — 公開網站內容

> **內部 readme，不會 publish 到網站。** 給未來的 Claude / Rex 看的元資料。

## 用途

這個資料夾放的是「**之後要 deploy 到 Cloudflare Pages（rexcode.app/vein）的公開內容**」，跟 `docs/` 內部開發 docs 分開兩條 track：

| 資料夾 | 對象 | 內容性質 | 語言 |
|---|---|---|---|
| `docs/` | Rex + Claude（內部 session）| 開發歷程、決策、雷區、戰略、命名辯論 | 繁中 + 英術語 |
| `docs_cloudflare/` | OSS 社群、潛在用戶、HN reader | 行銷文案、產品介紹、安裝指南 | **英文為主** |

## 為什麼分開

- 內部 docs 有 9 個 sub-session 的辯論歷程、競品數據、改名來回 — 對外部讀者是 noise
- 公開 docs 是「給陌生人 30 秒看懂 Vein」的 polish 版本
- 內部 docs commit 頻繁、會大改；公開 docs 動得慢、要 polish
- Cloudflare Pages 部署時 build pipeline 只抓 `docs_cloudflare/` 一個資料夾，乾淨

## 預定結構（Phase 0 階段，多數是 placeholder）

```
docs_cloudflare/
  _README.md           ← 本檔（不 publish）
  index.md             ← homepage（hero + tagline + 3 個 main feature 卡片）
  about.md             ← What is Vein / Lode Vein product family 介紹
  why.md               ← 為什麼存在（problem / 我們的解 / vs 競品）
  features.md          ← 完整功能列表（Phase 0 是 placeholder）
  install.md           ← Get started（待 code 寫完才填）
  faq.md               ← 常見問題（後期再加）
  assets/              ← 圖片 / 圖示（後期加）
```

## 部署計畫（先記）

- **Platform：** Cloudflare Pages（跟 Rex 既有 Jekyll 投資筆記站同 stack）
- **URL：** `rexcode.app/vein`（subdirectory of 主站）
- **Static generator：** 待定 — 可能用 Jekyll（沿用既有 stack）或 Astro / Hugo（純 markdown 友善）
- **Trigger：** push to `rex4ssd/vein` main branch → CF Pages auto-deploy
- **Time to first deploy：** **不急**。先把 `index.md` / `about.md` 寫到能 self-stand 即可

## 語言策略

- **主語言：英文** — OSS 社群、HN、Reddit 都是英語觀眾
- **未來 i18n：** 繁中版可能加 `/zh-tw/` subpath（學 React docs / Vercel 模式），但 Phase 0 不做
- **內部 docs 仍是繁中** — 不互相 sync

## 內容寫作原則

1. **短** — 用戶 30 秒掃完 hero + tagline 就要知道在幹嘛
2. **具體** — 用 code block / CLI 範例代替抽象描述
3. **誠實** — Phase 0 階段就明說「early access / dogfood phase」，不假裝穩定
4. **無 hype** — 不寫「revolutionary AI-powered memory layer」等行話；學 ripgrep / sqlite / git 的文案風格
5. **跟 Lode 互推** — homepage 提 Lode Vein family、Lode 那邊 footer 也提 Vein（之後做）

## 跟 docs/ 的互引規則

- **公開 docs 不引內部 docs** — 不貼 `decisions.md D-007` 連結，那是內部
- **內部 docs 可引公開 docs** — 「最終 marketing copy 見 docs_cloudflare/index.md」OK
- **共享的素材：** tagline / 產品名 / feature 短描述 — 公開先定，內部跟著用
