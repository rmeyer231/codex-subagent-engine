"""Isolated and explicitly gated live validation for the OpenLimits stack."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from src import dual_harness_global as stack

VALID_STATUSES: Final[tuple[str, ...]] = ("pass", "fail", "unresolved", "waived")
BOUNDED_PROMPT: Final[str] = "Reply with exactly CSE_CANARY_OK and no other text."
NATIVE_CLAUDE_UNSET_ENV: Final[tuple[str, ...]] = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
)


@dataclass(frozen=True)
class ValidationRow:
    """One redacted surface result in the validation matrix."""

    surface: str
    status: str
    provider: str
    model: str
    billing_destination: str
    evidence_source: str
    reason: str
    remediation: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid validation status: {self.status}")
        if not self.evidence_source:
            raise ValueError("every validation row requires an evidence source")
        if self.status in {"unresolved", "waived", "fail"} and not self.reason:
            raise ValueError(f"{self.status} validation rows require a reason")


@dataclass(frozen=True)
class ValidationReport:
    """Redacted validation matrix and readiness conclusion."""

    rows: tuple[ValidationRow, ...]
    mode: str

    @property
    def ready(self) -> bool:
        required = {
            "isolated-stack",
            "native-claude",
            "openlimits-claude",
            "openlimits-claude-rpce",
            "codex-cli",
            "codex-app",
            "claude-codex-plugin",
        }
        by_surface = {row.surface: row for row in self.rows}
        return required <= set(by_surface) and all(
            by_surface[surface].status in {"pass", "waived"}
            for surface in required
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "ready": self.ready,
            "rows": [
                {
                    key: stack.redact_text(value)
                    for key, value in asdict(row).items()
                }
                for row in self.rows
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2) + "\n"

    def to_text(self) -> str:
        lines = [
            "Validation matrix:",
            "surface | status | provider | model | billing | evidence | reason",
        ]
        for row in self.rows:
            values = (
                row.surface,
                row.status,
                row.provider,
                row.model,
                row.billing_destination,
                row.evidence_source,
                row.reason or "-",
            )
            lines.append(" | ".join(stack.redact_text(value) for value in values))
        lines.append(f"ready | {'yes' if self.ready else 'no'}")
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class LiveCanary:
    """One bounded, explicitly approved CLI request."""

    surface: str
    provider: str
    model: str
    billing_destination: str
    executable_path: str
    command: tuple[str, ...]
    environment: Mapping[str, str]
    unset_environment: tuple[str, ...] = ()
    prompt: str = BOUNDED_PROMPT


def _write_stub_scripts(root: Path, evidence: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    credential = root / "credential.py"
    credential.write_text("print('CSE_FAKE_CREDENTIAL_VALUE')\n", encoding="utf-8")
    claude = root / "claude.py"
    claude.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(sys.argv[1]).write_text(json.dumps({\n"
        "  'args': sys.argv[2:],\n"
        "  'base_url': os.environ.get('ANTHROPIC_BASE_URL'),\n"
        "  'token_present': bool(os.environ.get('ANTHROPIC_API_KEY')),\n"
        "  'opus': os.environ.get('ANTHROPIC_DEFAULT_OPUS_MODEL'),\n"
        "  'sonnet': os.environ.get('ANTHROPIC_DEFAULT_SONNET_MODEL'),\n"
        "  'haiku': os.environ.get('ANTHROPIC_DEFAULT_HAIKU_MODEL'),\n"
        "}))\n",
        encoding="utf-8",
    )
    return (sys.executable, str(credential)), (sys.executable, str(claude), str(evidence))


def run_isolated_canary(*, inject_failure: bool = False) -> ValidationReport:
    """Run a no-network canary entirely inside a temporary directory."""
    rows: list[ValidationRow] = []
    with tempfile.TemporaryDirectory(prefix="cse-openlimits-canary-") as temporary:
        root = Path(temporary)
        evidence = root / "launcher-evidence.json"
        credential_command, claude_command = _write_stub_scripts(root, evidence)
        plan = stack.plan_stack(
            claude_home=root / "claude",
            codex_home=root / "codex",
            launcher_dir=root / "bin",
            backup_root=root / "transactions",
            credential_command=credential_command,
            claude_command=claude_command,
            repoprompt_ce_command=claude_command,
        )
        result = stack.apply_stack(plan)
        launcher = root / "bin" / "claude-openlimits"
        completed = subprocess.run(
            [str(launcher), "--probe", "value with spaces"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if completed.returncode != 0:
            raise stack.StackOperationalError(
                f"Isolated launcher failed: {stack.redact_text(completed.stderr)}"
            )
        observed = json.loads(evidence.read_text(encoding="utf-8"))
        policy = stack.load_policy()
        expected_models = policy["models"]["claude"]
        assert observed == {
            "args": ["--probe", "value with spaces"],
            "base_url": "https://openlimits.app",
            "token_present": True,
            "opus": expected_models["architecture"],
            "sonnet": expected_models["implementation"],
            "haiku": expected_models["low_stakes"],
        }
        repoprompt_launcher = root / "bin" / "claude-openlimits-rpce"
        completed = subprocess.run(
            [str(repoprompt_launcher), "--rpce-probe", "value with spaces"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if completed.returncode != 0:
            raise stack.StackOperationalError(
                "Isolated RepoPrompt CE launcher failed: "
                f"{stack.redact_text(completed.stderr)}"
            )
        observed = json.loads(evidence.read_text(encoding="utf-8"))
        assert observed["args"] == ["--rpce-probe", "value with spaces"]
        assert observed["base_url"] == "https://openlimits.app"
        assert observed["token_present"] is True
        second = stack.plan_stack(
            claude_home=root / "claude",
            codex_home=root / "codex",
            launcher_dir=root / "bin",
            backup_root=root / "transactions",
            credential_command=credential_command,
            claude_command=claude_command,
            repoprompt_ce_command=claude_command,
        )
        if second.changes:
            raise stack.StackOperationalError("Isolated second apply was not a no-op")
        stack.rollback_transaction(
            result.transaction_id or "",
            backup_root=root / "transactions",
        )
        if any(target.path.exists() for target in plan.targets):
            raise stack.StackOperationalError("Isolated rollback left managed targets")
        rows.append(
            ValidationRow(
                "isolated-stack",
                "pass",
                "stubbed native + OpenLimits",
                "canonical policy",
                "none (no network)",
                "automated temporary-home canary",
                "plan, merge, both launchers, idempotence, and rollback passed",
            )
        )
        rows.append(
            ValidationRow(
                "credential-redaction",
                "pass",
                "fake command-backed credential",
                "not applicable",
                "none (no network)",
                "automated report and evidence scan",
                "fake credential value absent from report and launcher evidence",
            )
        )

        if inject_failure:
            failure_plan = stack.plan_stack(
                claude_home=root / "failure-claude",
                codex_home=root / "failure-codex",
                launcher_dir=root / "failure-bin",
                backup_root=root / "failure-transactions",
                credential_command=credential_command,
                claude_command=claude_command,
                repoprompt_ce_command=claude_command,
            )

            def fail(event: str) -> None:
                if event == "after_write:codex/config.toml":
                    raise RuntimeError("injected canary failure")

            try:
                stack.apply_stack(failure_plan, failure_hook=fail)
            except stack.StackOperationalError:
                pass
            else:
                raise stack.StackOperationalError("Injected failure unexpectedly succeeded")
            if any(target.path.exists() for target in failure_plan.targets):
                raise stack.StackOperationalError("Injected failure rollback left targets")
            rows.append(
                ValidationRow(
                    "injected-failure-rollback",
                    "pass",
                    "stubbed OpenLimits",
                    "canonical policy",
                    "none (no network)",
                    "automated injected write-boundary failure",
                    "all earlier mutations were restored",
                )
            )

    rows.extend(guided_unresolved_rows())
    report = ValidationReport(tuple(rows), "isolated")
    serialized = report.to_json() + report.to_text()
    if "CSE_FAKE_CREDENTIAL_VALUE" in serialized:
        raise stack.StackOperationalError("Isolated report contains credential material")
    return report


def build_live_canaries(
    *,
    claude_home: Path,
    codex_home: Path,
    launcher_dir: Path,
) -> tuple[LiveCanary, ...]:
    """Build bounded CLI requests; constructing the plan performs no request."""
    policy = stack.load_policy()
    prompt = BOUNDED_PROMPT
    environment = {
        "CLAUDE_CONFIG_DIR": str(claude_home),
        "CODEX_HOME": str(codex_home),
    }
    return (
        LiveCanary(
            "native-claude",
            "Anthropic native",
            "native subscription selection",
            "Claude Pro",
            "claude",
            ("claude", "-p", prompt, "--output-format", "json"),
            environment,
            unset_environment=NATIVE_CLAUDE_UNSET_ENV,
        ),
        LiveCanary(
            "openlimits-claude",
            "OpenLimits",
            policy["models"]["claude"]["implementation"],
            "OpenLimits Max",
            str(launcher_dir / "claude-openlimits"),
            (
                str(launcher_dir / "claude-openlimits"),
                "-p",
                prompt,
                "--output-format",
                "json",
            ),
            environment,
        ),
        LiveCanary(
            "openlimits-claude-rpce",
            "OpenLimits + RepoPrompt CE",
            policy["models"]["claude"]["implementation"],
            "OpenLimits Max",
            str(launcher_dir / "claude-openlimits-rpce"),
            (
                str(launcher_dir / "claude-openlimits-rpce"),
                "-p",
                prompt,
                "--output-format",
                "json",
            ),
            environment,
        ),
        LiveCanary(
            "codex-cli",
            "OpenLimits",
            policy["defaults"]["codex_model"],
            "OpenLimits Max",
            "codex",
            (
                "codex",
                "exec",
                "--skip-git-repo-check",
                "--model",
                policy["defaults"]["codex_model"],
                "--json",
                prompt,
            ),
            environment,
        ),
    )


def run_live_cli_canaries(
    canaries: tuple[LiveCanary, ...],
    *,
    provider_evidence: Mapping[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[ValidationRow, ...]:
    """Execute only the supplied, already displayed live CLI canary plan."""
    evidence = provider_evidence or {}
    rows: list[ValidationRow] = []
    for canary in canaries:
        environment = {**os.environ, **canary.environment}
        for key in canary.unset_environment:
            environment.pop(key, None)
        try:
            completed = runner(
                canary.command,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            rows.append(
                ValidationRow(
                    canary.surface,
                    "fail",
                    canary.provider,
                    canary.model,
                    canary.billing_destination,
                    "automated bounded CLI invocation",
                    stack.redact_text(exc),
                    "verify the executable, authentication, and provider configuration",
                )
            )
            continue
        if completed.returncode != 0:
            rows.append(
                ValidationRow(
                    canary.surface,
                    "fail",
                    canary.provider,
                    canary.model,
                    canary.billing_destination,
                    "automated bounded CLI invocation",
                    stack.redact_text(completed.stderr or "nonzero exit"),
                    "review redacted provider diagnostics",
                )
            )
            continue
        source = evidence.get(canary.surface)
        status = "pass" if source else "unresolved"
        reason = (
            "bounded request plus provider-side attribution recorded"
            if source
            else "bounded request succeeded but billing attribution was not recorded"
        )
        rows.append(
            ValidationRow(
                canary.surface,
                status,
                canary.provider,
                canary.model,
                canary.billing_destination,
                source or "automated CLI exit only",
                reason,
                "record a non-secret provider dashboard timestamp or request identifier"
                if not source
                else "",
            )
        )
    return tuple(rows)


def guided_unresolved_rows() -> tuple[ValidationRow, ...]:
    """Return user-observed app/plugin checks that automation must not infer."""
    policy = stack.load_policy()
    model = policy["defaults"]["codex_model"]
    return (
        ValidationRow(
            "native-claude",
            "unresolved",
            "Anthropic native",
            "native subscription selection",
            "Claude Pro",
            "not run in isolated mode",
            "requires an explicitly approved live request",
        ),
        ValidationRow(
            "openlimits-claude",
            "unresolved",
            "OpenLimits",
            policy["models"]["claude"]["implementation"],
            "OpenLimits Max",
            "not run in isolated mode",
            "requires an explicitly approved live request",
        ),
        ValidationRow(
            "openlimits-claude-rpce",
            "unresolved",
            "OpenLimits + RepoPrompt CE",
            policy["models"]["claude"]["implementation"],
            "OpenLimits Max",
            "not run in isolated mode",
            "requires an explicitly approved live request through RepoPrompt CE",
        ),
        ValidationRow(
            "codex-cli",
            "unresolved",
            "OpenLimits",
            model,
            "OpenLimits Max",
            "not run in isolated mode",
            "requires an explicitly approved live request",
        ),
        ValidationRow(
            "codex-app",
            "unresolved",
            "OpenLimits",
            model,
            "OpenLimits Max",
            "user-recorded disposable-checkout canary",
            "open Codex App with the effective CODEX_HOME and sole-writer ownership",
        ),
        ValidationRow(
            "claude-codex-plugin",
            "unresolved",
            "OpenLimits via codex app-server",
            model,
            "OpenLimits Max",
            "user-recorded read-only plugin canary",
            "record effective CODEX_HOME and confirm no nested CSE delegation",
        ),
    )


def guided_canary_steps(codex_home: Path) -> tuple[str, ...]:
    """Return explicit user-observed checks for app and plugin surfaces."""
    return (
        "Codex App: create a disposable checkout, declare Codex App the sole writer, "
        f"open it with effective CODEX_HOME={codex_home}, run the bounded prompt, and "
        "record the non-secret provider/model plus OpenLimits dashboard attribution.",
        "Claude Codex plugin: in a disposable checkout with Claude retaining ownership, "
        f"record effective CODEX_HOME={codex_home}, delegate one bounded read-only task "
        "through codex app-server, confirm no nested CSE delegation, and record user-observed "
        "provider/dashboard evidence.",
    )


def apply_waivers(
    rows: tuple[ValidationRow, ...],
    waivers: Mapping[str, str],
) -> tuple[ValidationRow, ...]:
    """Apply explicit user waivers without converting them into passes."""
    output: list[ValidationRow] = []
    for row in rows:
        reason = waivers.get(row.surface)
        if reason:
            output.append(
                ValidationRow(
                    row.surface,
                    "waived",
                    row.provider,
                    row.model,
                    row.billing_destination,
                    "explicit user waiver",
                    reason,
                    row.remediation,
                )
            )
        else:
            output.append(row)
    return tuple(output)


def write_report(report: ValidationReport, path: Path) -> None:
    """Write a redacted JSON report atomically."""
    stack._atomic_write(path, report.to_json(), 0o600)


__all__ = [
    "BOUNDED_PROMPT",
    "LiveCanary",
    "ValidationReport",
    "ValidationRow",
    "apply_waivers",
    "build_live_canaries",
    "guided_canary_steps",
    "guided_unresolved_rows",
    "run_isolated_canary",
    "run_live_cli_canaries",
    "write_report",
]
