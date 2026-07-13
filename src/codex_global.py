"""Packaged Codex template resource loader.

The global Codex routing bundle installed by ``cse install-codex`` renders
agent profiles, AGENTS routing guidance, and
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

import os
import shutil
import tempfile
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files as _resource_files
from pathlib import Path
from typing import Final

import tomlkit

_PACKAGE_PARENT: Final[str] = "src"
_DATA_SUBDIR: Final[str] = "templates/codex"
BEGIN_MARKER: Final[str] = "<!-- BEGIN CSE-MANAGED -->"
END_MARKER: Final[str] = "<!-- END CSE-MANAGED -->"
AGENT_NAMES: Final[tuple[str, ...]] = (
    "cse_explorer",
    "cse_planner",
    "cse_implementer",
    "cse_reviewer",
)
MANAGED_AGENT_SETTINGS: Final[dict[str, int | bool]] = {
    "max_threads": 4,
    "max_depth": 1,
    "job_max_runtime_seconds": 1800,
    "interrupt_message": True,
}
EXPECTED_SANDBOXES: Final[dict[str, str]] = {
    "cse_explorer": "read-only",
    "cse_planner": "read-only",
    "cse_implementer": "workspace-write",
    "cse_reviewer": "read-only",
}
INSTALL_PATHS: Final[tuple[Path, ...]] = (
    Path("config.toml"),
    Path("AGENTS.md"),
    Path("model-routing.md"),
    *(Path("agents") / f"{name}.toml" for name in AGENT_NAMES),
)


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


class CodexInstallError(RuntimeError):
    """Base class for installer failures with stable CLI exit behavior."""

    exit_code = 1


class InstallValidationError(CodexInstallError):
    """Raised for invalid templates, targets, or rendered configuration."""

    exit_code = 2


class InstallConflictError(CodexInstallError):
    """Raised when applying would overwrite unmanaged user content."""

    exit_code = 2


class InstallOperationalError(CodexInstallError):
    """Raised when backup, write, or post-write verification fails."""

    exit_code = 1


@dataclass(frozen=True)
class PlanEntry:
    """One redacted destination decision in a deterministic install plan."""

    relative_path: Path
    action: str
    reason: str

    @property
    def summary(self) -> str:
        """Return a target-relative summary that never includes file contents."""
        return f"{self.relative_path.as_posix()}: {self.action} ({self.reason})"


@dataclass(frozen=True)
class InstallPlan:
    """Validated, rendered installation plan and its observed target state."""

    codex_home: Path
    entries: tuple[PlanEntry, ...]
    rendered: Mapping[Path, str]
    observed: Mapping[Path, str | None]

    def entry_for(self, relative_path: Path) -> PlanEntry:
        """Return the entry for ``relative_path`` or raise ``KeyError``."""
        for entry in self.entries:
            if entry.relative_path == relative_path:
                return entry
        raise KeyError(relative_path)

    def content_for(self, relative_path: Path) -> str:
        """Return the validated content intended for ``relative_path``."""
        return self.rendered[relative_path]

    @property
    def conflicts(self) -> tuple[PlanEntry, ...]:
        """Return entries that require explicit conflict resolution."""
        return tuple(entry for entry in self.entries if entry.action == "conflict")

    @property
    def changes(self) -> tuple[PlanEntry, ...]:
        """Return entries that will be created or updated."""
        return tuple(
            entry for entry in self.entries if entry.action in {"create", "update"}
        )


@dataclass(frozen=True)
class InstallResult:
    """Outcome of applying a validated install plan."""

    changed: bool
    backup_directory: Path | None
    changed_paths: tuple[Path, ...]


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


def resolve_codex_home(
    explicit: str | os.PathLike[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve Codex home by option, environment, then user-home precedence."""
    environment = os.environ if environ is None else environ
    selected = explicit or environment.get("CODEX_HOME") or Path.home() / ".codex"
    return Path(os.path.abspath(Path(selected).expanduser()))


