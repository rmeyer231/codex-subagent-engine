"""Preview-first installation for the Claude/Codex OpenLimits stack."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files as _resource_files
from pathlib import Path
from typing import Any, Final

import tomlkit

from src import codex_global

_PACKAGE_PARENT: Final[str] = "src"
_DATA_SUBDIR: Final[str] = "templates/dual_harness"
DUAL_BEGIN_MARKER: Final[str] = "<!-- BEGIN CSE-DUAL-HARNESS -->"
DUAL_END_MARKER: Final[str] = "<!-- END CSE-DUAL-HARNESS -->"


class StackInstallError(RuntimeError):
    """Base error for dual-harness planning and installation."""

    exit_code = 1


class StackValidationError(StackInstallError):
    """A template, target, or option failed deterministic validation."""

    exit_code = 2


class StackConflictError(StackInstallError):
    """Target state or unmanaged content requires explicit resolution."""

    exit_code = 2


class StackCredentialError(StackInstallError):
    """Credential preflight failed without exposing command output."""

    exit_code = 3


class StackOperationalError(StackInstallError):
    """A backup, write, validation, or restoration operation failed."""

    exit_code = 1


@dataclass(frozen=True)
class StackTarget:
    """One destination and its immutable state at preview time."""

    key: str
    path: Path
    rendered: str
    observed: str | None
    observed_mode: int | None
    desired_mode: int
    action: str
    reason: str

    @property
    def summary(self) -> str:
        return f"{self.key}: {self.action} ({self.reason})"


@dataclass(frozen=True)
class StackPlan:
    """Validated cross-home plan; rendered and observed content stay private."""

    claude_home: Path
    codex_home: Path
    launcher_dir: Path
    backup_root: Path
    targets: tuple[StackTarget, ...]
    keychain_service: str
    keychain_account: str
    credential_command: tuple[str, ...]
    legacy_credential_paths: tuple[str, ...]

    @property
    def conflicts(self) -> tuple[StackTarget, ...]:
        return tuple(target for target in self.targets if target.action == "conflict")

    @property
    def changes(self) -> tuple[StackTarget, ...]:
        return tuple(
            target for target in self.targets if target.action in {"create", "update"}
        )


@dataclass(frozen=True)
class StackApplyResult:
    """Result of an apply or explicit rollback."""

    changed: bool
    transaction_id: str | None
    transaction_directory: Path | None
    changed_keys: tuple[str, ...]


def package_data_root() -> Path:
    """Return the editable-install location of dual-harness package data."""
    return Path(__file__).resolve().parent / _DATA_SUBDIR


def load_template(resource: str) -> str:
    """Load a UTF-8 resource from ``src/templates/dual_harness``."""
    if not resource or resource.startswith(("/", "\\")):
        raise ValueError("resource name must be a non-empty relative path")
    parts = resource.replace("\\", "/").split("/")
    if ".." in parts or "" in parts or "\\" in resource:
        raise ValueError("resource name must be a normalized POSIX relative path")
    candidate = package_data_root() / resource
    try:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    except OSError:
        pass
    traversable = _resource_files(_PACKAGE_PARENT).joinpath(_DATA_SUBDIR, resource)
    if traversable.is_file():
        return traversable.read_text(encoding="utf-8")
    raise StackValidationError(f"Missing packaged dual-harness resource: {resource}")


def load_codex_template(resource: str) -> str:
    """Expose the existing Codex resource loader to policy validators."""
    return codex_global.load_template(resource)


def load_policy() -> dict[str, Any]:
    """Load and minimally validate the canonical routing policy."""
    try:
        policy = json.loads(load_template("policy.json"))
    except json.JSONDecodeError as exc:
        raise StackValidationError(f"Invalid dual-harness policy JSON: {exc}") from exc
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise StackValidationError("Dual-harness policy must use schema_version 1")
    return policy


def _render_policy_template(resource: str, replacements: Mapping[str, str]) -> str:
    rendered = load_template(resource)
    for name, value in replacements.items():
        rendered = rendered.replace(f"{{{{{name}}}}}", value)
    if "{{" in rendered or "}}" in rendered:
        raise StackValidationError(f"Unresolved placeholder in {resource}")
    return rendered


def _claude_model_replacements(policy: Mapping[str, Any]) -> dict[str, str]:
    models = policy["models"]["claude"]
    return {
        "CLAUDE_ARCHITECTURE_MODEL": models["architecture"],
        "CLAUDE_IMPLEMENTATION_MODEL": models["implementation"],
        "CLAUDE_LOW_STAKES_MODEL": models["low_stakes"],
    }


def render_claude_routing() -> str:
    """Render managed Claude instructions from the canonical policy."""
    return _render_policy_template(
        "CLAUDE.routing.md", _claude_model_replacements(load_policy())
    )


def render_claude_model_routing() -> str:
    """Render Claude's model-routing document from the canonical policy."""
    return _render_policy_template(
        "model-routing.md", _claude_model_replacements(load_policy())
    )


