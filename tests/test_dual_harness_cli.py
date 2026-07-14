"""CLI coverage for the opt-in OpenLimits stack commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import cli
from src import dual_harness_global as stack


def _args(tmp_path: Path) -> list[str]:
    return [
        "install-openlimits-stack",
        "--claude-home",
        str(tmp_path / "claude"),
        "--codex-home",
        str(tmp_path / "codex"),
        "--launcher-dir",
        str(tmp_path / "bin"),
        "--backup-root",
        str(tmp_path / "backups"),
    ]


def test_preview_is_default_and_writes_nothing(capsys, tmp_path: Path) -> None:
    exit_code = cli.main(_args(tmp_path))
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Preview for OpenLimits dual-harness stack" in captured.out
    assert "Preview complete; no files or credentials were changed." in captured.out
    assert "openai/gpt-5.6-terra" not in captured.out
    assert not (tmp_path / "claude").exists()
    assert not (tmp_path / "codex").exists()


def test_conflict_preview_has_stable_validation_exit(capsys, tmp_path: Path) -> None:
    claude = tmp_path / "claude"
    claude.mkdir()
    (claude / "settings.json").write_text(
        json.dumps({"apiKeyHelper": "/tmp/custom"}), encoding="utf-8"
    )
    exit_code = cli.main(_args(tmp_path))
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "claude/settings.json: conflict" in captured.out
    assert "--resolve-conflicts" in captured.err


def test_apply_noop_and_rollback_paths(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(stack, "_default_credential_check", lambda _command: True)
    args = [*_args(tmp_path), "--apply"]
    assert cli.main(args) == 0
    first = capsys.readouterr()
    assert "Applied 12 managed destination(s)" in first.out
    transactions = list((tmp_path / "backups").glob("txn-*"))
    assert len(transactions) == 1
    transaction_id = transactions[0].name

    assert cli.main(args) == 0
    second = capsys.readouterr()
    assert "No-op" in second.out
    assert len(list((tmp_path / "backups").glob("txn-*"))) == 1

    rollback_args = [
        "install-openlimits-stack",
        "--backup-root",
        str(tmp_path / "backups"),
        "--rollback",
        transaction_id,
    ]
    assert cli.main(rollback_args) == 0
    rolled_back = capsys.readouterr()
    assert f"Rolled back transaction {transaction_id}" in rolled_back.out
    assert not (tmp_path / "claude" / "settings.json").exists()


def test_missing_keychain_is_redacted_and_prints_interactive_provisioning(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(stack, "_default_credential_check", lambda _command: False)
    exit_code = cli.main([*_args(tmp_path), "--apply"])
    captured = capsys.readouterr()
    assert exit_code == 3
    assert "service='OpenLimits', account='api-key'" in captured.err
    assert "add-generic-password" in captured.err
    assert captured.err.rstrip().endswith("-U -w")
    assert not (tmp_path / "backups").exists()


def test_legacy_plaintext_value_is_never_printed(capsys, tmp_path: Path) -> None:
    claude = tmp_path / "claude"
    claude.mkdir()
    token = "sk-never-print-this-token"
    (claude / "settings.json").write_text(
        json.dumps({"env": {"ANTHROPIC_AUTH_TOKEN": token}}), encoding="utf-8"
    )
    exit_code = cli.main([*_args(tmp_path), "--apply"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "credential-conflict" in captured.out
    assert token not in captured.out + captured.err
    assert not (tmp_path / "backups").exists()


def test_operational_error_has_stable_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    tmp_path: Path,
) -> None:
    def fail(_plan):
        raise stack.StackOperationalError("synthetic operational failure")

    monkeypatch.setattr(stack, "apply_stack", fail)
    exit_code = cli.main([*_args(tmp_path), "--apply"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "synthetic operational failure" in captured.err


def test_cli_has_no_raw_token_option(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main([*_args(tmp_path), "--api-key", "sk-do-not-accept"])
    assert excinfo.value.code == 2
