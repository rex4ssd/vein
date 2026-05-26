# ctx — Strategy & Business Model

> 商業 / 戰略 / 競爭定位。
> 跟 [`spec/v0.1.md`](spec/v0.1.md) 分工：spec 是**技術**藍圖，本檔是**商業**藍圖。
> 為什麼這個專案值得做兩年、怎麼長大、怎麼養活自己。

---

## 0. TL;DR

採 **Open Core** 模式：

| 產品 | 定位 | 收費 | 角色 |
|---|---|---|---|
| **ctx CLI** | 本機 AI context broker | 100% OSS、MIT、永遠免費 | adoption funnel |
| **ctx MCP server** | 同上，daemon 形態 | 100% OSS | LLM tool 標準介面 |
| **Lode** | 桌面 GUI（已存在） | 一次性付費 / App Store | premium companion |
| **ctx Cloud**（v1.x+ 才考慮） | 團隊 `.ctx/` sync + RBAC | 訂閱 / 企業 | enterprise value |

**核心信念：**
- **個人功能不鎖**。所有 individual developer 想要的 100% 免費。
- **商業價值來自協作、合規、ops** — 不來自 cripple-ware。
- **Local-first 是 brand promise，不可妥協**。Cloud 是 opt-in extension。
- **ctx 自己不一定要賺錢**。它的最大價值是當 Lode 的「不可替代附加值」+ 未來 Cloud 的「不可避開的本機 endpoint」。

---

## 1. Gemini 戰略建議的 critical review

Gemini 提的九個點，我逐條 buy / push-back：

### 1.1 把 `.ctx/` 變 De Facto Standard ✅ 方向對，但要小心 framing

**買單的部分：** 對，這是核心 moat。`.git/` 的 power 不在 git 本身，在「全世界 tooling 都讀 .git/」。`.ctx/` 同理。

**Push-back：** Standards 不是宣告出來的，是被採用出來的。我們 **不能在 README 寫「this is the standard」**——這是 LangChain 早期的錯。正確路徑：
1. Phase 0-1：自己 dogfood 到極致，做出無可挑剔的小工具
2. Phase 1-2：找 3-5 個早期 power user 共同改 schema（schema 是被「真實使用」碾過才會收斂）
3. Phase 2+：schema 凍結成 v1.0，**這時才能說 standard**
4. 在 schema 凍結前，**保留 breaking change 的權利**（用 `version:` field）

**做不到 standard 怎麼辦？** 沒關係，自用 + Lode 整合本身就值回票價。

---

### 1.2 嵌入 Git Hooks / CI/CD ✅ 對，但 Phase 0 不做

**買單：** `git commit` 時自動 update `.ctx/` summary、PR description 自動生成 from `.ctx`——這些是 sticky 的關鍵。

**Push-back：** Phase 0 **絕對不做**。原因：
- Git hook 設計錯一次會被 dev 終身討厭（每次 commit 多等 5 秒 = 卸載）
- 要先驗證「人工 `ctx ask`」真的有用，再考慮自動化
- Hook 牽涉到 `pre-commit` framework / husky / lefthook 多套生態，要先有人用才有得整合

**時程：** v0.5 後再加，**且預設 opt-in**（不自動寫 .git/hooks/）。

---

### 1.3 MCP Server 霸主 ✅ 押對寶

完全同意。MCP 正在變成 LLM tool 通信的事實標準（Anthropic / OpenAI / 大家都在跟）。**ctx 必須有最穩、最薄、最 spec-compliant 的 MCP server 實作**。

具體 commit：
- v0.3 加 `ctx serve --mcp`，wraps `ctx ask` / `ctx search` / `ctx digest` 三個 tool
- 認真寫 MCP integration test，跑在 CI

---

### 1.4 Lode 視覺化 Context Debugging ⭐ 這是 Gemini 最強的洞見

這條我加碼。**這是整個戰略的 keystone**。