def keychain_command(service: str, account: str) -> tuple[str, ...]:
    """Return the default command-backed credential lookup."""
    return (
        "/usr/bin/security",
        "find-generic-password",
        "-s",
        service,
        "-a",
        account,
        "-w",
    )


def render_launcher(
    *,
    credential_command: tuple[str, ...],
    claude_command: tuple[str, ...] = ("claude",),
) -> str:
    """Render the credential-free process-scoped Claude launcher."""
    return _render_openlimits_launcher(
        "claude-openlimits",
        credential_command=credential_command,
        command_placeholder="CLAUDE_COMMAND",
        harness_command=claude_command,
    )


def render_repoprompt_ce_launcher(
    *,
    credential_command: tuple[str, ...],
    repoprompt_ce_command: tuple[str, ...] = ("claude-rpce",),
) -> str:
    """Render the OpenLimits launcher that composes RepoPrompt CE discovery."""
    return _render_openlimits_launcher(
        "claude-openlimits-rpce",
        credential_command=credential_command,
        command_placeholder="REPOPROMPT_CE_COMMAND",
        harness_command=repoprompt_ce_command,
    )


def _render_openlimits_launcher(
    resource: str,
    *,
    credential_command: tuple[str, ...],
    command_placeholder: str,
    harness_command: tuple[str, ...],
) -> str:
    if not credential_command or not harness_command:
        raise StackValidationError("Credential and harness commands must be non-empty")
    policy = load_policy()
    replacements = _claude_model_replacements(policy)
    replacements.update(
        {
            "CREDENTIAL_COMMAND": shlex.join(credential_command),
            command_placeholder: shlex.join(harness_command),
            "CLAUDE_BASE_URL": shlex.quote(
                policy["providers"]["claude_openlimits"]["base_url"]
            ),
            **{
                key: shlex.quote(value)
                for key, value in _claude_model_replacements(policy).items()
            },
        }
    )
    return _render_policy_template(resource, replacements)


def validate_packaged_policy() -> None:
    """Validate policy/template agreement before a plan inspects targets."""
    policy = load_policy()
    claude_outputs = (render_claude_routing(), render_claude_model_routing())
    codex_outputs = (
        load_codex_template("AGENTS.routing.md"),
        load_codex_template("model-routing.md"),
    )
    for output in claude_outputs:
        if output.count(DUAL_BEGIN_MARKER) != 1 or output.count(DUAL_END_MARKER) != 1:
            raise StackValidationError("Claude managed template has invalid markers")
    for model in policy["models"]["claude"].values():
        if not all(model in output for output in claude_outputs):
            raise StackValidationError(f"Claude model missing from rendered policy: {model}")
    for model in policy["models"]["codex"].values():
        if model not in codex_outputs[1]:
            raise StackValidationError(f"Codex model missing from model routing: {model}")
    normalized_codex = " ".join(codex_outputs[0].split())
    for field in policy["handoff_fields"]:
        if f"`{field}`" not in normalized_codex:
            raise StackValidationError(f"Codex routing is missing handoff field: {field}")
    launcher = render_launcher(
        credential_command=keychain_command("OpenLimits", "api-key")
    )
    repoprompt_launcher = render_repoprompt_ce_launcher(
        credential_command=keychain_command("OpenLimits", "api-key")
    )
    for rendered_launcher in (launcher, repoprompt_launcher):
        if "ANTHROPIC_API_KEY=\"$token\"" not in rendered_launcher:
            raise StackValidationError("Launcher does not pass runtime credential")


