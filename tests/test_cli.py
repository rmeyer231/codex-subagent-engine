"""CLI coverage for the global Codex installer command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

from src import cli, codex_global


def test_run_dispatch_preserves_manifest_and_approve_all(monkeypatch) -> None:
    run_handler = AsyncMock()
    monkeypatch.setattr(cli, "_run", run_handler)

    exit_code = cli.main(["run", "manifest.toml", "--approve-all"])

    assert exit_code == 0
    run_handler.assert_awaited_once()
    args = run_handler.await_args.args[0]
    assert args.manifest == "manifest.toml"
    assert args.approve_all is True


def test_batch_dispatch_preserves_manifest_and_csv_arguments(monkeypatch) -> None:
    batch_handler = AsyncMock()
    monkeypatch.setattr(cli, "_batch", batch_handler)

    exit_code = cli.main(
        ["batch", "manifest.toml", "input.csv", "output.csv"]
    )

    assert exit_code == 0
    batch_handler.assert_awaited_once()
    args = batch_handler.await_args.args[0]
    assert args.manifest == "manifest.toml"
    assert args.input_csv == "input.csv"
    assert args.output_csv == "output.csv"


def test_install_codex_defaults_to_redacted_preview(
    capsys, tmp_path: Path
) -> None:
    target = tmp_path / "preview-home"

    exit_code = cli.main(["install-codex", "--codex-home", str(target)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Preview" in captured.out
    assert "no files were written" in captured.out
    assert "config.toml" in captured.out
    assert str(target) not in captured.out
    assert not target.exists()


def test_install_codex_apply_writes_bundle(capsys, tmp_path: Path) -> None:
    target = tmp_path / "apply-home"

    exit_code = cli.main(
        ["install-codex", "--codex-home", str(target), "--apply"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Applied" in captured.out
    assert "Backup:" not in captured.out
    assert (target / "config.toml").is_file()
    assert (target / "agents/cse_reviewer.toml").is_file()


def test_install_codex_conflict_returns_validation_exit_code(
    capsys, tmp_path: Path
) -> None:
    target = tmp_path / "conflict-home"
    target.mkdir()
    (target / "model-routing.md").write_text("user-owned\n", encoding="utf-8")

    exit_code = cli.main(
        ["install-codex", "--codex-home", str(target), "--apply"]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "conflict" in captured.err.lower()
    assert "--force-model-routing" in captured.err
    assert not (target / "config.toml").exists()


def test_install_codex_force_model_routing_resolves_conflict(
    capsys, tmp_path: Path
) -> None:
    target = tmp_path / "forced-home"
    target.mkdir()
    (target / "model-routing.md").write_text("user-owned\n", encoding="utf-8")

    exit_code = cli.main(
        [
            "install-codex",
            "--codex-home",
            str(target),
            "--apply",
            "--force-model-routing",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.count("Backup: backups/cse-") == 1
    assert "Codex-opus-4-8" in (target / "model-routing.md").read_text(
        encoding="utf-8"
    )


def test_install_codex_reports_backup_before_later_write_failure(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    target = tmp_path / "failed-home"
    target.mkdir()
    (target / "config.toml").write_text(
        "[agents]\nmax_threads = 8\n", encoding="utf-8"
    )

    def fail_write(path: Path, content: str) -> None:
        raise codex_global.InstallOperationalError("simulated destination failure")

    monkeypatch.setattr(codex_global, "_atomic_write", fail_write)

    exit_code = cli.main(
        ["install-codex", "--codex-home", str(target), "--apply"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out.count("Backup: backups/cse-") == 1
    assert str(target) not in captured.out
    assert "Applied" not in captured.out
    assert "simulated destination failure" in captured.err


def test_install_codex_invalid_template_returns_redacted_validation_exit(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    target = tmp_path / "validation-home"
    original_loader = codex_global.load_template

    def invalid_loader(resource: str) -> str:
        if resource == "agents/cse_reviewer.toml":
            return "name = [\n"
        return original_loader(resource)

    monkeypatch.setattr(codex_global, "load_template", invalid_loader)

    exit_code = cli.main(["install-codex", "--codex-home", str(target)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "agents/cse_reviewer.toml" in captured.err
    assert str(target) not in captured.err
    assert not target.exists()


def test_install_codex_post_write_mismatch_returns_redacted_operational_exit(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    target = tmp_path / "operational-home"
    target.mkdir()
    (target / "config.toml").write_text(
        "[agents]\nmax_threads = 8\n", encoding="utf-8"
    )
    original_atomic_write = codex_global._atomic_write

    def write_then_corrupt(path: Path, content: str) -> None:
        original_atomic_write(path, content)
        if path.name == "config.toml":
            path.write_text(f"{content}# corrupt\n", encoding="utf-8")

    monkeypatch.setattr(codex_global, "_atomic_write", write_then_corrupt)

    exit_code = cli.main(
        ["install-codex", "--codex-home", str(target), "--apply"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out.count("Backup: backups/cse-") == 1
    assert "Applied" not in captured.out
    assert "Post-write validation mismatch for config.toml" in captured.err
    assert str(target) not in captured.out + captured.err