理由：
- LLM 出錯時，現在 100% 黑箱——你不知道 Claude 「看到」什麼才講錯話
- ctx 本身已經把 context 結構化（chunks / digests / 進 brief 的 token），所以 visualization 的原料齊全
- Lode 已經有 file/folder/binary 三套 compare UI，**「context diff」就是再一套 compare，技術 reuse 高**
- 對付費 user 來說，這是一個「**為什麼我要買 Lode**」的硬理由

詳細展開見 §6。

---

### 1.5 Lode 當 RAG 管理面板 ⭕ 合理但 obvious

「右鍵資料夾 → Add to ctx ignore」這種 — 對的、要做、但**不是賣點**。屬於「沒有會被罵、有了不會被誇」的功能。優先級放第二梯。

---

### 1.6 ctx → Lode 行銷漏斗 ✅ 對

具體實作（每個都低成本）：
- `ctx --version` 末尾印一行：「Visual context debugger? Try Lode — rexcode.app/lode」
- README badges：「[Lode]」link
- ctx GitHub 首頁附 screenshot of Lode 的 context view
- **但不放 popup / nag**。OSS 工具 nag = 自殺

---

### 1.7 個人免費 ✅ 對

但要做到 **真的免費**：
- 無 telemetry default（要 telemetry → 明確 opt-in、可關）
- 無 nag screen
- 無「Pro feature locked」按鈕
- 無 phone-home，連 license check 都不做

每一個小細節都是品牌。Sentry 早期就是因為過度 commercial nudge 流失了一批死忠 OSS 粉。

---

### 1.8 ctx Cloud 訂閱 ⚠️ 跟 local-first 有張力，要設計好

**Gemini 的版本有問題：** 「資深工程師的 `.ctx` 自動同步給菜鳥」——這個直覺是對的，但 naive 實作會破壞 local-first 信任。

**問題：**
- `.ctx/` 含 chunk 原文 = 公司 source code 上雲 = 法務地獄
- 「中央伺服器自動同步」= 不再 local-first
- 違反 brand promise = OSS adoption 死

**正解：** Cloud 是 **e2e encrypted relay**，不是 source of truth。
- chunks / embeddings 在本機算
- 上雲前用 team key e2e 加密，server 看不到內容
- server 角色：blob storage + sync coordinator，不是 LLM、不是 search engine
- **如果 server 倒了，本機照樣跑** — 這是 local-first 的硬定義

技術細節：見 §5。

---

### 1.9 企業 RBAC ✅ 是 enterprise 的剛需

「哪些 agent / 員工能讀哪些 `.ctx` chunk」——這是金融 / 醫療 / 大公司一定會問的。但：

**Push-back：** 不是 v0.1-v0.5 的事。RBAC 是「打入企業」的功能，**不是「activation」的功能**。先讓 5 個個人 / 小團隊用得爽，再做 enterprise gate。

順序錯了會死：早期就做 SSO / SAML / audit log = 工程量爆炸 + 沒人用。

---

## 2. 三層護城河（怎麼真的建）

| Moat | 建法 | 風險 | 時程 |
|---|---|---|---|
| **Standard** (`.ctx/` format) | dogfood → 找 3-5 個 power user 共同收斂 schema → v1.0 凍結 | 沒人跟進 → 退回「自用工具」 | 12-18 個月 |
| **Workflow** (git hook / CI) | 等 ctx CLI 有 1K stars 再做 hook integration | 早做會被罵慢 / 干擾 | v0.5+ |
| **Protocol** (MCP server) | v0.3 做、認真寫 MCP spec compliance、認真寫 test | MCP spec drift / Anthropic 改方向 | v0.3，6 個月內 |

**最強的 moat 其實是第 4 個：「Network of one」**——只要 Rex 自己每天用 ctx + Lode + Claude 5 小時，半年後就有別人模仿不來的工作流深度。這個 moat 是時間 + dogfood，不是程式碼。