def render_codex_config(
    existing: str | None,
    *,
    keychain_service: str,
    keychain_account: str,
    credential_command: tuple[str, ...] | None = None,
) -> str:
    """Merge OpenLimits into Codex TOML and return a first-pass fixed point."""
    rendered = existing or ""
    for _attempt in range(4):
        updated = _render_codex_config_once(
            rendered,
            keychain_service=keychain_service,
            keychain_account=keychain_account,
            credential_command=credential_command,
        )
        if updated == rendered:
            return updated
        rendered = updated
    raise StackValidationError("Codex OpenLimits provider rendering did not converge")


def _render_codex_config_once(
    existing: str,
    *,
    keychain_service: str,
    keychain_account: str,
    credential_command: tuple[str, ...] | None,
) -> str:
    try:
        doc = tomlkit.parse(existing)
    except Exception as exc:
        raise StackValidationError(f"Invalid target Codex config.toml: {exc}") from exc
    providers = doc.get("model_providers")
    if providers is None:
        providers = tomlkit.table()
        doc["model_providers"] = providers
    if not isinstance(providers, Mapping):
        raise StackValidationError("Codex model_providers must be a TOML table")

    policy = load_policy()
    provider_policy = policy["providers"]["codex_openlimits"]
    provider = tomlkit.table()
    provider["name"] = "OpenLimits"
    provider["base_url"] = provider_policy["base_url"]
    provider["wire_api"] = provider_policy["wire_api"]
    auth = tomlkit.table()
    command = credential_command or keychain_command(
        keychain_service, keychain_account
    )
    _validate_credential_command(tuple(command))
    auth["command"] = command[0]
    auth["args"] = list(command[1:])
    provider["auth"] = auth
    providers["openlimits"] = provider
    doc["model_provider"] = "openlimits"
    doc["model"] = policy["defaults"]["codex_model"]
    return tomlkit.dumps(doc)


_CLAUDE_MANAGED_ENV: Final[tuple[str, ...]] = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
)
_CLAUDE_SECRET_ENV: Final[tuple[str, ...]] = (
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
)


def _resolve_path(value: str | os.PathLike[str] | Path) -> Path:
    return Path(os.path.abspath(Path(value).expanduser()))


def resolve_stack_paths(
    *,
    claude_home: str | os.PathLike[str] | None = None,
    codex_home: str | os.PathLike[str] | None = None,
    launcher_dir: str | os.PathLike[str] | None = None,
    backup_root: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, Path, Path, Path]:
    """Resolve explicit paths before environment and user-home defaults."""
    environment = os.environ if environ is None else environ
    resolved_claude = _resolve_path(
        claude_home
        or environment.get("CLAUDE_CONFIG_DIR")
        or Path.home() / ".claude"
    )
    resolved_codex = codex_global.resolve_codex_home(codex_home, environ=environment)
    resolved_launcher = _resolve_path(
        launcher_dir or environment.get("CSE_LAUNCHER_DIR") or Path.home() / ".local/bin"
    )
    resolved_backup = _resolve_path(
        backup_root or resolved_codex / "backups/openlimits-stack"
    )
    return resolved_claude, resolved_codex, resolved_launcher, resolved_backup


def _read_target(path: Path) -> tuple[str | None, int | None]:
    try:
        if not path.exists():
            return None, None
        if path.is_symlink() or not path.is_file():
            raise StackValidationError(
                f"Managed target {path.name} must be a regular non-symlink file"
            )
        return path.read_text(encoding="utf-8"), path.stat().st_mode & 0o777
    except StackValidationError:
        raise
    except (OSError, UnicodeError) as exc:
        raise StackOperationalError(f"Unable to read managed target {path.name}: {exc}") from exc


def _target(
    key: str,
    path: Path,
    rendered: str,
    observed: str | None,
    observed_mode: int | None,
    *,
    default_mode: int = 0o644,
    forced_action: str | None = None,
    forced_reason: str | None = None,
) -> StackTarget:
    desired_mode = default_mode if observed_mode is None else observed_mode
    if key.startswith("launcher/"):
        desired_mode = 0o755
    if forced_action:
        return StackTarget(
            key,
            path,
            rendered,
            observed,
            observed_mode,
            desired_mode,
            forced_action,
            forced_reason or "explicit resolution required",
        )
    if observed is None:
        action, reason = "create", "managed destination is absent"
    elif observed == rendered and observed_mode == desired_mode:
        action, reason = "no-op", "managed content and mode are current"
    else:
        action, reason = "update", "managed content or mode differs"
    return StackTarget(
        key,
        path,
        rendered,
        observed,
        observed_mode,
        desired_mode,
        action,
        reason,
    )


