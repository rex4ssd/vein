# Vein Test Suite

## 快速執行

```bash
# 在 project root 執行
pip install -e ".[dev]" --break-system-packages   # 第一次，或 pyproject.toml 有改

pytest tests/ -q                  # 全跑
pytest tests/test_models.py -q    # 只跑 models
pytest tests/test_store.py  -q    # 只跑 store
pytest tests/ -q -k "roundtrip"   # 只跑名稱含 roundtrip 的 case
pytest tests/ -q --tb=short       # 失敗時印 short traceback
```

預期輸出（目前 baseline）：

```
30 passed in 0.09s
```

---

## 目錄結構

```
tests/
  __init__.py
  README.md          ← 本檔：執行方式 + 規則
  test_models.py     ← Entry dataclass 測試
  test_models.md     ← test_models.py 說明文件 + flowchart
  test_store.py      ← VeinStore I/O 測試
  test_store.md      ← test_store.py 說明文件 + flowchart
```

---

## 測試檔對應表

| 測試檔 | 被測模組 | 說明文件 |
|--------|----------|----------|
| `test_models.py` | `src/vein/core/models.py` | [test_models.md](test_models.md) |
| `test_store.py`  | `src/vein/core/store.py`  | [test_store.md](test_store.md) |

---

## 新增功能的 validation 規則

每新增一個功能，**必須**在 `tests/` 建立對應的 validation `.py`，同時補一份同名 `.md`。

### 規則一覽

| 類型 | 說明 |
|------|------|
| **新命令** | `test_cmd_<name>.py` — 用 `click.testing.CliRunner` 跑 CLI |
| **新 core 模組** | `test_<module>.py` — 直接 import + assert |
| **新 I/O 流程** | `test_<flow>.py` — 用 `tmp_path` fixture 隔離 FS |
| **新 AI 整合** | `test_<feature>_offline.py` — **不連 ollama**，只測 fallback 路徑 |

### 假數據原則

- 所有測試用 `tmp_path`（pytest built-in）或 `@pytest.fixture` 隔離，**不汙染 `.vein/`**
- Entry 假數據統一用 `_make_entry(**overrides)` helper（見 `test_store.py`）
- 需要批量假數據時用 list comprehension + `Entry.new_id()`，不寫死 id
- 涉及 ollama 的功能，測試分兩層：
  1. `_offline` — mock / fallback，always pass（CI 可跑）
  2. `_live`（optional）— 需要本機 ollama，用 `@pytest.mark.skipif` 標記

### `skipif` 範例

```python
import httpx, pytest

def _ollama_alive() -> bool:
    try:
        return httpx.get("http://localhost:11434", timeout=1.0).status_code == 200
    except Exception:
        return False

requires_ollama = pytest.mark.skipif(not _ollama_alive(), reason="ollama not running")

@requires_ollama
def test_embed_live():
    from vein.core.embed import embed_text
    vec = embed_text("hello", base_url="http://localhost:11434")
    assert vec is not None and len(vec) == 768
```

---

## 功能 → 測試 對應（roadmap）

下列功能尚未有對應測試，新增時補齊：

| 功能 | 計畫測試檔 |
|------|------------|
| `vein.core.embed` — cosine / top_k | `test_embed.py` |
| `vein.core.index` — FTS + vector search | `test_index.py` |
| `vein.core.polish` — fallback_polish / auto_title | `test_polish.py` |
| `vein.core.brief` — generate_brief | `test_brief.py` |
| CLI: `vein log` (CliRunner) | `test_cmd_log.py` |
| CLI: `vein recall` (CliRunner) | `test_cmd_recall.py` |
| CLI: `vein import` (CliRunner + tmp decisions.md) | `test_cmd_import.py` |
| CLI: `vein reindex` (CliRunner) | `test_cmd_reindex.py` |