---

## 3. 雙軌：ctx OSS × Lode 付費

兩條產品線分工乾淨：

```
┌─────────────────────────────────────────────────────────┐
│  ctx (OSS, MIT)                                          │
│   • CLI + MCP server                                     │
│   • 100% local 跑得起來，沒有任何 Lode 依賴              │
│   • adoption funnel — 越多人用越好                       │
└─────────────────────────────────────────────────────────┘
                      ▲
                      │ 整合：lode://ctx/... URL scheme
                      │      Lode 讀 .ctx/ schema
                      │      Lode UI 操作呼叫 ctx CLI / MCP
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Lode (paid, closed-source, already shipping)            │
│   • Premium GUI for ctx + 其他既有 mode                  │
│   • 沒 Lode → ctx 還是好用                               │
│   • 有 Lode → ctx 變超好用（visualization 加成）          │
└─────────────────────────────────────────────────────────┘
```

**關鍵紀律：**
- ctx 不能對 Lode 有任何 hard dependency。OSS 用戶 100% 不需要碰 Lode。
- Lode 對 ctx 的整合是「**讀 ctx 寫出的格式**」，不是「呼叫 Lode 才能解碼的東西」。
- 任何 Lode 才能做的事，**ctx CLI 也要能做**（只是醜一點）。否則違反 OSS 完整性。

---

## 4. Monetization：三層 Feature Matrix

| 能力 | Solo (free) | Team (paid) | Enterprise (paid) |
|---|:---:|:---:|:---:|
| **ctx CLI 全部 commands** | ✓ | ✓ | ✓ |
| **MCP server** | ✓ | ✓ | ✓ |
| **本機 embedding / digest** | ✓ | ✓ | ✓ |
| **無限 projects / chunks** | ✓ | ✓ | ✓ |
| **Lode integration（讀 .ctx 視覺化）** | ✓ | ✓ | ✓ |
| `.ctx/` git commit/share（手動） | ✓ | ✓ | ✓ |
| — | — | — | — |
| **Cloud sync**（e2e encrypted） |  | ✓ | ✓ |
| **Team digest aggregation** |  | ✓ | ✓ |
| **Shared topic digests** |  | ✓ | ✓ |
| **Onboarding mode**（讀別人的 .ctx） |  | ✓ | ✓ |
| — | — | — | — |
| **RBAC**（per-chunk access） |  |  | ✓ |
| **SSO / SAML** |  |  | ✓ |
| **Audit log** |  |  | ✓ |
| **Self-hosted sync server** |  | optional | ✓ |
| **SLA + priority support** |  | community | ✓ |
| **法務 / vendor 文件** |  |  | ✓ |

**核心原則：**
- Solo 那一欄沒有任何「打折版」的東西。CLI / MCP / Lode 整合全給。
- 付費價值都跟「多個人 / 跨機器 / 合規 / ops」相關。
- **沒有 per-feature paywall**——付費 tier 解鎖的是「協作能力」整包。

**價格（粗估，等實際時再校準）：**
- Team: $8-15 / user / month（學 Linear / Notion 區間）
- Enterprise: 詢價 / $20K+ ACV 起跳

---

## 5. Local-first × Cloud sync 怎麼共存（最微妙的部分）

這是整個戰略**最容易翻車**的地方。設計原則：

### 5.1 「Local-first」的硬定義（我們自己要守）

1. **離線可用**：沒網路 ctx 全功能跑（embedding / digest / ask / brief）。
2. **本機是 source of truth**：`.ctx/` 在本機是完整的，cloud 不是 master。
3. **Server 倒了不影響本機**：cloud sync = 加分項，不是 dependency。
4. **資料用戶可帶走**：`.ctx/` 可 rsync、可 commit、可拷貝。

### 5.2 ctx Cloud 的「正確」架構