def _parse_toml(text: str, label: str) -> tomlkit.TOMLDocument:
    try:
        return tomlkit.parse(text)
    except Exception as exc:
        raise InstallValidationError(f"Invalid TOML in {label}: {exc}") from exc


def _load_validated_templates() -> dict[Path, str]:
    """Load and validate every packaged source before target inspection."""
    try:
        config_text = load_template("config.toml")
        routing_text = load_template("AGENTS.routing.md")
        model_text = load_template("model-routing.md")
        agent_texts = {
            name: load_template(f"agents/{name}.toml") for name in AGENT_NAMES
        }
    except (CodexTemplateNotFound, OSError) as exc:
        raise InstallValidationError(f"Unable to load Codex routing templates: {exc}") from exc

    config_doc = _parse_toml(config_text, "packaged config.toml")
    agents_settings = config_doc.get("agents")
    if not isinstance(agents_settings, Mapping):
        raise InstallValidationError("Packaged config.toml is missing the [agents] table")
    for key, expected in MANAGED_AGENT_SETTINGS.items():
        if agents_settings.get(key) != expected:
            raise InstallValidationError(
                f"Packaged config.toml [agents].{key} must equal {expected!r}"
            )

    for name, text in agent_texts.items():
        doc = _parse_toml(text, f"packaged agents/{name}.toml")
        _validate_agent_document(doc, name, "Packaged")

    _extract_managed_block(routing_text, "packaged AGENTS.routing.md")
    if not model_text.strip():
        raise InstallValidationError("Packaged model-routing.md must not be empty")

    return {
        Path("config.toml"): config_text,
        Path("AGENTS.md"): routing_text,
        Path("model-routing.md"): model_text,
        **{
            Path("agents") / f"{name}.toml": text
            for name, text in agent_texts.items()
        },
    }


def _extract_managed_block(text: str, label: str) -> str:
    begin_count = text.count(BEGIN_MARKER)
    end_count = text.count(END_MARKER)
    begin = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if begin_count != 1 or end_count != 1 or begin > end:
        raise InstallValidationError(
            f"{label} must contain exactly one ordered CSE BEGIN/END marker pair"
        )
    return text[begin : end + len(END_MARKER)]


def _validate_agent_document(
    doc: tomlkit.TOMLDocument, name: str, label_prefix: str
) -> None:
    for field in ("name", "description", "developer_instructions", "sandbox_mode"):
        if field not in doc or not str(doc[field]).strip():
            raise InstallValidationError(
                f"{label_prefix} agent {name} is missing required field {field!r}"
            )
    if str(doc["name"]) != name:
        raise InstallValidationError(
            f"{label_prefix} agent {name} declares mismatched name {doc['name']!r}"
        )
    if str(doc["sandbox_mode"]) != EXPECTED_SANDBOXES[name]:
        raise InstallValidationError(
            f"{label_prefix} agent {name} has invalid sandbox_mode {doc['sandbox_mode']!r}"
        )
    if "model" in doc:
        raise InstallValidationError(
            f"{label_prefix} agent {name} must omit model and inherit the parent model"
        )


def _merge_config(existing: str | None, template: str) -> str:
    if existing is None:
        return template
    doc = _parse_toml(existing, "target config.toml")
    agents = doc.get("agents")
    if agents is None:
        agents = tomlkit.table()
        doc["agents"] = agents
    if not isinstance(agents, Mapping):
        raise InstallValidationError("Target config.toml [agents] must be a TOML table")
    for key, value in MANAGED_AGENT_SETTINGS.items():
        agents[key] = value
    return tomlkit.dumps(doc)


