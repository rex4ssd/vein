"""Tests for vein fetch — GitHub repo insight ingestion."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from vein.cli import main
from vein.commands.fetch import _normalise_github, _collect_files, _build_content, _readme_fallback


# ── _normalise_github ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("source, expected_slug", [
    ("owner/repo",                         "owner/repo"),
    ("https://github.com/owner/repo",      "owner/repo"),
    ("https://github.com/owner/repo.git",  "owner/repo"),
    ("github.com/owner/repo",              "owner/repo"),
    ("owner/repo.git",                     "owner/repo"),   # shorthand with .git
])
def test_normalise_github_slug(source, expected_slug):
    _, slug = _normalise_github(source)
    assert slug == expected_slug


@pytest.mark.parametrize("source, expected_url_prefix", [
    ("owner/repo",                     "https://github.com/owner/repo"),
    ("https://github.com/owner/repo",  "https://github.com/owner/repo"),
])
def test_normalise_github_url(source, expected_url_prefix):
    clone_url, _ = _normalise_github(source)
    assert clone_url.startswith(expected_url_prefix)


def test_normalise_github_invalid():
    import click
    with pytest.raises(click.BadParameter):
        _normalise_github("not-a-valid-source")


# ── _collect_files ────────────────────────────────────────────────────────────

def test_collect_files_readme_first(tmp_path):
    (tmp_path / "README.md").write_text("# Hello", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changes", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide", encoding="utf-8")

    files = _collect_files(tmp_path, max_files=5)
    assert files[0].name == "README.md"
    assert len(files) <= 5


def test_collect_files_respects_max(tmp_path):
    for i in range(10):
        (tmp_path / f"doc{i}.md").write_text(f"# Doc {i}", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    for i in range(10):
        (docs / f"d{i}.md").write_text(f"# {i}", encoding="utf-8")

    files = _collect_files(tmp_path, max_files=3)
    assert len(files) <= 3


def test_collect_files_empty_dir(tmp_path):
    files = _collect_files(tmp_path, max_files=5)
    assert files == []


# ── _build_content ────────────────────────────────────────────────────────────

def test_build_content_truncates(tmp_path):
    p = tmp_path / "README.md"
    p.write_text("x" * 20_000, encoding="utf-8")
    content = _build_content([p], max_chars=500)
    assert len(content) <= 550   # small buffer for header


def test_build_content_includes_filename(tmp_path):
    p = tmp_path / "DESIGN.md"
    p.write_text("Design notes here", encoding="utf-8")
    content = _build_content([p], max_chars=5000)
    assert "DESIGN.md" in content


# ── _readme_fallback ──────────────────────────────────────────────────────────

def test_readme_fallback_returns_one_entry(tmp_path):
    p = tmp_path / "README.md"
    p.write_text("# MyProject\n\nThis is a great tool for doing things.", encoding="utf-8")
    entries = _readme_fallback([p], "owner/myproject")
    assert len(entries) == 1
    assert entries[0]["type"] == "reference"
    assert "owner/myproject" in entries[0]["title"]


def test_readme_fallback_no_readme(tmp_path):
    entries = _readme_fallback([], "owner/norepo")
    assert len(entries) == 1
    assert entries[0]["type"] == "reference"


# ── CLI smoke test ────────────────────────────────────────────────────────────

def test_fetch_help():
    runner = CliRunner()
    result = runner.invoke(main, ["fetch", "--help"])
    assert result.exit_code == 0
    assert "owner/repo" in result.output


def test_fetch_dry_run_no_clone(tmp_path):
    """dry-run with mocked clone + ollama — nothing written to store."""
    runner = CliRunner()

    fake_items = [
        {"type": "reference", "title": "click overview", "body": "A CLI framework by Pallets."},
        {"type": "decision",  "title": "click uses decorators", "body": "Decorator-based API for ergonomics."},
    ]

    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # init a .vein/
        init_result = runner.invoke(main, ["init", "test"])
        assert init_result.exit_code == 0

        with (
            patch("vein.commands.fetch.subprocess.run") as mock_run,
            patch("vein.commands.fetch._collect_files") as mock_collect,
            patch("vein.commands.fetch._build_content", return_value="some docs"),
            patch("vein.commands.fetch._call_ollama_fetch", return_value=fake_items),
            patch("shutil.rmtree"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            # return two fake paths so collect doesn't return []
            mock_collect.return_value = [Path(td) / "README.md"]
            (Path(td) / "README.md").write_text("# click", encoding="utf-8")

            result = runner.invoke(main, ["fetch", "pallets/click", "--dry-run"])

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()

        # nothing written
        vein_dir = Path(td) / ".vein"
        all_entries = list(vein_dir.rglob("*.md")) if vein_dir.exists() else []
        # only config.yaml expected, no entry files
        assert not any(f.name.startswith("2") for f in all_entries)