```
本機 A                          本機 B
┌──────────┐                   ┌──────────┐
│  ctx CLI │                   │  ctx CLI │
│  .ctx/   │                   │  .ctx/   │
└────┬─────┘                   └────▲─────┘
     │ encrypted blob              │
     │ (team key, e2e)             │
     ▼                              │
   ┌─────────────────────────────────┐
   │  ctx Cloud (blob store + sync)  │
   │  • 看不到內容                    │
   │  • 只 route 加密 blob            │
   │  • 沒它 ctx 仍能跑              │
   └─────────────────────────────────┘
```

**Server 知道什麼：**
- team 有哪些 member（誰可以收 sync）
- blob 大小、時間戳（for sync 排程）

**Server 看不到什麼：**
- chunk 原文
- digest 內容
- query history

**這是不是「免費的 1Password 模式」？** 是的。1Password、Bitwarden、Standard Notes 都這樣做了，且企業愛這個——因為他們也不想資料給供應商看。

### 5.3 Phase 0 要為 Cloud 預留什麼？

**現在不做 cloud**，但 schema 設計要可加密：

- `.ctx/index/chunks.jsonl` 用 newline-delimited JSON，每行可獨立加密
- `.ctx/digests/*.md` 是純文字，可直接 GPG / age 加密
- `config.yaml` 預留 `team:` block（v0.1 留空，未來用）
- `version:` field 必要，以後加 cloud 用 schema migration

**不做的事：**
- 不寫 sync 程式碼
- 不選 cloud vendor
- 不研究 stripe billing
- 不研究 SAML

這些都 v1.x 才碰。

---

## 6. Lode 殺手 feature：Context Time Travel（回答 Gemini 最後那問）

Gemini 問：「Lode 做哪個 visualization 會讓付費用戶最驚豔？」

**我的答案：Context Time Travel + Diff**。理由如下：

### 6.1 痛點：LLM 出錯時你不知道牠看到什麼

現在 dev 用 Claude / Cursor 出錯時的反應：
1. 看 Claude 回答 → 錯的
2. 截圖丟群組 / Reddit 抱怨
3. 重新 ask → 還是錯
4. 換 model → 也錯
5. 放棄、手動寫

**沒有人知道 Claude 「看到」什麼 context**——因為 IDE 把那層藏起來了。

### 6.2 ctx 把這層 expose 出來

每次 `ctx ask "x"` 結束，`.ctx/memory/sessions.jsonl` 記：
```json
{
  "ts": "2026-05-26T14:33:12",
  "query": "MarkdownPreview Tailwind 那個雷",
  "chunks_used": ["src/...:42-78", "docs/decisions.md:D-018", ...],
  "digest": "<2K token brief>",
  "digest_token_count": 1843
}
```

### 6.3 Lode 怎麼把這變成 GUI 殺手 feature

**Lode 開「Context Time Travel」mode：**

```
┌────────────────────────────────────────────────────────────┐
│ Context Time Travel                          ⏸ ▶ ⏮ ⏭     │
├────────────────────────────────────────────────────────────┤
│ Session: 2026-05-26 14:33                                  │
│ Query: "MarkdownPreview Tailwind 那個雷"                   │
│                                                            │
│ ┌─ Chunks used (12) ────────────┬─ Digest sent (1843t) ──┐│
│ │ ✓ src/.../Preview.tsx:42-78   │ Root cause: Tailwind   ││
│ │ ✓ docs/decisions.md:D-018     │ v3 preflight reset...  ││
│ │ ✓ docs/changelog.md:session-AC│                        ││
│ │ ✗ src/.../Editor.tsx:200-250  │ ◀ chunk highlight on   ││
│ │   (excluded: low score 0.62)  │   hover                ││
│ │ ...                           │                        ││
│ └───────────────────────────────┴────────────────────────┘│
│                                                            │
│ [Diff against 2026-05-25 session] [Replay this context]   │
└────────────────────────────────────────────────────────────┘
```

