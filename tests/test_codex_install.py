"""Focused tests for the safe global Codex installer."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src import codex_global


EXPECTED_PATHS = (
    Path("config.toml"),
    Path("AGENTS.md"),
    Path("model-routing.md"),
    Path("agents/cse_explorer.toml"),
    Path("agents/cse_planner.toml"),
    Path("agents/cse_implementer.toml"),
    Path("agents/cse_reviewer.toml"),
)


def test_resolve_codex_home_precedence_and_normalization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    explicit = tmp_path / "explicit" / ".." / "chosen"
    env_home = tmp_path / "environment"
    monkeypatch.setenv("CODEX_HOME", str(env_home))

    assert codex_global.resolve_codex_home(explicit) == Path(
        os.path.abspath(explicit.expanduser())
    )
    assert codex_global.resolve_codex_home(environ=os.environ) == env_home

    monkeypatch.delenv("CODEX_HOME")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    assert codex_global.resolve_codex_home() == tmp_path / "home" / ".codex"


def test_plan_is_deterministic_and_does_not_create_target(tmp_path: Path) -> None:
    target = tmp_path / "missing" / "codex-home"

    plan = codex_global.plan_install(target)

    assert not target.exists()
    assert tuple(entry.relative_path for entry in plan.entries) == EXPECTED_PATHS
    assert {entry.action for entry in plan.entries} == {"create"}
    assert all(str(target) not in entry.summary for entry in plan.entries)


def test_plan_preserves_unrelated_config_and_comments(tmp_path: Path) -> None:
    target = tmp_path / "codex"
    target.mkdir()
    original = (
        "# keep this comment\n"
        'model = "secret-model" # keep inline\n\n'
        "[agents]\n"
        "max_threads = 99 # replace value, keep comment\n"
        'unrelated = "keep"\n\n'
        "[mcp_servers.private]\n"
        'token_env_var = "TOP_SECRET"\n'
    )
    (target / "config.toml").write_text(original, encoding="utf-8")

    plan = codex_global.plan_install(target)
    rendered = plan.content_for(Path("config.toml"))

    assert "# keep this comment" in rendered
    assert 'model = "secret-model" # keep inline' in rendered
    assert 'unrelated = "keep"' in rendered
    assert '[mcp_servers.private]' in rendered
    assert 'token_env_var = "TOP_SECRET"' in rendered
    assert "max_threads = 4 # replace value, keep comment" in rendered
    assert "max_depth = 1" in rendered
    assert "job_max_runtime_seconds = 1800" in rendered
    assert "interrupt_message = true" in rendered


def test_pooler_provider_and_mcp_survive_preview_apply_and_noop(
    tmp_path: Path,
) -> None:
    target = tmp_path / "codex"
    target.mkdir()
    config_path = target / "config.toml"
    config_path.write_text(
        'model_provider = "openlimits"\n\n'
        "[model_providers.openlimits]\n"
        'name = "OpenAI"\n'
        'base_url = "https://openlimits.invalid/v1"\n'
        'env_key = "OPENLIMITS_API_KEY"\n'
        'wire_api = "responses"\n\n'
        "[model_providers.codex-pooler-ws]\n"
        'name = "OpenAI"\n'
        'base_url = "https://pooler.invalid/backend-api/codex"\n'
        'env_key = "CODEX_POOLER_API_KEY"\n'
        'wire_api = "responses"\n'
        "supports_websockets = true\n"
        "requires_openai_auth = true\n\n"
        "[mcp_servers.codex_pooler]\n"
        'url = "https://pooler.invalid/mcp"\n'
        'bearer_token_env_var = "CODEX_POOLER_MCP_KEY"\n\n'
        "[agents]\n"
        "max_threads = 99\n",
        encoding="utf-8",
    )

    def assert_unrelated_config_is_preserved(text: str) -> None:
        doc = codex_global._parse_toml(text, "test Pooler config")
        assert doc["model_provider"] == "openlimits"
        assert doc["model_providers"]["openlimits"] == {
            "name": "OpenAI",
            "base_url": "https://openlimits.invalid/v1",
            "env_key": "OPENLIMITS_API_KEY",
            "wire_api": "responses",
        }
        assert doc["model_providers"]["codex-pooler-ws"] == {
            "name": "OpenAI",
            "base_url": "https://pooler.invalid/backend-api/codex",
            "env_key": "CODEX_POOLER_API_KEY",
            "wire_api": "responses",
            "supports_websockets": True,
            "requires_openai_auth": True,
        }
        assert doc["mcp_servers"]["codex_pooler"] == {
            "url": "https://pooler.invalid/mcp",
            "bearer_token_env_var": "CODEX_POOLER_MCP_KEY",
        }

    first_plan = codex_global.plan_install(target)
    assert_unrelated_config_is_preserved(first_plan.content_for(Path("config.toml")))

    first_result = codex_global.apply_plan(first_plan)
    assert first_result.changed is True
    assert_unrelated_config_is_preserved(config_path.read_text(encoding="utf-8"))

    second_plan = codex_global.plan_install(target)
    assert {entry.action for entry in second_plan.entries} == {"no-op"}
    second_result = codex_global.apply_plan(second_plan)
    assert second_result.changed is False
    assert second_result.backup_directory is None


def test_plan_appends_then_replaces_only_managed_agents_block(tmp_path: Path) -> None:
    target = tmp_path / "codex"
    target.mkdir()
    agents_path = target / "AGENTS.md"
    agents_path.write_text("user prefix\nuser suffix\n", encoding="utf-8")

    first = codex_global.plan_install(target)
    first_rendered = first.content_for(Path("AGENTS.md"))
    assert first_rendered.startswith("user prefix\nuser suffix\n\n")
    assert first_rendered.count(codex_global.BEGIN_MARKER) == 1
    assert first_rendered.count(codex_global.END_MARKER) == 1

    agents_path.write_text(
        "user prefix\n"
        f"{codex_global.BEGIN_MARKER}\nold managed text\n{codex_global.END_MARKER}\n"
        "user suffix\n",
        encoding="utf-8",
    )
    second = codex_global.plan_install(target)
    second_rendered = second.content_for(Path("AGENTS.md"))
    assert second_rendered.startswith("user prefix\n")
    assert second_rendered.endswith("\nuser suffix\n")
    assert "old managed text" not in second_rendered


@pytest.mark.parametrize(
    "broken",
    [
        "prefix\n<!-- BEGIN CSE-MANAGED -->\n",
        "prefix\n<!-- END CSE-MANAGED -->\n",
        (
            "<!-- BEGIN CSE-MANAGED -->\n<!-- BEGIN CSE-MANAGED -->\n"
            "<!-- END CSE-MANAGED -->\n"
        ),
        "<!-- END CSE-MANAGED -->\n<!-- BEGIN CSE-MANAGED -->\n",
    ],
)
def test_plan_rejects_malformed_target_markers(tmp_path: Path, broken: str) -> None:
    target = tmp_path / "codex"
    target.mkdir()
    (target / "AGENTS.md").write_text(broken, encoding="utf-8")

    with pytest.raises(codex_global.InstallValidationError, match="AGENTS.md"):
        codex_global.plan_install(target)


def test_model_routing_requires_explicit_force_to_replace(tmp_path: Path) -> None:
    target = tmp_path / "codex"
    target.mkdir()
    (target / "model-routing.md").write_text("user-owned routing\n", encoding="utf-8")

    blocked = codex_global.plan_install(target)
    model_entry = blocked.entry_for(Path("model-routing.md"))
    assert model_entry.action == "conflict"
    assert "force-model-routing" in model_entry.reason

    forced = codex_global.plan_install(target, force_model_routing=True)
    assert forced.entry_for(Path("model-routing.md")).action == "update"


def test_template_validation_stops_before_target_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "codex"
    original_loader = codex_global.load_template

    def invalid_loader(resource: str) -> str:
        if resource == "agents/cse_explorer.toml":
            return 'name = "wrong"\n'
        return original_loader(resource)

    monkeypatch.setattr(codex_global, "load_template", invalid_loader)

    with pytest.raises(codex_global.InstallValidationError, match="cse_explorer"):
        codex_global.plan_install(target)
    assert not target.exists()


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        (field, invalid_value)
        for field in ("name", "description", "developer_instructions", "sandbox_mode")
        for invalid_value in (["not-a-string"], 7, True)
    ],
)
def test_agent_required_fields_must_be_non_empty_strings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    invalid_value: object,
) -> None:
    target = tmp_path / "codex"
    original_loader = codex_global.load_template
    invalid_doc = codex_global._parse_toml(
        original_loader("agents/cse_explorer.toml"),
        "test agent profile",
    )
    invalid_doc[field] = invalid_value

    def invalid_loader(resource: str) -> str:
        if resource == "agents/cse_explorer.toml":
            return invalid_doc.as_string()
        return original_loader(resource)

    monkeypatch.setattr(codex_global, "load_template", invalid_loader)

    with pytest.raises(
        codex_global.InstallValidationError,
        match=rf"{field}.*non-empty string",
    ):
        codex_global.plan_install(target)

    assert not target.exists()


@pytest.mark.parametrize(
    ("setting", "invalid_value", "expected_type"),
    [
        ("max_threads", True, "integer"),
        ("max_depth", True, "integer"),
        ("job_max_runtime_seconds", True, "integer"),
        ("interrupt_message", 1, "boolean"),
    ],
)
def test_managed_agent_settings_require_exact_toml_types(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setting: str,
    invalid_value: object,
    expected_type: str,
) -> None:
    target = tmp_path / "codex"
    original_loader = codex_global.load_template
    invalid_doc = codex_global._parse_toml(
        original_loader("config.toml"),
        "test config",
    )
    invalid_doc["agents"][setting] = invalid_value

    def invalid_loader(resource: str) -> str:
        if resource == "config.toml":
            return invalid_doc.as_string()
        return original_loader(resource)

    monkeypatch.setattr(codex_global, "load_template", invalid_loader)

    with pytest.raises(
        codex_global.InstallValidationError,
        match=rf"{setting}.*{expected_type}",
    ):
        codex_global.plan_install(target)

    assert not target.exists()


@pytest.mark.parametrize(
    ("resource", "invalid_text", "message_pattern"),
    [
        (
            "agents/cse_explorer.toml",
            "name = [\n",
            r"Invalid TOML.*agents/cse_explorer\.toml",
        ),
        (
            "agents/cse_explorer.toml",
            (
                codex_global.load_template("agents/cse_explorer.toml").replace(
                    'sandbox_mode = "read-only"',
                    'sandbox_mode = "danger-full-access"',
                )
            ),
            r"cse_explorer.*invalid sandbox_mode",
        ),
        (
            "config.toml",
            codex_global.load_template("config.toml").replace(
                "max_threads = 4", "max_threads = 5"
            ),
            r"config\.toml.*max_threads.*4",
        ),
        (
            "AGENTS.routing.md",
            codex_global.load_template("AGENTS.routing.md").replace(
                codex_global.END_MARKER, ""
            ),
            r"AGENTS\.routing\.md.*marker pair",
        ),
        ("model-routing.md", "\n", r"model-routing\.md.*not be empty"),
    ],
)
def test_invalid_packaged_resources_fail_before_target_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resource: str,
    invalid_text: str,
    message_pattern: str,
) -> None:
    target = tmp_path / "codex"
    original_loader = codex_global.load_template

    def invalid_loader(candidate: str) -> str:
        if candidate == resource:
            return invalid_text
        return original_loader(candidate)

    monkeypatch.setattr(codex_global, "load_template", invalid_loader)

    with pytest.raises(codex_global.InstallValidationError, match=message_pattern):
        codex_global.plan_install(target)

    assert not target.exists()


def test_apply_backs_up_changed_files_and_second_apply_is_noop(tmp_path: Path) -> None:
    target = tmp_path / "codex"
    target.mkdir()
    original_config = "# original\n[agents]\nmax_threads = 8\n"
    (target / "config.toml").write_text(original_config, encoding="utf-8")

    first_plan = codex_global.plan_install(target)
    result = codex_global.apply_plan(first_plan)

    assert result.changed is True
    assert result.backup_directory is not None
    assert (result.backup_directory / "config.toml").read_text(encoding="utf-8") == original_config
    assert all((target / path).is_file() for path in EXPECTED_PATHS)

    second_plan = codex_global.plan_install(target)
    assert {entry.action for entry in second_plan.entries} == {"no-op"}
    second_result = codex_global.apply_plan(second_plan)
    assert second_result.changed is False
    assert second_result.backup_directory is None


def test_apply_backup_preserves_every_changed_existing_destination(tmp_path: Path) -> None:
    target = tmp_path / "codex"
    originals = {
        Path("config.toml"): b"# original config\n[agents]\nmax_threads = 8\n",
        Path("AGENTS.md"): "user guidance: caf\u00e9\n".encode(),
        Path("model-routing.md"): b"user-owned model routing\n",
        Path("agents/cse_explorer.toml"): b"user-owned explorer profile\n",
    }
    for relative_path, content in originals.items():
        destination = target / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    plan = codex_global.plan_install(target, force_model_routing=True)
    result = codex_global.apply_plan(plan)

    assert result.backup_directory is not None
    backed_up_files = {
        path.relative_to(result.backup_directory)
        for path in result.backup_directory.rglob("*")
        if path.is_file()
    }
    assert backed_up_files == set(originals)
    for relative_path, content in originals.items():
        assert (result.backup_directory / relative_path).read_bytes() == content


def test_post_write_mismatch_raises_and_retains_backup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "codex"
    target.mkdir()
    original_config = b"# original\n[agents]\nmax_threads = 8\n"
    (target / "config.toml").write_bytes(original_config)
    plan = codex_global.plan_install(target)
    original_atomic_write = codex_global._atomic_write

    def write_then_corrupt(path: Path, content: str) -> None:
        original_atomic_write(path, content)
        if path.name == "config.toml":
            path.write_text(f"{content}# post-replace corruption\n", encoding="utf-8")

    monkeypatch.setattr(codex_global, "_atomic_write", write_then_corrupt)

    with pytest.raises(
        codex_global.InstallOperationalError,
        match=r"Post-write validation mismatch for config\.toml",
    ):
        codex_global.apply_plan(plan)

    backups = [path for path in (target / "backups").iterdir() if path.is_dir()]
    assert len(backups) == 1
    assert (backups[0] / "config.toml").read_bytes() == original_config


def test_apply_rejects_stale_plan_before_backup_or_write(tmp_path: Path) -> None:
    target = tmp_path / "codex"
    target.mkdir()
    config_path = target / "config.toml"
    config_path.write_text("[agents]\nmax_threads = 8\n", encoding="utf-8")
    plan = codex_global.plan_install(target)

    changed_after_planning = "# changed after preview\n[agents]\nmax_threads = 7\n"
    config_path.write_text(changed_after_planning, encoding="utf-8")

    with pytest.raises(codex_global.InstallConflictError, match="changed after preview"):
        codex_global.apply_plan(plan)

    assert config_path.read_text(encoding="utf-8") == changed_after_planning
    assert not (target / "backups").exists()
    assert not (target / "AGENTS.md").exists()


def test_apply_reports_backup_before_first_destination_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "codex"
    target.mkdir()
    (target / "config.toml").write_text(
        "[agents]\nmax_threads = 8\n", encoding="utf-8"
    )
    plan = codex_global.plan_install(target)
    events: list[tuple[str, Path]] = []
    original_atomic_write = codex_global._atomic_write

    def record_write(path: Path, content: str) -> None:
        events.append(("write", path))
        original_atomic_write(path, content)

    monkeypatch.setattr(codex_global, "_atomic_write", record_write)

    result = codex_global.apply_plan(
        plan,
        backup_reporter=lambda path: events.append(("backup", path)),
    )

    assert result.backup_directory is not None
    assert events[0] == ("backup", result.backup_directory)
    assert events[1][0] == "write"


def test_apply_wraps_backup_reporter_failure_before_any_destination_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "codex"
    target.mkdir()
    original_config = "[agents]\nmax_threads = 8\n"
    (target / "config.toml").write_text(original_config, encoding="utf-8")
    plan = codex_global.plan_install(target)
    reported_backups: list[Path] = []
    writes: list[Path] = []

    def fail_reporter(backup: Path) -> None:
        reported_backups.append(backup)
        raise RuntimeError(f"secret callback detail under {target}")

    monkeypatch.setattr(
        codex_global,
        "_atomic_write",
        lambda path, content: writes.append(path),
    )

    with pytest.raises(codex_global.InstallOperationalError) as excinfo:
        codex_global.apply_plan(plan, backup_reporter=fail_reporter)

    assert len(reported_backups) == 1
    backup = reported_backups[0]
    assert backup.is_dir()
    assert (backup / "config.toml").read_text(encoding="utf-8") == original_config
    assert writes == []
    message = str(excinfo.value)
    assert "backups/cse-" in message
    assert str(target) not in message
    assert "secret callback detail" not in message
    assert excinfo.value.__cause__ is None


def test_apply_refuses_conflict_before_creating_backup(tmp_path: Path) -> None:
    target = tmp_path / "codex"
    target.mkdir()
    (target / "model-routing.md").write_text("user-owned\n", encoding="utf-8")
    plan = codex_global.plan_install(target)

    with pytest.raises(codex_global.InstallConflictError):
        codex_global.apply_plan(plan)

    assert not (target / "backups").exists()
    assert not (target / "config.toml").exists()


def test_apply_reports_atomic_replace_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "codex"
    plan = codex_global.plan_install(target)

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(codex_global.os, "replace", fail_replace)

    with pytest.raises(codex_global.InstallOperationalError, match="atomic"):
        codex_global.apply_plan(plan)
    assert not list(target.rglob("*.tmp"))


def test_atomic_failure_after_first_replacement_keeps_complete_backup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "codex"
    originals = {
        Path("config.toml"): b"[agents]\nmax_threads = 8\n",
        Path("AGENTS.md"): b"user guidance\n",
        Path("model-routing.md"): b"user model routing\n",
        Path("agents/cse_explorer.toml"): b"user explorer\n",
    }
    for relative_path, content in originals.items():
        destination = target / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    plan = codex_global.plan_install(target, force_model_routing=True)
    original_replace = codex_global.os.replace
    replace_count = 0

    def fail_second_replace(source: Path, destination: Path) -> None:
        nonlocal replace_count
        replace_count += 1
        if replace_count == 2:
            raise OSError("simulated second replace failure")
        original_replace(source, destination)

    monkeypatch.setattr(codex_global.os, "replace", fail_second_replace)

    with pytest.raises(codex_global.InstallOperationalError, match="atomically replace"):
        codex_global.apply_plan(plan)

    assert replace_count == 2
    assert (target / "config.toml").read_text(encoding="utf-8") == plan.content_for(
        Path("config.toml")
    )
    assert (target / "AGENTS.md").read_bytes() == originals[Path("AGENTS.md")]
    assert not list(target.rglob("*.tmp"))
    backups = [path for path in (target / "backups").iterdir() if path.is_dir()]
    assert len(backups) == 1
    for relative_path, content in originals.items():
        assert (backups[0] / relative_path).read_bytes() == content