def _merge_agents(existing: str | None, packaged_source: str) -> str:
    block = _extract_managed_block(packaged_source, "packaged AGENTS.routing.md")
    if existing is None or existing == "":
        return f"{block}\n"

    begin_count = existing.count(BEGIN_MARKER)
    end_count = existing.count(END_MARKER)
    if begin_count == 0 and end_count == 0:
        separator = "\n" if existing.endswith("\n") else "\n\n"
        return f"{existing}{separator}{block}\n"
    if begin_count != 1 or end_count != 1:
        raise InstallValidationError(
            "Target AGENTS.md must contain either no CSE markers or exactly one pair"
        )
    begin = existing.find(BEGIN_MARKER)
    end = existing.find(END_MARKER)
    if begin > end:
        raise InstallValidationError(
            "Target AGENTS.md contains a reversed CSE marker pair"
        )
    end += len(END_MARKER)
    return f"{existing[:begin]}{block}{existing[end:]}"


def _read_optional(path: Path) -> str | None:
    try:
        if not path.exists():
            return None
        if not path.is_file():
            raise InstallValidationError(
                f"Target destination {path.name} exists but is not a regular file"
            )
        return path.read_text(encoding="utf-8")
    except InstallValidationError:
        raise
    except (OSError, UnicodeError) as exc:
        raise InstallOperationalError(
            f"Unable to read target-relative destination {path.name}: {exc}"
        ) from exc


def _entry(relative_path: Path, observed: str | None, rendered: str) -> PlanEntry:
    if observed is None:
        return PlanEntry(relative_path, "create", "managed destination is absent")
    if observed == rendered:
        return PlanEntry(relative_path, "no-op", "managed content is current")
    return PlanEntry(relative_path, "update", "managed content differs")


def plan_install(
    codex_home: str | os.PathLike[str] | None = None,
    *,
    force_model_routing: bool = False,
    environ: Mapping[str, str] | None = None,
) -> InstallPlan:
    """Build a validated, deterministic plan without modifying the target."""
    home = resolve_codex_home(codex_home, environ=environ)
    templates = _load_validated_templates()
    observed = {path: _read_optional(home / path) for path in INSTALL_PATHS}

    rendered = dict(templates)
    rendered[Path("config.toml")] = _merge_config(
        observed[Path("config.toml")], templates[Path("config.toml")]
    )
    rendered[Path("AGENTS.md")] = _merge_agents(
        observed[Path("AGENTS.md")], templates[Path("AGENTS.md")]
    )
    _validate_rendered_bundle(rendered, templates[Path("AGENTS.md")])

    entries = [_entry(path, observed[path], rendered[path]) for path in INSTALL_PATHS]
    model_index = INSTALL_PATHS.index(Path("model-routing.md"))
    model_entry = entries[model_index]
    if model_entry.action == "update" and not force_model_routing:
        entries[model_index] = PlanEntry(
            Path("model-routing.md"),
            "conflict",
            "existing user content differs; pass --force-model-routing to replace",
        )

    return InstallPlan(home, tuple(entries), rendered, observed)


def _validate_rendered_bundle(
    rendered: Mapping[Path, str], packaged_routing_source: str
) -> None:
    expected = set(INSTALL_PATHS)
    if set(rendered) != expected:
        raise InstallValidationError("Rendered bundle has missing or unexpected destinations")

    config_doc = _parse_toml(rendered[Path("config.toml")], "rendered config.toml")
    agents = config_doc.get("agents")
    if not isinstance(agents, Mapping):
        raise InstallValidationError("Rendered config.toml is missing [agents]")
    for key, expected_value in MANAGED_AGENT_SETTINGS.items():
        if agents.get(key) != expected_value:
            raise InstallValidationError(
                f"Rendered config.toml [agents].{key} does not match the managed value"
            )

    expected_block = _extract_managed_block(
        packaged_routing_source, "packaged AGENTS.routing.md"
    )
    actual_block = _extract_managed_block(rendered[Path("AGENTS.md")], "rendered AGENTS.md")
    if actual_block != expected_block:
        raise InstallValidationError("Rendered AGENTS.md managed block is not current")
    if not rendered[Path("model-routing.md")].strip():
        raise InstallValidationError("Rendered model-routing.md must not be empty")
    for name in AGENT_NAMES:
        relative = Path("agents") / f"{name}.toml"
        doc = _parse_toml(rendered[relative], f"rendered {relative.as_posix()}")
        _validate_agent_document(doc, name, "Rendered")