**功能：**
- **時間軸 scrubbing**：拉 timeline 看不同時間 ctx 看到什麼
- **Chunk 高亮**：點 digest 某段 → 對應 chunk 高亮（reverse trace）
- **Context Diff**：比兩個 session 的 chunk set 差異
- **Replay**：用某天的 context 重跑今天的 query（debug AI drift）

### 6.4 為什麼是「殺手」

- **痛點真實**：每個用 LLM 的人都吃過幻覺
- **沒競品**：Cursor / Continue / Windsurf 都沒這個（它們的 context 是 closed source）
- **技術 fit**：Lode 既有 compare UI 直接 reuse
- **ctx-only**：用 Cursor 看不到 ctx 的 timeline，因為 timeline 在 `.ctx/memory/`
- **驅動 ctx adoption**：「為了看這個 timeline，我得用 ctx」

### 6.5 第二優先 feature（排第二梯）

1. **Topic Digest editor**：手動 curate「search 相關的」digest，給 ctx 用
2. **Chunk include/exclude visual editor**：folder tree 上 toggle 哪些檔入 index
3. **Embedding cluster view**：把 chunks 2D project 出來，看 semantic clusters

---

## 7. Reality Check / 風險清單

**這個戰略要跑通的真實機率：**

| 里程碑 | 機率 | 失敗 fallback |
|---|---|---|
| ctx 自己每天用得爽（Phase 0 dogfood） | 80% | 不行就回到「整理 CLAUDE.md」土法 |
| ctx 上 GitHub 拿 1K stars | 30% | 沒人 star = 純自用工具，沒差 |
| Lode + ctx 視覺化推動 Lode 銷量 +30% | 40% | 反正 Lode 也賣 |
| ctx Cloud 有 100 付費 team | 15% | 不做就好，OSS 還在 |
| 變成「.git 級」standard | 3% | 接受，這是 stretch goal |

**乘起來：full vision 成功率 ~1%**。但每個 fallback 都還是賺到的——這是好的 risk profile。

**最大的失敗模式：**
- **過度商業化太早**：v0.1 就想 cloud / billing → 主線 code 寫不完，OSS 沒人用
- **OSS 跟 commercial 角力**：Lode 整合做太死，OSS 不能單跑 → 信任崩
- **Local-first 妥協**：為了 cloud 簡化把資料明文上雲 → 死
- **Standard 病**：太早宣告 `.ctx/` 是 standard → 圈內笑 → 信譽掉

**最大的成功因子：**
- Rex 自己每天 dogfood，半年內 ctx 變不可或缺 → 一切其他事都可以慢慢來
- 早期 3-5 個粉用得爽、會寫 issue → schema 收斂的關鍵
- 跟一兩個 LLM client（Claude Desktop / Cursor）有 MCP 認證 → 跨工具 moat

---

## 8. Phase 0 要為未來 monetization 做對哪些事

**做了就好的（成本低 / 不做未來補很痛）：**

| 項目 | 為什麼 | 怎麼做 |
|---|---|---|
| `config.yaml` 有 `version:` field | 未來 schema migration | `version: "0.1"` |
| `config.yaml` 預留 `team:` block | 未來 cloud sync | 留空 + 註解 |
| chunks / digests 設計成「可獨立加密」 | 未來 e2e cloud | newline-delimited、每行獨立 |
| License 選 MIT 不是 AGPL/BUSL | OSS adoption 最大化 | 寫進 LICENSE 檔 |
| 沒有 telemetry default | 信任 | 連 phone-home 都不裝 |
| `.ctx/.gitignore` 預設正確 | 用戶自然分享公開部分 | 見 D-005 |

**現在不要做（做了浪費）：**
- billing 程式碼
- SSO / SAML
- audit log
- cloud server 程式碼
- team management UI
- pricing page / docs