def _extract_managed_block(text: str, label: str) -> str:
    if text.count(DUAL_BEGIN_MARKER) != 1 or text.count(DUAL_END_MARKER) != 1:
        raise StackValidationError(f"{label} must contain exactly one managed marker pair")
    begin = text.index(DUAL_BEGIN_MARKER)
    end = text.index(DUAL_END_MARKER)
    if begin > end:
        raise StackValidationError(f"{label} has reversed managed markers")
    return text[begin : end + len(DUAL_END_MARKER)]


def merge_managed_markdown(existing: str | None, packaged: str, label: str) -> str:
    """Replace or append exactly one dual-harness block while preserving prose."""
    block = _extract_managed_block(packaged, f"packaged {label}")
    if not existing:
        return f"{block}\n"
    begin_count = existing.count(DUAL_BEGIN_MARKER)
    end_count = existing.count(DUAL_END_MARKER)
    if begin_count == 0 and end_count == 0:
        separator = "\n" if existing.endswith("\n") else "\n\n"
        return f"{existing}{separator}{block}\n"
    if begin_count != 1 or end_count != 1:
        raise StackValidationError(f"Target {label} has incomplete or duplicate markers")
    begin = existing.index(DUAL_BEGIN_MARKER)
    end = existing.index(DUAL_END_MARKER)
    if begin > end:
        raise StackValidationError(f"Target {label} has reversed managed markers")
    end += len(DUAL_END_MARKER)
    return f"{existing[:begin]}{block}{existing[end:]}"


def render_claude_settings(
    existing: str | None,
    *,
    remove_api_key_helper: bool = False,
) -> tuple[str, tuple[str, ...], bool]:
    """Remove only managed gateway keys and report secret/helper conflicts."""
    try:
        document = json.loads(existing) if existing else {}
    except json.JSONDecodeError as exc:
        raise StackValidationError(f"Invalid target Claude settings.json: {exc}") from exc
    if not isinstance(document, dict):
        raise StackValidationError("Claude settings.json root must be an object")
    environment = document.get("env", {})
    if environment is None:
        environment = {}
    if not isinstance(environment, dict):
        raise StackValidationError("Claude settings.json env must be an object")
    legacy = tuple(
        f"claude/settings.json:env.{name}"
        for name in _CLAUDE_SECRET_ENV
        if environment.get(name)
    )
    for name in _CLAUDE_MANAGED_ENV:
        environment.pop(name, None)
    if environment:
        document["env"] = environment
    else:
        document.pop("env", None)
    helper_present = bool(document.get("apiKeyHelper"))
    if remove_api_key_helper:
        document.pop("apiKeyHelper", None)
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n", legacy, helper_present


