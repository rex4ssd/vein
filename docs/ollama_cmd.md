# Ollama — vein 用的指令 & model 速查

> Mac Studio M1 / 32GB。vein 的 embed / polish / fetch 都走本機 ollama（`http://localhost:11434`）。

---

## 0. 重點：model 是按需載入，不是常駐

ollama 預設 **on-demand**：某個 model 被呼叫才載入記憶體，最後一次用完過 `keep_alive`（預設 **5 分鐘**）自動卸載。閒置時不吃 RAM，daemon 本身閒置也幾乎零負擔。

vein 的三個 model 各由不同指令觸發，**不會同時常駐**：

| config 欄位 | model | 何時載入 |
|---|---|---|
| `embed_model` | qwen3-embedding（或 bge-m3） | `vein recall` / `reindex` / `log` |
| `debrief_model` | qwen2.5-coder:7b | `vein debrief` / `log` polish |
| `fetch_model` | deepseek-r1:14b | `vein fetch` / `study` |

日常 `recall` 只 embed「一句 query」→ 極快；唯一重的是 `reindex`（一次 embed 全部 entries），偶爾才跑。

---

## 1. 控制何時卸載（free RAM）

```bash
# 用完 N 秒就卸載；設 "0" = 每次呼叫完立刻卸載
launchctl setenv OLLAMA_KEEP_ALIVE "30s"
# 改完重啟 ollama（menu bar app 退出再開，或 kill 後重跑）
```

```bash
ollama ps                        # 看現在誰被載入（閒置時應為空）
ollama stop qwen3-embedding:4b   # 手動卸載某 model
```

> `ollama serve` 報 `address already in use` = daemon 已在跑，不用再開。

---

## 2. Embedding model 選擇（embed_model 這格）

換掉 `nomic-embed-text`（堪用但中英跨語言弱）。32GB 都跑得動，差別在 load 速度 / RAM / 精準度：

| model | 大小(量化) | 維度 | 取捨 |
|---|---|---|---|
| `nomic-embed-text` | 274MB | 768 | 現況，最弱（尤其中問英答） |
| `qwen3-embedding:0.6b` | ~640MB | ≤1024 | 秒載、低 RAM，仍大幅贏 nomic ← 速度優先 |
| `bge-m3` | ~1.2GB | 1024 | 老牌強多語言，輕快 drop-in |
| `qwen3-embedding:4b` | ~2.5GB | 可調 | SOTA 中英，第一發 cold-load 幾秒 ← 精準優先 |
| `qwen3-embedding:8b` | ~6GB | 可調 | 最強但 reindex/recall 慢 |

**建議：** 天天用的 embed 選小的（`qwen3-embedding:0.6b` 或 `bge-m3`）最舒服；`debrief`/`fetch` 偶爾跑，留大 model 沒差。

---

## 3. 換 embed model 的步驟

```bash
# 1. 拉 model
ollama pull qwen3-embedding:0.6b      # 或 bge-m3 / qwen3-embedding:4b
```

```yaml
# 2. 改 .vein/config.yaml
model:
  base_url: http://localhost:11434
  embed_model: qwen3-embedding:0.6b   # ← 換這格
  debrief_model: qwen2.5-coder:7b
  fetch_model: deepseek-r1:14b
```

```bash
# 3. 維度變了，一定要 --force 重建 vec index
cd /Users/lion/Documents/vein && vein reindex --force
```

驗證 reindex 最後一行要看到 **`embedded: 134  fts-only: 0`**（不是 `embedded: 0`）。
若報維度不符 → vein 的 vec index 寫死了舊維度，需把 index 改成動態維度（vein-side 小修）。

---

## 4. 疑難排解

| 症狀 | 解 |
|---|---|
| reindex `embedded: 0` | model 沒 pull → `ollama pull <embed_model>`；或 daemon 沒跑 |
| recall 一直 `keyword`/`FTS5` 模式 | 同上，embedding 沒生效 |
| 測 embedding 通不通 | `curl -s http://localhost:11434/api/embeddings -d '{"model":"qwen3-embedding:0.6b","prompt":"test"}' \| head -c 120` 看到一串數字即 OK |
| Mac 變慢 | `ollama ps` 看常駐 model；`OLLAMA_KEEP_ALIVE` 設短；embed 換小 model |

---

## 5. 常用一覽

```bash
ollama list                      # 已安裝的 model
ollama ps                        # 當前載入中的 model
ollama pull <model>              # 下載
ollama stop <model>              # 卸載
ollama rm <model>                # 刪除
launchctl setenv OLLAMA_KEEP_ALIVE "30s"   # 閒置卸載時間
```