def _assert_plan_is_current(plan: InstallPlan) -> None:
    for relative_path in INSTALL_PATHS:
        current = _read_optional(plan.codex_home / relative_path)
        if current != plan.observed[relative_path]:
            raise InstallConflictError(
                f"Target-relative destination {relative_path.as_posix()} changed after preview; "
                "build a fresh plan"
            )


def _create_backup(plan: InstallPlan) -> Path | None:
    existing_changes = [
        entry
        for entry in plan.changes
        if plan.observed[entry.relative_path] is not None
    ]
    if not existing_changes:
        return None

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    backup = plan.codex_home / "backups" / f"cse-{stamp}"
    try:
        for entry in existing_changes:
            source = plan.codex_home / entry.relative_path
            destination = backup / entry.relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    except OSError as exc:
        raise InstallOperationalError(
            f"Unable to create backup for {entry.relative_path.as_posix()}: {exc}"
        ) from exc
    return backup


def _atomic_write(path: Path, content: str) -> None:
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise InstallOperationalError(
            f"Unable to atomically replace {path.name}: {exc}"
        ) from exc
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


def _post_write_validate(plan: InstallPlan) -> None:
    installed: dict[Path, str] = {}
    try:
        for relative_path in INSTALL_PATHS:
            installed[relative_path] = (plan.codex_home / relative_path).read_text(
                encoding="utf-8"
            )
    except (OSError, UnicodeError) as exc:
        raise InstallOperationalError(
            f"Post-write validation could not read {relative_path.as_posix()}: {exc}"
        ) from exc
    for relative_path, expected in plan.rendered.items():
        if installed[relative_path] != expected:
            raise InstallOperationalError(
                f"Post-write validation mismatch for {relative_path.as_posix()}"
            )
    try:
        packaged_source = load_template("AGENTS.routing.md")
        _validate_rendered_bundle(installed, packaged_source)
    except (CodexTemplateNotFound, InstallValidationError, OSError) as exc:
        raise InstallOperationalError(f"Post-write validation failed: {exc}") from exc


def apply_plan(
    plan: InstallPlan,
    *,
    backup_reporter: Callable[[Path], None] | None = None,
) -> InstallResult:
    """Apply a conflict-free plan using backups and atomic replacements."""
    if plan.conflicts:
        paths = ", ".join(entry.relative_path.as_posix() for entry in plan.conflicts)
        raise InstallConflictError(
            f"Unresolved managed-content conflict in {paths}; use the explicit force option"
        )
    try:
        packaged_source = load_template("AGENTS.routing.md")
        _validate_rendered_bundle(plan.rendered, packaged_source)
    except (CodexTemplateNotFound, OSError) as exc:
        raise InstallOperationalError(
            f"Unable to revalidate packaged routing source before apply: {exc}"
        ) from exc
    _assert_plan_is_current(plan)
    if not plan.changes:
        return InstallResult(False, None, ())

    backup = _create_backup(plan)
    if backup is not None and backup_reporter is not None:
        backup_reporter(backup)
    for entry in plan.changes:
        _atomic_write(plan.codex_home / entry.relative_path, plan.rendered[entry.relative_path])
    _post_write_validate(plan)
    return InstallResult(
        True,
        backup,
        tuple(entry.relative_path for entry in plan.changes),
    )


__all__ = [
    "AGENT_NAMES",
    "BEGIN_MARKER",
    "CodexInstallError",
    "CodexTemplateNotFound",
    "END_MARKER",
    "EXPECTED_SANDBOXES",
    "INSTALL_PATHS",
    "InstallConflictError",
    "InstallOperationalError",
    "InstallPlan",
    "InstallResult",
    "InstallValidationError",
    "MANAGED_AGENT_SETTINGS",
    "PlanEntry",
    "apply_plan",
    "load_template",
    "package_data_root",
    "plan_install",
    "resolve_codex_home",
]