**順手做（5 分鐘但長期保險）：**
- ✅ 註冊 `lodevein` GitHub org（保留 namespace，不一定要用，預防被別人蹭名）— **Session 0.11 加入 checklist**
- 註冊 `vein.dev` / `vein.app` domain（待測，可能被佔）
- TM 搜尋「Vein」+「Lode Vein」是否已被人註冊（待 public flip 前）

---

## 9. 未決議

| # | 問題 | 何時決 | 狀態 |
|---|---|---|---|
| S1 | License 用 MIT vs Apache-2.0（patent grant） | OSS release 前 | 暫定 MIT (D-006)，public flip 前再 review |
| S2 | 商標：vein 這名字會不會撞註冊？ | OSS release 前 | 已查 GitHub/npm/PyPI（D-007），TM 待查 |
| S3 | ~~Visibility timing: private vs public from day 1~~ | ~~進 code 前~~ | ✅ **已決 D-008**：private 現在，v0.3 flip public |
| S4 | Lode 的 Vein 整合做成「Vein mode」（新 mode）還是 sidebar 浮層？ | Lode v0.6 規劃時 | 未決 |
| S5 | Cloud sync 用自己的 server vs 用 GitHub repo 當 backend？ | v1.x 才碰 | 未決 |
| S6 | Vein Cloud 是 separate product 還是 Lode 的訂閱 add-on？ | v1.x 才碰 | 未決 |

---

## 11. Alternative thesis: "Decision / Debug Lore Archive"（Gemini Pivot, 2026-05-26）

Session 0.7 Gemini 提出一個 sharper 的切法，值得認真評估，可能取代或補強 Path B。

### 11.1 Core insight

> 程式碼是現在進行式，LLM context window 夠大就能掃完整 codebase 的 AST。
> 但**「為什麼上週三在這行加 workaround」、「為了避開某個 API bug 浪費 3 小時」**
> 這些**重構與 Debug 歷史**，LLM 永遠猜不到。

**這個切法的本質：** ctx 不是「code RAG broker」，是**「Decision & Debug Lore archive」**。

**對照競品：**
- context-hub / ctx-sys / ContextFS 全都做 code RAG / chunk + embed → 不可避免重複 git 已經提供的 code history
- 沒有人做「**AI 輔助的 Decision Lore 捕獲 + 自動關聯**」
- adr-tools 系列做 ADR 但**沒有 AI**、**沒有 RAG 索引**、**沒有 auto-surfacing**

這個 niche 真正的 gap：**ADR-style 紀錄 + AI 輔助 capture + RAG-style retrieval + Lode visualization**。

### 11.2 Critical review of Gemini's specifics

| Gemini 提的 | Buy / Push-back |
|---|---|
| Auto-bootstrap：`ctx init` 時 ollama 掃 git log 自動產第一版決策摘要 | ⚠️ **半買** — 想法對但執行有雷：AI auto-generated 的「決策」品質參差，bad summary 會污染 archive。**正解：產出 draft 進 `decisions/_drafts/`，由人 review 後才入 main archive** |
| Context As Code：`.ctx/` push to GitHub，Dev B clone 立刻繼承 Dev A 半年 debug 記憶 | ✅ **買** — 這是真實的 onboarding 殺手 use case，且**不需要 cloud sync**（git 本身就是 transport），規避了 local-first vs cloud 的張力 |
| `.ctx/` 黃金結構：`decisions/` + `debug_lore/` + `ctx.json` | ✅ **大致買** — 比我原 spec 的 `chunks.jsonl` + `embeddings.db` 簡單很多，純 markdown，git-friendly。但需要加一個 `index/`（embedding cache）才能做 RAG retrieval |
| Lode 「Send to ctx memory」按鈕 | ✅ **買** — 跟我之前推的 Context Time Travel 互補。「Send to ctx」是 capture 動作，Time Travel 是 review 動作 |
| Lode 決策時間軸 | ✅ **買** — 跟我之前推一致 |

