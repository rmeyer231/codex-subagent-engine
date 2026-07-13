"""CLI coverage for the global Codex installer command."""

from __future__ import annotations

from pathlib import Path

from src import cli, codex_global


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
