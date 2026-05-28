"""Config loader — merges ai_providers.yaml + .env."""

from __future__ import annotations

from pathlib import Path

import yaml

# Search order for ai_providers.yaml
_PROVIDER_SEARCH = [
    Path.cwd() / "config" / "ai_providers.yaml",
    Path.home() / ".config" / "vein" / "ai_providers.yaml",
]


def load_env(project_root: Path | None = None) -> None:
    """Load .env from project_root (or cwd walk-up). No-op if python-dotenv missing."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    if project_root and (project_root / ".env").exists():
        load_dotenv(project_root / ".env", override=False)
    else:
        load_dotenv(override=False)


def load_ai_providers(project_root: Path | None = None) -> dict:
    """Load config/ai_providers.yaml. Falls back to minimal defaults."""
    search_paths = []
    if project_root:
        search_paths.append(project_root / "config" / "ai_providers.yaml")
    search_paths.extend(_PROVIDER_SEARCH)

    for p in search_paths:
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    # minimal defaults if file not found
    return {
        "local": {
            "backend": "ollama",
            "base_url": "http://localhost:11434",
            "polish_model": "qwen2.5-coder:7b",
            "digest_model": "llama3.2:3b",
            "embed_model": "nomic-embed-text",
            "analyze_model": "deepseek-r1:14b",
            "timeout_seconds": 120,
        }
    }


def get_local_config(providers: dict) -> dict:
    return providers.get("local", {})


def get_provider(providers: dict, name: str) -> dict | None:
    p = providers.get(name, {})
    if p.get("enabled", name == "local"):
        return p
    return None


def routing_for(providers: dict, task: str) -> list[str]:
    """Return ordered list of provider names for a task role."""
    routing = providers.get("routing", {})
    return routing.get(task, ["local"])
