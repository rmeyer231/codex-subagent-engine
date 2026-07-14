"""Tests for dual-harness planning, apply, and rollback."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import tomlkit

from src import dual_harness_global as stack


TARGET_KEYS = (
    "codex/config.toml",
    "codex/AGENTS.md",
    "codex/model-routing.md",
    "codex/agents/cse_explorer.toml",
    "codex/agents/cse_planner.toml",
    "codex/agents/cse_implementer.toml",
    "codex/agents/cse_reviewer.toml",
    "claude/settings.json",
    "claude/CLAUDE.md",
    "claude/model-routing.md",
    "launcher/claude-openlimits",
    "launcher/claude-openlimits-rpce",
)
FAILURE_BOUNDARIES = tuple(
    event
    for key in TARGET_KEYS
    for event in (f"before_write:{key}", f"after_write:{key}")
) + ("before_validate", "after_validate")


def _paths(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    return (
        tmp_path / "claude-home",
        tmp_path / "codex-home",
        tmp_path / "bin",
        tmp_path / "transactions",
    )


def _plan(tmp_path: Path, **kwargs) -> stack.StackPlan:
    claude, codex, launcher, backups = _paths(tmp_path)
    return stack.plan_stack(
        claude_home=claude,
        codex_home=codex,
        launcher_dir=launcher,
        backup_root=backups,
        credential_command=(str(tmp_path / "fake-credential"), "--print"),
        claude_command=(str(tmp_path / "fake-claude"),),
        repoprompt_ce_command=(str(tmp_path / "fake-claude-rpce"),),
        **kwargs,
    )


def test_plan_uses_alternate_roots_without_writes_or_credential_execution(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    claude, codex, launcher, backups = _paths(tmp_path)
    assert plan.claude_home == claude
    assert plan.codex_home == codex
    assert plan.launcher_dir == launcher
    assert plan.backup_root == backups
    assert [target.key for target in plan.targets] == list(TARGET_KEYS)
    assert all(target.action == "create" for target in plan.targets)
    assert not claude.exists()
    assert not codex.exists()
    assert not launcher.exists()
    assert not backups.exists()


def test_plan_preserves_unrelated_claude_and_codex_configuration(
    tmp_path: Path,
) -> None:
    claude, codex, launcher, _ = _paths(tmp_path)
    claude.mkdir()
    codex.mkdir()
    launcher.mkdir()
    (claude / "settings.json").write_text(
        json.dumps(
            {
                "env": {
                    "ANTHROPIC_BASE_URL": "https://openlimits.app",
                    "ANTHROPIC_DEFAULT_SONNET_MODEL": "old-model",
                    "KEEP_ME": "yes",
                },
                "enabledPlugins": {"codex@openai-codex": True},
                "hooks": {"Stop": ["keep"]},
                "mcpServers": {"example": {"command": "example"}},
            }
        ),
        encoding="utf-8",
    )
    (claude / "CLAUDE.md").write_text("user prose\n", encoding="utf-8")
    (claude / "model-routing.md").write_text("user model note\n", encoding="utf-8")
    (codex / "config.toml").write_text(
        '[model_providers.other]\nname = "Other"\n\n'
        '[projects."/tmp/project"]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )

    plan = _plan(tmp_path)
    settings = json.loads(
        next(t.rendered for t in plan.targets if t.key == "claude/settings.json")
    )
    assert settings["env"] == {"KEEP_ME": "yes"}
    assert settings["enabledPlugins"] == {"codex@openai-codex": True}
    assert settings["hooks"] == {"Stop": ["keep"]}
    assert settings["mcpServers"]["example"]["command"] == "example"
    assert "user prose" in next(
        t.rendered for t in plan.targets if t.key == "claude/CLAUDE.md"
    )
    assert "user model note" in next(
        t.rendered for t in plan.targets if t.key == "claude/model-routing.md"
    )
    codex_doc = tomlkit.parse(
        next(t.rendered for t in plan.targets if t.key == "codex/config.toml")
    )
    assert codex_doc["model_providers"]["other"]["name"] == "Other"
    assert codex_doc["projects"]["/tmp/project"]["trust_level"] == "trusted"


def test_codex_provider_render_is_a_fixed_point_with_following_plugin_table() -> None:
    existing = (
        '[model_providers.openlimits]\nname = "Old OpenLimits"\n'
        'base_url = "https://old.example/v1"\nenv_key = "OPENAI_API_KEY"\n'
        'wire_api = "responses"\n\n'
        '[plugins."example"]\nenabled = true\nmodel_provider = "openlimits"\n'
    )
    first = stack.render_codex_config(
        existing,
        keychain_service="OpenLimits",
        keychain_account="api-key",
    )
    second = stack.render_codex_config(
        first,
        keychain_service="OpenLimits",
        keychain_account="api-key",
    )
    assert first == second
    document = tomlkit.parse(first)
    assert document["plugins"]["example"]["enabled"] is True
    assert "env_key" not in document["model_providers"]["openlimits"]


def test_codex_provider_splits_custom_credential_command_into_command_and_args() -> None:
    rendered = stack.render_codex_config(
        "",
        keychain_service="unused",
        keychain_account="unused",
        credential_command=("/tmp/helper with spaces", "--account", "api-key"),
    )
    auth = tomlkit.parse(rendered)["model_providers"]["openlimits"]["auth"]
    assert auth["command"] == "/tmp/helper with spaces"
    assert list(auth["args"]) == ["--account", "api-key"]


def test_api_key_helper_and_existing_launcher_require_explicit_resolution(
    tmp_path: Path,
) -> None:
    claude, _, launcher, _ = _paths(tmp_path)
    claude.mkdir()
    launcher.mkdir()
    (claude / "settings.json").write_text(
        json.dumps({"apiKeyHelper": "/tmp/custom-helper"}), encoding="utf-8"
    )
    (launcher / "claude-openlimits").write_text("#!/bin/sh\nexit 4\n", encoding="utf-8")
    (launcher / "claude-openlimits-rpce").write_text(
        "#!/bin/sh\nexit 5\n", encoding="utf-8"
    )

    preview = _plan(tmp_path)
    assert {target.key for target in preview.conflicts} == {
        "claude/settings.json",
        "launcher/claude-openlimits",
        "launcher/claude-openlimits-rpce",
    }
    resolved = _plan(tmp_path, resolve_conflicts=True)
    assert not resolved.conflicts
    settings = json.loads(
        next(t.rendered for t in resolved.targets if t.key == "claude/settings.json")
    )
    assert "apiKeyHelper" not in settings


def test_plaintext_credential_blocks_apply_before_backup_or_write(tmp_path: Path) -> None:
    claude, _, _, backups = _paths(tmp_path)
    claude.mkdir()
    settings_path = claude / "settings.json"
    original = json.dumps(
        {"env": {"ANTHROPIC_AUTH_TOKEN": "sk-super-secret-value"}}
    )
    settings_path.write_text(original, encoding="utf-8")
    plan = _plan(tmp_path)
    assert plan.legacy_credential_paths == (
        "claude/settings.json:env.ANTHROPIC_AUTH_TOKEN",
    )
    with pytest.raises(stack.StackCredentialError) as excinfo:
        stack.apply_stack(plan, credential_checker=lambda _command: True)
    assert "sk-super-secret-value" not in str(excinfo.value)
    assert settings_path.read_text(encoding="utf-8") == original
    assert not backups.exists()


def test_missing_keychain_blocks_apply_without_mutation(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    with pytest.raises(stack.StackCredentialError) as excinfo:
        stack.apply_stack(plan, credential_checker=lambda _command: False)
    assert "service='OpenLimits'" in str(excinfo.value)
    assert not plan.backup_root.exists()
    assert all(not target.path.exists() for target in plan.targets)


def test_raw_token_credential_command_is_rejected_during_planning(
    tmp_path: Path,
) -> None:
    claude, codex, launcher, backups = _paths(tmp_path)
    with pytest.raises(stack.StackValidationError, match="not a raw token"):
        stack.plan_stack(
            claude_home=claude,
            codex_home=codex,
            launcher_dir=launcher,
            backup_root=backups,
            credential_command=("credential-helper", "sk-raw-token-value"),
        )
    assert not backups.exists()


def test_apply_is_idempotent_and_explicit_rollback_restores_prior_state(
    tmp_path: Path,
) -> None:
    claude, codex, launcher, backups = _paths(tmp_path)
    claude.mkdir()
    codex.mkdir()
    launcher.mkdir()
    settings_path = claude / "settings.json"
    config_path = codex / "config.toml"
    launcher_path = launcher / "claude-openlimits"
    repoprompt_launcher_path = launcher / "claude-openlimits-rpce"
    settings_original = '{"theme": "dark"}\n'
    config_original = '[projects."/tmp/example"]\ntrust_level = "trusted"\n'
    launcher_original = "#!/bin/sh\nexit 9\n"
    repoprompt_launcher_original = "#!/bin/sh\nexit 10\n"
    settings_path.write_text(settings_original, encoding="utf-8")
    config_path.write_text(config_original, encoding="utf-8")
    launcher_path.write_text(launcher_original, encoding="utf-8")
    launcher_path.chmod(0o700)
    repoprompt_launcher_path.write_text(
        repoprompt_launcher_original, encoding="utf-8"
    )
    repoprompt_launcher_path.chmod(0o700)

    first = _plan(tmp_path, resolve_conflicts=True)
    result = stack.apply_stack(first, credential_checker=lambda _command: True)
    assert result.changed is True
    assert result.transaction_id
    assert launcher_path.stat().st_mode & 0o777 == 0o755
    assert repoprompt_launcher_path.stat().st_mode & 0o777 == 0o755
    assert not first.legacy_credential_paths

    second = _plan(tmp_path, resolve_conflicts=True)
    assert not second.changes
    no_op = stack.apply_stack(second, credential_checker=lambda _command: True)
    assert no_op.changed is False
    assert len(list(backups.glob("txn-*"))) == 1

    rolled_back = stack.rollback_transaction(
        result.transaction_id or "",
        backup_root=backups,
    )
    assert rolled_back.changed is True
    assert settings_path.read_text(encoding="utf-8") == settings_original
    assert config_path.read_text(encoding="utf-8") == config_original
    assert launcher_path.read_text(encoding="utf-8") == launcher_original
    assert launcher_path.stat().st_mode & 0o777 == 0o700
    assert (
        repoprompt_launcher_path.read_text(encoding="utf-8")
        == repoprompt_launcher_original
    )
    assert repoprompt_launcher_path.stat().st_mode & 0o777 == 0o700
    assert not (claude / "CLAUDE.md").exists()
    assert not (codex / "AGENTS.md").exists()


@pytest.mark.parametrize("boundary", FAILURE_BOUNDARIES)
def test_every_write_and_validation_boundary_rolls_back(
    boundary: str,
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)

    def fail(selected: str) -> None:
        if selected == boundary:
            raise RuntimeError("simulated failure with sk-secret-value")

    with pytest.raises(stack.StackOperationalError) as excinfo:
        stack.apply_stack(
            plan,
            credential_checker=lambda _command: True,
            failure_hook=fail,
        )
    assert "sk-secret-value" not in str(excinfo.value)
    assert "[REDACTED]" in str(excinfo.value)
    assert all(not target.path.exists() for target in plan.targets)
    transactions = list(plan.backup_root.glob("txn-*"))
    assert len(transactions) == 1
    manifest = json.loads(
        (transactions[0] / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "auto_rolled_back"
    assert manifest["failure_boundary"] == boundary


def test_plan_recheck_detects_change_after_preview(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    settings = next(target for target in plan.targets if target.key == "claude/settings.json")
    settings.path.parent.mkdir(parents=True)
    settings.path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(stack.StackConflictError, match="changed after preview"):
        stack.apply_stack(plan, credential_checker=lambda _command: True)
    assert not plan.backup_root.exists()


def test_automatic_rollback_failure_is_explicit_and_retains_backups(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)

    def fail_restore(_transaction, _records):
        raise stack.StackOperationalError("Rollback failed for synthetic target")

    monkeypatch.setattr(stack, "_restore_records", fail_restore)

    def fail_after_first(event: str) -> None:
        if event == "after_write:codex/config.toml":
            raise RuntimeError("write boundary failure")

    with pytest.raises(stack.StackOperationalError, match="backups retained"):
        stack.apply_stack(
            plan,
            credential_checker=lambda _command: True,
            failure_hook=fail_after_first,
        )
    assert len(list(plan.backup_root.glob("txn-*"))) == 1
