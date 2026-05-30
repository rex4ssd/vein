"""registry.py — global registry of known .vein/ project roots.

Enables cross-project recall: `vein recall "app store reject" -x` run from one
repo surfaces lore from every other repo that has run `vein init`. This is what
lets a new project (e.g. SunnyWalker) benefit from another's hard-won lore
(e.g. Lode's App Store cert pitfalls) instead of starting cold.

Stored as one absolute project-root path per line at
``$XDG_CONFIG_HOME/vein/registry.txt`` (default ``~/.config/vein/registry.txt``).
Plain text on purpose: human-inspectable, git-ignorable, trivially editable.
"""

from __future__ import annotations

import os
from pathlib import Path

VEIN_DIR = ".vein"


def registry_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "vein" / "registry.txt"


def register(root: Path) -> bool:
    """Add a project root to the registry. Idempotent. Returns True if added."""
    root = Path(root).resolve()
    existing = _read_raw()
    if root in existing:
        return False
    existing.append(root)
    _write(existing)
    return True


def roots() -> list[Path]:
    """Registered roots that still contain a .vein/, deduped, order preserved."""
    out: list[Path] = []
    seen: set[Path] = set()
    for p in _read_raw():
        if p in seen:
            continue
        if (p / VEIN_DIR).is_dir():
            seen.add(p)
            out.append(p)
    return out


def _read_raw() -> list[Path]:
    path = registry_path()
    if not path.exists():
        return []
    return [
        Path(line.strip())
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write(paths: list[Path]) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(str(p) for p in paths) + "\n", encoding="utf-8")
