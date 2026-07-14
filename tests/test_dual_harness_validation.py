"""Tests for isolated, live-plan, and guided validation behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src import cli
from src import dual_harness_validation as validation


def test_isolated_canary_passes_without_readiness_or_secret_material() -> None:
    first = validation.run_isolated_canary()
    second = validation.run_isolated_canary()
    assert first.mode == "isolated"
    assert first.ready is False
    assert second.ready is False
    assert {row.status for row in first.rows} == {"pass", "unresolved"}
    assert next(row for row in first.rows if row.surface == "isolated-stack").status == (
        "pass"
    )
    serialized = first.to_json() + first.to_text()
    assert "CSE_FAKE_CREDENTIAL_VALUE" not in serialized
    assert "ANTHROPIC_AUTH_TOKEN" not in serialized
    assert "ANTHROPIC_API_KEY" not in serialized


def test_isolated_injected_failure_proves_rollback() -> None:
    report = validation.run_isolated_canary(inject_failure=True)
    row = next(
        row for row in report.rows if row.surface == "injected-failure-rollback"
    )
    assert row.status == "pass"
    assert "restored" in row.reason


def test_live_plan_names_provider_model_path_prompt_and_billing(tmp_path: Path) -> None:
    canaries = validation.build_live_canaries(
        claude_home=tmp_path / "claude",
        codex_home=tmp_path / "codex",
        launcher_dir=tmp_path / "bin",
    )
    assert [canary.surface for canary in canaries] == [
        "native-claude",
        "openlimits-claude",
        "openlimits-claude-rpce",
        "codex-cli",
    ]
    assert all(canary.prompt == validation.BOUNDED_PROMPT for canary in canaries)
    assert canaries[1].model == "anthropic/claude-sonnet-5"
    assert canaries[2].model == "anthropic/claude-sonnet-5"
    assert canaries[2].executable_path.endswith("claude-openlimits-rpce")
    assert canaries[3].model == "openai/gpt-5.6-terra"
    assert canaries[1].billing_destination == "OpenLimits Max"
    assert canaries[3].environment["CODEX_HOME"] == str(tmp_path / "codex")
    assert "--skip-git-repo-check" in canaries[3].command


def test_native_canary_scrubs_inherited_openlimits_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    inherited_keys = (
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    )
    for key in inherited_keys:
        monkeypatch.setenv(key, "must-not-reach-native-claude")
    canary = validation.build_live_canaries(
        claude_home=tmp_path / "claude",
        codex_home=tmp_path / "codex",
        launcher_dir=tmp_path / "bin",
    )[0]
    observed_environment: dict[str, str] = {}

    def succeed(*_args, **kwargs):
        observed_environment.update(kwargs["env"])
        return subprocess.CompletedProcess(canary.command, 0, stdout="ok", stderr="")

    validation.run_live_cli_canaries((canary,), runner=succeed)
    assert not inherited_keys & observed_environment.keys()


def test_successful_live_request_stays_unresolved_without_provider_evidence(
    tmp_path: Path,
) -> None:
    canary = validation.build_live_canaries(
        claude_home=tmp_path / "claude",
        codex_home=tmp_path / "codex",
        launcher_dir=tmp_path / "bin",
    )[3]

    def succeed(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            canary.command,
            0,
            stdout="CSE_CANARY_OK sk-output-secret-value",
            stderr="",
        )

    unresolved = validation.run_live_cli_canaries((canary,), runner=succeed)[0]
    assert unresolved.status == "unresolved"
    assert "billing attribution" in unresolved.reason
    assert "sk-output-secret-value" not in json.dumps(unresolved.__dict__)

    passed = validation.run_live_cli_canaries(
        (canary,),
        runner=succeed,
        provider_evidence={"codex-cli": "OpenLimits dashboard 2026-07-13T12:00Z"},
    )[0]
    assert passed.status == "pass"
    assert "dashboard" in passed.evidence_source


def test_secret_bearing_live_failure_is_redacted(tmp_path: Path) -> None:
    canary = validation.build_live_canaries(
        claude_home=tmp_path / "claude",
        codex_home=tmp_path / "codex",
        launcher_dir=tmp_path / "bin",
    )[0]

    def fail(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            canary.command,
            1,
            stdout="",
            stderr="Bearer sk-provider-secret-value was rejected",
        )

    row = validation.run_live_cli_canaries((canary,), runner=fail)[0]
    assert row.status == "fail"
    assert "sk-provider-secret-value" not in row.reason
    assert "[REDACTED]" in row.reason


def test_guided_steps_require_disposable_checkout_effective_home_and_ownership(
    tmp_path: Path,
) -> None:
    steps = " ".join(validation.guided_canary_steps(tmp_path / "codex"))
    assert "disposable checkout" in steps
    assert "sole writer" in steps
    assert f"CODEX_HOME={tmp_path / 'codex'}" in steps
    assert "codex app-server" in steps
    assert "user-observed" in steps


def test_waiver_is_distinct_from_pass_and_requires_reason() -> None:
    rows = validation.guided_unresolved_rows()
    waived = validation.apply_waivers(
        rows,
        {"codex-app": "User elected to defer the desktop canary"},
    )
    row = next(row for row in waived if row.surface == "codex-app")
    assert row.status == "waived"
    assert row.evidence_source == "explicit user waiver"
    assert row.reason == "User elected to defer the desktop canary"


def test_report_writer_is_redacted_and_private(tmp_path: Path) -> None:
    report = validation.ValidationReport(
        (
            validation.ValidationRow(
                "synthetic",
                "fail",
                "OpenLimits",
                "openai/gpt-5.6-terra",
                "OpenLimits Max",
                "automated stub",
                "Bearer sk-sensitive-report-token failed",
            ),
        ),
        "isolated",
    )
    target = tmp_path / "report.json"
    validation.write_report(report, target)
    text = target.read_text(encoding="utf-8")
    assert "sk-sensitive-report-token" not in text
    assert "[REDACTED]" in text
    assert target.stat().st_mode & 0o777 == 0o600


def test_validation_cli_defaults_to_no_network_isolated_mode(capsys) -> None:
    exit_code = cli.main(["validate-openlimits-stack"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "isolated-stack | pass" in captured.out
    assert "ready | no" in captured.out
    assert "Explicit live canary plan" not in captured.out


def test_validation_cli_rejects_malformed_evidence(capsys) -> None:
    exit_code = cli.main(
        ["validate-openlimits-stack", "--provider-evidence", "missing-equals"]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "SURFACE=VALUE" in captured.err


def test_live_cli_displays_every_request_before_injected_execution(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    tmp_path: Path,
) -> None:
    def pass_canaries(canaries, **_kwargs):
        return tuple(
            validation.ValidationRow(
                canary.surface,
                "pass",
                canary.provider,
                canary.model,
                canary.billing_destination,
                "injected provider dashboard evidence",
                "bounded request and attribution passed",
            )
            for canary in canaries
        )

    monkeypatch.setattr(validation, "run_live_cli_canaries", pass_canaries)
    exit_code = cli.main(
        [
            "validate-openlimits-stack",
            "--live",
            "--claude-home",
            str(tmp_path / "claude"),
            "--codex-home",
            str(tmp_path / "codex"),
            "--launcher-dir",
            str(tmp_path / "bin"),
            "--waive",
            "codex-app=desktop canary deferred",
            "--waive",
            "claude-codex-plugin=plugin canary deferred",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.index("Explicit live canary plan") < captured.out.index(
        "Validation matrix"
    )
    assert "surface=native-claude provider=Anthropic native" in captured.out
    assert "surface=openlimits-claude provider=OpenLimits" in captured.out
    assert "surface=openlimits-claude-rpce provider=OpenLimits + RepoPrompt CE" in captured.out
    assert "surface=codex-cli provider=OpenLimits" in captured.out
    assert "model=openai/gpt-5.6-terra" in captured.out
    assert "billing=OpenLimits Max" in captured.out
    assert validation.BOUNDED_PROMPT in captured.out
    assert "Guided app/plugin canaries (user-recorded evidence)" in captured.out
    assert "ready | yes" in captured.out
