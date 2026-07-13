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