def plan_stack(
    *,
    claude_home: str | os.PathLike[str] | None = None,
    codex_home: str | os.PathLike[str] | None = None,
    launcher_dir: str | os.PathLike[str] | None = None,
    backup_root: str | os.PathLike[str] | None = None,
    keychain_service: str = "OpenLimits",
    keychain_account: str = "api-key",
    credential_command: tuple[str, ...] | None = None,
    claude_command: tuple[str, ...] = ("claude",),
    repoprompt_ce_command: tuple[str, ...] = ("claude-rpce",),
    resolve_conflicts: bool = False,
    environ: Mapping[str, str] | None = None,
) -> StackPlan:
    """Build a deterministic plan without executing credentials or writing."""
    validate_packaged_policy()
    resolved = resolve_stack_paths(
        claude_home=claude_home,
        codex_home=codex_home,
        launcher_dir=launcher_dir,
        backup_root=backup_root,
        environ=environ,
    )
    resolved_claude, resolved_codex, resolved_launcher, resolved_backup = resolved
    command = credential_command or keychain_command(
        keychain_service, keychain_account
    )
    _validate_credential_command(tuple(command))

    try:
        codex_plan = codex_global.plan_install(
            resolved_codex,
            force_model_routing=resolve_conflicts,
            environ=environ,
        )
    except codex_global.CodexInstallError as exc:
        raise StackValidationError(f"Unable to compose Codex install plan: {exc}") from exc

    targets: list[StackTarget] = []
    for relative_path in codex_global.INSTALL_PATHS:
        observed = codex_plan.observed[relative_path]
        mode = _read_target(resolved_codex / relative_path)[1]
        rendered = codex_plan.rendered[relative_path]
        if relative_path == Path("config.toml"):
            rendered = render_codex_config(
                rendered,
                keychain_service=keychain_service,
                keychain_account=keychain_account,
                credential_command=command,
            )
        existing_entry = codex_plan.entry_for(relative_path)
        forced_action = None
        forced_reason = None
        if existing_entry.action == "conflict":
            forced_action = "conflict"
            forced_reason = existing_entry.reason
        targets.append(
            _target(
                f"codex/{relative_path.as_posix()}",
                resolved_codex / relative_path,
                rendered,
                observed,
                mode,
                forced_action=forced_action,
                forced_reason=forced_reason,
            )
        )

    settings_path = resolved_claude / "settings.json"
    settings_observed, settings_mode = _read_target(settings_path)
    settings_rendered, legacy, helper_present = render_claude_settings(
        settings_observed,
        remove_api_key_helper=resolve_conflicts,
    )
    targets.append(
        _target(
            "claude/settings.json",
            settings_path,
            settings_rendered,
            settings_observed,
            settings_mode,
            forced_action="conflict" if helper_present and not resolve_conflicts else None,
            forced_reason=(
                "apiKeyHelper may override native Claude authentication; "
                "review before explicit removal"
            ),
        )
    )

    for name, rendered_block in (
        ("CLAUDE.md", render_claude_routing()),
        ("model-routing.md", render_claude_model_routing()),
    ):
        path = resolved_claude / name
        observed, mode = _read_target(path)
        rendered = merge_managed_markdown(observed, rendered_block, name)
        targets.append(
            _target(f"claude/{name}", path, rendered, observed, mode)
        )

    launchers = (
        (
            "claude-openlimits",
            render_launcher(
                credential_command=command,
                claude_command=claude_command,
            ),
        ),
        (
            "claude-openlimits-rpce",
            render_repoprompt_ce_launcher(
                credential_command=command,
                repoprompt_ce_command=repoprompt_ce_command,
            ),
        ),
    )
    for launcher_name, launcher_rendered in launchers:
        launcher_path = resolved_launcher / launcher_name
        launcher_observed, launcher_mode = _read_target(launcher_path)
        launcher_conflict = (
            launcher_observed is not None
            and launcher_observed != launcher_rendered
            and not resolve_conflicts
        )
        targets.append(
            _target(
                f"launcher/{launcher_name}",
                launcher_path,
                launcher_rendered,
                launcher_observed,
                launcher_mode,
                default_mode=0o755,
                forced_action="conflict" if launcher_conflict else None,
                forced_reason=(
                    "existing launcher differs; review before explicit replacement"
                ),
            )
        )
    return StackPlan(
        resolved_claude,
        resolved_codex,
        resolved_launcher,
        resolved_backup,
        tuple(targets),
        keychain_service,
        keychain_account,
        tuple(command),
        legacy,
    )


