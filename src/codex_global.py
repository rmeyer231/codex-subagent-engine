"""Packaged Codex template resource loader.

The global Codex routing bundle (installed by ``cse install-codex``, added
in a later task) renders agent profiles, AGENTS routing guidance, and
the model-routing document from templates that ship inside the
distribution wheel under ``src/templates/codex/``.

This module is the single read-side interface to those packaged
resources. Keeping every read behind :func:`load_template` lets the
installer validate and report missing templates with an actionable
error, rather than a generic ``FileNotFoundError`` from somewhere deep
inside template rendering.

Resource names accepted here are *relative* POSIX-style paths under the
package data root (e.g. ``agents/AGENTS.md``). Traversal segments
(``..``) and absolute paths are rejected up front.
"""

from __future__ import annotations

from importlib.resources import files as _resource_files
from pathlib import Path
from typing import Final

_PACKAGE_PARENT: Final[str] = "src"
_DATA_SUBDIR: Final[str] = "templates/codex"


class CodexTemplateNotFound(FileNotFoundError):
    """Raised when a packaged Codex template cannot be located.

    The error message includes both the resource name and the package
    data root so the installer can render an actionable diagnostic.
    """

    def __init__(self, resource: str, package_data_root: Path) -> None:
        self.resource = resource
        self.package_data_root = package_data_root
        super().__init__(
            f"Packaged Codex template '{resource}' not found under "
            f"'{package_data_root}' (package '{_PACKAGE_PARENT}', "
            f"subdirectory '{_DATA_SUBDIR}'). "
            "The distribution may be corrupt or incomplete."
        )


def package_data_root() -> Path:
    """Return the on-disk path to the packaged Codex data directory.

    The data directory lives at ``src/templates/codex/`` inside the
    ``src`` package so Hatch ships it in the wheel via the
    ``include`` rule in ``pyproject.toml``.
    """
    return Path(__file__).resolve().parent / _DATA_SUBDIR


def _validate_resource_name(resource: str) -> str:
    """Validate and normalize a packaged-template resource name.

    Accepts POSIX-style relative paths only. Rejects absolute paths,
    empty strings, and any segment equal to ``..`` to prevent traversal
    outside the package data root.
    """
    if not isinstance(resource, str) or not resource:
        raise ValueError("resource name must be a non-empty string")
    if resource.startswith("/") or resource.startswith("\\"):
        raise ValueError(
            f"resource name must be relative, got absolute path: {resource!r}"
        )
    on_windows_sep = "\\" in resource
    parts = resource.replace("\\", "/").split("/")
    if any(part == ".." for part in parts):
        raise ValueError(
            f"resource name must not contain '..' segments: {resource!r}"
        )
    if any(part == "" for part in parts):
        raise ValueError(f"resource name has an empty segment: {resource!r}")
    if on_windows_sep:
        raise ValueError(
            f"resource name must use POSIX separators, got: {resource!r}"
        )
    return resource


def load_template(resource: str) -> str:
    """Read a packaged Codex template and return its UTF-8 text contents.

    Parameters
    ----------
    resource:
        Relative POSIX-style path under the package data root, e.g.
        ``agents/AGENTS.md`` or ``model-routing.md``.

    Returns
    -------
    str
        The decoded template text.

    Raises
    ------
    ValueError
        If ``resource`` is empty, absolute, or contains traversal segments.
    CodexTemplateNotFound
        If the resource does not exist in the installed distribution.
    """
    name = _validate_resource_name(resource)
    root = package_data_root()
    candidate = root.joinpath(name)

    # Direct filesystem path first — covers editable installs and most
    # wheel installs. When the on-disk path is unavailable (read-only
    # install root, zipapp, etc.) fall back to importlib.resources so
    # the wheel's recorded layout is consulted.
    try:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    except OSError:
        # Fall through to the importlib.resources lookup below.
        pass

    traversable = _resource_files(_PACKAGE_PARENT).joinpath(_DATA_SUBDIR, name)
    if traversable.is_file():
        return traversable.read_text(encoding="utf-8")

    raise CodexTemplateNotFound(name, root)


__all__ = [
    "CodexTemplateNotFound",
    "load_template",
    "package_data_root",
]