### 11.3 為什麼這個 thesis 更好

1. **避開最擁擠的 niche**（code RAG 有 304⭐ 的 context-hub + 一堆小的競品）
2. **進到還沒被 AI 化的成熟領域**（ADR 模式存在十年，但沒有現代 AI 工具）
3. **價值不重疊 git** — git 給你 code history，ctx 給你 **decision history**
4. **天然 fits Lode** — Lode 已經有 diff / compare 三套 mode，「捕獲 diff 變決策」是自然延伸
5. **adoption 故事乾淨**：「LLM 看 code 看夠多了，但牠不知道你為什麼這樣寫」— 一句話講完
6. **schema 簡單** — markdown + frontmatter，不是 embeddings DB，git diff 友善

### 11.4 New Path D — Decision Lore Niche

**取代 / 補強 Path A/B/C。**

| 維度 | Path D 內容 |
|---|---|
| **Product positioning** | ctx = decision / debug lore archive，**不是** code RAG broker |
| **核心 schema** | `.ctx/decisions/*.md`（ADR 風格）+ `.ctx/debug_lore/*.md`（踩坑筆記）+ `.ctx/links/`（autogen，連到 git sha / file:line） |
| **Capture 機制** | `ctx log` CLI（主）+ Lode "Send to ctx" 按鈕（次）+ commit message tag（fallback）— 見 §12.5 |
| **AI 角色** | (a) 從 git log 跑 weekly draft → 人 review → 入 archive (b) capture 時即時 polish 用戶 stream-of-thought |
| **Retrieval** | RAG over `decisions/` + `debug_lore/`（小規模，幾百個檔，輕量 embedding 即可） |
| **Lode 殺手 feature** | 「決策時間軸」+「Send to ctx」+「給我相關的 lore」（在 diff view 旁顯示「這個檔 last 3 個相關決策」） |
| **改名** | 仍需要 — 但「decision lore」angle 讓改名更明確：`adrly` / `lore` / `cclore` / `ctx-lore` / `debugbook` 等 |

### 11.5 回答 Gemini 的觸發機制問題（auto-commit vs Lode button）

**Gemini 問：** 在日常開發節奏中，是「每次 git commit 自動觸發總結」好，還是「Lode 介面按鈕」好？

**我的答案：兩個都不對，正解是第三個（+ 那兩個當 fallback）：**

#### 主要觸發：`ctx log` CLI（terminal-native）

```bash
# 解完 bug 馬上
ctx log debug "API rate limit returns 200 not 429, see api/client.rs:142 workaround"

# 重構完
ctx log decision "dropped sqlite for parquet -- single-writer constraint failed scale test"

# Interactive mode（想清楚再寫）
ctx log
> Type: [d]ecision / [b]ug-lore / [r]efactor / [q]uirk
> Title: ...
> Body (multi-line, end with .): ...
> Links files (paste paths, empty to skip): ...
```

**為什麼這個是主：**
- ✅ **Rex 整天在 terminal** — 跟 vim / git / cmd_entry 同 surface
- ✅ **explicit semantic action** — 你說「這是 decision」才寫，不會 noise
- ✅ **Lode 可不開** — 不依賴 GUI
- ✅ **不污染 git workflow** — 跟 `git commit` 解耦

#### Fallback 1：Lode "Send to ctx" 按鈕

- 在 Lode diff view / file compare 找到「啊這就是上週修的雷」→ 右鍵 "Send to ctx" → 自動帶 file:line + diff snippet 進 `ctx log` 預填欄位
- 用於 **「眼睛先看到 → 想記」** 的順序（reverse capture）

#### Fallback 2：commit message magic tag

- commit message 含 `[decision]` / `[lore]` 等 tag → post-commit hook 觸發 `ctx log` 預填
- **opt-in**（要 user 主動裝 hook），絕不 default
- 用於 **「commit 才想起來要記」** 的補救