def redact_text(value: object, secrets: tuple[str, ...] = ()) -> str:
    """Remove known secret values and common authorization/token forms."""
    text = str(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    patterns = (
        r"(?i)Bearer\s+[^\s,;]+",
        r"(?i)(?:ANTHROPIC_AUTH_TOKEN|ANTHROPIC_API_KEY|OPENAI_API_KEY)=[^\s]+",
        r"\b(?:sk|ol)-[A-Za-z0-9_-]{8,}\b",
    )
    for pattern in patterns:
        text = re.sub(pattern, "[REDACTED]", text)
    return text


def _validate_credential_command(command: tuple[str, ...]) -> None:
    if not command:
        raise StackValidationError("Credential command must not be empty")
    serialized = " ".join(command)
    if redact_text(serialized) != serialized:
        raise StackValidationError(
            "Credential command arguments must reference a credential store, not a raw token"
        )


def _default_credential_check(command: tuple[str, ...]) -> bool:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0 and bool(completed.stdout.strip())


def _assert_plan_is_current(plan: StackPlan) -> None:
    for target in plan.targets:
        current, mode = _read_target(target.path)
        if current != target.observed or mode != target.observed_mode:
            raise StackConflictError(
                f"{target.key} changed after preview; build and review a fresh plan"
            )


def _atomic_write(path: Path, content: str, mode: int) -> None:
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
        temporary.chmod(mode)
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise StackOperationalError(
            f"Unable to atomically replace managed target {path.name}: {exc}"
        ) from exc
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


def _write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    _atomic_write(path, json.dumps(manifest, indent=2) + "\n", 0o600)


def _transaction_id() -> str:
    return datetime.now(UTC).strftime("txn-%Y%m%dT%H%M%S.%fZ")


def _create_transaction(plan: StackPlan) -> tuple[Path, dict[str, Any]]:
    transaction_id = _transaction_id()
    transaction = plan.backup_root / transaction_id
    try:
        transaction.mkdir(parents=True, exist_ok=False)
        records: list[dict[str, Any]] = []
        for target in plan.changes:
            backup_relative: str | None = None
            if target.observed is not None:
                backup_path = transaction / "files" / target.key
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target.path, backup_path)
                backup_relative = backup_path.relative_to(transaction).as_posix()
            records.append(
                {
                    "key": target.key,
                    "path": str(target.path),
                    "existed": target.observed is not None,
                    "backup": backup_relative,
                    "mode": target.observed_mode,
                    "desired_mode": target.desired_mode,
                }
            )
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "transaction_id": transaction_id,
            "status": "prepared",
            "stack": "OpenLimits Max + Claude Pro + ChatGPT Free",
            "targets": records,
        }
        _write_manifest(transaction / "manifest.json", manifest)
        return transaction, manifest
    except (OSError, StackInstallError) as exc:
        raise StackOperationalError(
            f"Unable to create transaction backup set: {redact_text(exc)}"
        ) from exc


def _restore_records(
    transaction: Path,
    records: list[dict[str, Any]],
) -> tuple[str, ...]:
    restored: list[str] = []
    for record in reversed(records):
        path = Path(record["path"])
        try:
            if record["existed"]:
                backup = transaction / record["backup"]
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, path)
                if record["mode"] is not None:
                    path.chmod(record["mode"])
            else:
                path.unlink(missing_ok=True)
            restored.append(record["key"])
        except OSError as exc:
            raise StackOperationalError(
                f"Rollback failed for {record['key']}: {redact_text(exc)}"
            ) from exc
    return tuple(restored)


def validate_installed_plan(plan: StackPlan) -> None:
    """Post-write validation of contents, modes, providers, and native Claude lane."""
    for target in plan.targets:
        installed, mode = _read_target(target.path)
        if installed != target.rendered or mode != target.desired_mode:
            raise StackOperationalError(f"Post-write validation mismatch for {target.key}")
    settings = json.loads(
        next(target.rendered for target in plan.targets if target.key == "claude/settings.json")
    )
    environment = settings.get("env", {})
    if any(key in environment for key in _CLAUDE_MANAGED_ENV):
        raise StackOperationalError("Post-write Claude settings retain managed overrides")
    codex_text = next(
        target.rendered for target in plan.targets if target.key == "codex/config.toml"
    )
    codex_doc = tomlkit.parse(codex_text)
    if codex_doc.get("model_provider") != "openlimits":
        raise StackOperationalError("Post-write Codex provider is not OpenLimits")
    if codex_doc.get("model") != load_policy()["defaults"]["codex_model"]:
        raise StackOperationalError("Post-write Codex default model is not current")


