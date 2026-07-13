"""Tests for the packaged Codex template resource loader.

The installer (Task 3) will need to render and write Codex agent/AGENTS/
model-routing templates that ship inside the distribution wheel. The
loader here is the single read-side interface to those packaged
resources.

It must:
- resolve resource names relative to the package data root,
- return the raw bytes/text content,
- raise a clear error when a packaged template is missing so callers
  can surface actionable messages instead of cryptic FileNotFoundError,
- fall back to ``importlib.resources`` when the direct filesystem
  path is unavailable (for example when the code lives inside a wheel
  installed to a read-only location where the absolute on-disk path
  does not exist).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src import codex_global


def test_package_data_root_exists() -> None:
    """The codex_global module exposes a discoverable data root."""
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
    assert "templates/codex" in msg


def test_load_template_rejects_path_traversal() -> None:
    """Resource names must not escape the package via '..' segments."""
    with pytest.raises(ValueError):
        codex_global.load_template("../pyproject.toml")


def test_load_template_falls_back_to_importlib_resources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When the direct filesystem path is unavailable, the loader uses
    importlib.resources to read from the ``src`` package's ``templates/codex``
    subdirectory."""
    # Redirect package_data_root() to a path that does not exist on disk
    # so the on-disk lookup is guaranteed to miss. The loader must still
    # succeed by falling back to importlib.resources.
    missing = tmp_path / "definitely-not-on-disk"
    monkeypatch.setattr(codex_global, "package_data_root", lambda: missing)

    text = codex_global.load_template("agents/AGENTS.md")
    assert isinstance(text, str)
    assert text.strip(), "AGENTS.md template should not be empty"