#### 為什麼**不**做「自動 on every commit 跑 AI summary」

- 90% 的 commit 不是 decision（fix typo / lint / 小 refactor）
- AI 對「無內容 commit」會幻覺，生出 noise pollute archive
- Hook 每次 commit 多 5-10 秒 = 終身被討厭
- Auto-bootstrap (Gemini 提的) **限定在 `ctx init` 一次性事件**才合理：那是 cold start 必要之惡；常駐 auto-summary 是惡

#### 三層 capture matrix

| 觸發 | 速度 | noise | 何時用 |
|---|---|---|---|
| `ctx log` CLI | 即時 | 零 | 主，bug/decision 解完當下 |
| Lode "Send to ctx" 按鈕 | 中（GUI 操作） | 零 | 開 Lode 比對時眼睛先看到 |
| commit magic tag | 慢（commit 後） | 低 | commit 才想起 |
| `ctx init` 一次 bootstrap | 一次性 | 低（人 review） | 第一次裝 ctx 補回去 |
| 每次 commit auto | n/a | **高** | **不做** |

### 11.6 Path D 對 Phase 0 spec 的影響

如果走 Path D，Phase 0 spec（v0.1）要改的事：

| 項目 | 原 spec | Path D 修正 |
|---|---|---|
| 核心動詞 | `ctx ask` / `ctx index` / `ctx digest` | `ctx log` / `ctx recall` / `ctx review` |
| `.ctx/` schema | chunks.jsonl + embeddings.db | decisions/*.md + debug_lore/*.md + links/ |
| 第一個能跑的 command | `ctx init` + `ctx ask` | `ctx log` + `ctx recall` |
| RAG scope | 全 repo 的 code + docs | 只有 `decisions/` + `debug_lore/`（小很多） |
| Lode 整合優先順序 | v0.4 才做 | **v0.2 就做**（Send to ctx 按鈕） |
| ollama 用量 | 高（每次 query 跑 digest） | **低**（capture 時 polish 一次，retrieve 走 embedding） |

工程量比原 spec 小：因為 archive scale 小（幾百個決策 vs 萬個 chunk），embedding / retrieval / digest 都更便宜。

### 11.7 Path D 風險

| 風險 | 描述 | 緩解 |
|---|---|---|
| Adoption 阻力 | 寫 ADR 是十年沒解的人類惰性問題；AI 輔助也不一定能解 | 把 `ctx log` 做到 ≤ 5 秒 friction；Lode "Send to ctx" 把 capture 變副產品 |
| 競品轉向 | ctx-sys / ContextFS 已經有 `decision` tool，可能轉向這個 niche | 我們**唯一不可被抄的**仍是 Lode 整合 + Rex dogfood |
| Niche 太小 | 「Decision lore」可能比 code RAG 小 10 倍市場 | 接受 — 配合 Lode 賺錢，不靠 ctx 本身賺 |
| 改名疲勞 | 第二次改名 | 一次性疼痛，越早越好 |

### 11.8 Path A/B/C/D 收斂建議

我現在的推薦排序：

1. **Path D** — Decision Lore niche（新 thesis，但是真正藍海，跟 Lode 整合最自然）
2. Path B — Lode-led + Context Time Travel（仍可行，但少了 Path D 的清晰 positioning）
3. Path C — abort 自寫，整合既有（context-hub / ctx-sys quality 不確定）
4. Path A — standalone OSS 改名重 niche（最累，紅海風險最大）

**Path D ≈ Path B 升級版** — 同樣 Lode-led，但 ctx engine 有了清晰的 unique positioning（decision lore 而非 code RAG）。

---

## 12. References

- 商業模式：Sentry / Linear / Mattermost / GitLab open core patterns
- Local-first 哲學：[inkandswitch local-first](https://www.inkandswitch.com/local-first/)
- 1Password / Bitwarden e2e encrypted sync 架構
- Anthropic MCP spec
