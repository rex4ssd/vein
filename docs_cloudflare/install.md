# Install

> *Placeholder — Vein is in Phase 0. The commands below are the planned UX. Actual install will work once Phase 0 code ships (target: 2026 Q3).*

## Requirements

- macOS / Linux / WSL
- Python 3.11+
- [Ollama](https://ollama.com) running locally (for embedding + capture-time polish)

## Install via pip

```bash
pip install lode-vein
```

> Note: PyPI package is `lode-vein` (the `vein` package name is squat-occupied). The CLI command is still `vein`.

## Install via Homebrew *(planned)*

```bash
brew install rex4ssd/tap/vein
```

## Set up Ollama models

```bash
# Embedding model (small, fast)
ollama pull nomic-embed-text

# Capture-time polish model (medium)
ollama pull qwen2.5-coder:7b
```

## First run

```bash
cd your-project
vein init

# Capture your first decision
vein log decision "chose React 18 over Vue 3 for ecosystem compatibility"

# Verify
vein recall "react"
```

## MCP setup (for Claude Desktop / Cursor)

Add to your MCP client config:

```json
{
  "mcpServers": {
    "vein": {
      "command": "vein",
      "args": ["serve"]
    }
  }
}
```

Tool-specific guides coming soon.

## Uninstall

```bash
pip uninstall lode-vein
rm -rf .vein/
```

That's it. Vein never installs system-wide hooks or background daemons (except the optional `vein serve` MCP server you launch explicitly).
