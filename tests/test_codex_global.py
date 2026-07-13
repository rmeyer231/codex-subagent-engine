"""Tests for the packaged Codex template resource loader.

The installer (Task 3) will need to render and write Codex agent/AGENTS/
model-routing templates that ship inside the distribution wheel. The loader
here is the single read-side interface to those packaged resources.

It must:
- resolve resource names relative to the package data root,
- return the raw bytes/text content,
- raise a clear error when a packaged template is missing so callers
  can surface actionable messages instead of cryptic FileNotFoundError.
"""

from __future__ import annotations

import pytest

from src import codex_global


def test_package_data_root_exists() -> None:
    """The codex_global package exposes a discoverable data root."""
    root = codex_global.package_data_root()
    assert root.exists(), f"package data root missing: {root}"
    assert root.is_dir(), f"package data root is not a directory: {root}"


def test_load_template_returns_text() -> None:
    """load_template reads a packaged resource and returns its text contents."""
    text = codex_global.load_template("agents/AGENTS.md")
    assert isinstance(text, str)
    assert text.strip(), "AGENTS.md template should not be empty"


def test_load_missing_template_raises_actionable_error() -> None:
    """Missing templates raise CodexTemplateNotFound with the package + name."""
    with pytest.raises(codex_global.CodexTemplateNotFound) as excinfo:
        codex_global.load_template("agents/does_not_exist.md")
    msg = str(excinfo.value)
    assert "agents/does_not_exist.md" in msg
    assert "codex_global" in msg


def test_load_template_rejects_path_traversal() -> None:
    """Resource names must not escape the package via '..' segments."""
    with pytest.raises(ValueError):
        codex_global.load_template("../pyproject.toml")