def apply_stack(
    plan: StackPlan,
    *,
    credential_checker: Callable[[tuple[str, ...]], bool] | None = None,
    failure_hook: Callable[[str], None] | None = None,
) -> StackApplyResult:
    """Apply a conflict-free plan with one cross-home transaction and rollback."""
    if plan.conflicts:
        keys = ", ".join(target.key for target in plan.conflicts)
        raise StackConflictError(
            f"Unresolved managed-content conflict in {keys}; review and explicitly resolve"
        )
    if plan.legacy_credential_paths:
        paths = ", ".join(plan.legacy_credential_paths)
        raise StackCredentialError(
            f"Legacy plaintext credential detected at {paths}; rotate and remove it before apply"
        )
    checker = credential_checker or _default_credential_check
    try:
        credential_available = checker(plan.credential_command)
    except Exception:
        credential_available = False
    if not credential_available:
        raise StackCredentialError(
            "OpenLimits Keychain item is unavailable for "
            f"service={plan.keychain_service!r}, account={plan.keychain_account!r}"
        )
    _assert_plan_is_current(plan)
    if not plan.changes:
        return StackApplyResult(False, None, None, ())

    transaction, manifest = _create_transaction(plan)
    records_by_key = {record["key"]: record for record in manifest["targets"]}
    mutated_records: list[dict[str, Any]] = []
    event = "prepared"
    try:
        for target in plan.changes:
            event = f"before_write:{target.key}"
            if failure_hook:
                failure_hook(event)
            _atomic_write(target.path, target.rendered, target.desired_mode)
            mutated_records.append(records_by_key[target.key])
            event = f"after_write:{target.key}"
            if failure_hook:
                failure_hook(event)
        event = "before_validate"
        if failure_hook:
            failure_hook(event)
        validate_installed_plan(plan)
        event = "after_validate"
        if failure_hook:
            failure_hook(event)
        manifest["status"] = "applied"
        _write_manifest(transaction / "manifest.json", manifest)
    except Exception as exc:
        try:
            _restore_records(transaction, mutated_records)
            manifest["status"] = "auto_rolled_back"
            manifest["failure_boundary"] = event
            manifest["error_type"] = type(exc).__name__
            _write_manifest(transaction / "manifest.json", manifest)
        except StackInstallError as rollback_exc:
            raise StackOperationalError(
                f"Apply failed at {event}; automatic {redact_text(rollback_exc)}; "
                f"backups retained in transaction {transaction.name}"
            ) from None
        raise StackOperationalError(
            f"Apply failed at {event}; automatic rollback completed: {redact_text(exc)}"
        ) from None
    return StackApplyResult(
        True,
        manifest["transaction_id"],
        transaction,
        tuple(target.key for target in plan.changes),
    )


def rollback_transaction(
    transaction_id: str,
    *,
    backup_root: str | os.PathLike[str],
) -> StackApplyResult:
    """Restore one completed transaction without accessing credentials."""
    root = _resolve_path(backup_root)
    transaction = _resolve_path(root / transaction_id)
    if transaction.parent != root or transaction.name != transaction_id:
        raise StackValidationError("Invalid transaction identifier")
    manifest_path = transaction / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StackValidationError(
            f"Unable to read transaction manifest {transaction_id}: {redact_text(exc)}"
        ) from exc
    if manifest.get("schema_version") != 1 or manifest.get("transaction_id") != transaction_id:
        raise StackValidationError("Transaction manifest identity is invalid")
    if manifest.get("status") != "applied":
        raise StackConflictError(
            f"Transaction {transaction_id} is not in applied state"
        )
    records = manifest.get("targets")
    if not isinstance(records, list):
        raise StackValidationError("Transaction manifest targets are invalid")
    restored = _restore_records(transaction, records)
    manifest["status"] = "rolled_back"
    _write_manifest(manifest_path, manifest)
    return StackApplyResult(True, transaction_id, transaction, restored)


__all__ = [
    "DUAL_BEGIN_MARKER",
    "DUAL_END_MARKER",
    "StackApplyResult",
    "StackConflictError",
    "StackCredentialError",
    "StackInstallError",
    "StackOperationalError",
    "StackPlan",
    "StackTarget",
    "StackValidationError",
    "apply_stack",
    "keychain_command",
    "load_codex_template",
    "load_policy",
    "load_template",
    "merge_managed_markdown",
    "package_data_root",
    "plan_stack",
    "redact_text",
    "render_claude_model_routing",
    "render_claude_routing",
    "render_claude_settings",
    "render_codex_config",
    "render_launcher",
    "render_repoprompt_ce_launcher",
    "resolve_stack_paths",
    "rollback_transaction",
    "validate_installed_plan",
    "validate_packaged_policy",
]
