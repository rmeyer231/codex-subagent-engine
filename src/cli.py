"""
CLI entrypoint: `cse run <manifest.toml>`
"""

import argparse
import asyncio
import shlex
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="cse",
        description="Codex Subagent Engine — spawn parallel AI agents from a TOML manifest",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # cse run <manifest>
    run_parser = subparsers.add_parser("run", help="Run a manifest file")
    run_parser.add_argument("manifest", help="Path to TOML manifest file")
    run_parser.add_argument("--approve-all", action="store_true", help="Auto-approve all outputs (skip approval gates)")

    # cse batch <manifest> <input.csv> <output.csv>
    batch_parser = subparsers.add_parser("batch", help="Run manifest against a CSV batch")
    batch_parser.add_argument("manifest", help="Path to TOML manifest file")
    batch_parser.add_argument("input_csv", help="Input CSV file (one row per task)")
    batch_parser.add_argument("output_csv", help="Output CSV file with results")

    install_parser = subparsers.add_parser(
        "install-codex",
        help="Preview or apply native Codex subagent routing",
    )
    install_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the validated plan (the default is preview only)",
    )
    install_parser.add_argument(
        "--codex-home",
        metavar="PATH",
        help="Target Codex home (overrides CODEX_HOME and ~/.codex)",
    )
    install_parser.add_argument(
        "--force-model-routing",
        action="store_true",
        help="Explicitly replace a differing model-routing.md",
    )

    stack_parser = subparsers.add_parser(
        "install-openlimits-stack",
        help="Preview, apply, or roll back the dual-harness OpenLimits stack",
    )
    stack_mode = stack_parser.add_mutually_exclusive_group()
    stack_mode.add_argument(
        "--apply",
        action="store_true",
        help="Apply the reviewed plan (the default is preview only)",
    )
    stack_mode.add_argument(
        "--rollback",
        metavar="TRANSACTION_ID",
        help="Restore a previously applied transaction",
    )
    stack_parser.add_argument("--claude-home", metavar="PATH")
    stack_parser.add_argument("--codex-home", metavar="PATH")
    stack_parser.add_argument("--launcher-dir", metavar="PATH")
    stack_parser.add_argument("--backup-root", metavar="PATH")
    stack_parser.add_argument(
        "--keychain-service",
        default="OpenLimits",
        help="macOS Keychain service name (default: OpenLimits)",
    )
    stack_parser.add_argument(
        "--keychain-account",
        default="api-key",
        help="macOS Keychain account name (default: api-key)",
    )
    stack_parser.add_argument(
        "--resolve-conflicts",
        action="store_true",
        help="Replace reviewed managed conflicts, including apiKeyHelper/launcher",
    )

    validate_parser = subparsers.add_parser(
        "validate-openlimits-stack",
        help="Run isolated validation or explicitly gated live canaries",
    )
    validate_parser.add_argument(
        "--live",
        action="store_true",
        help="Run the displayed bounded Claude and Codex CLI provider requests",
    )
    validate_parser.add_argument(
        "--inject-failure",
        action="store_true",
        help="Also prove automatic rollback with an injected isolated failure",
    )
    validate_parser.add_argument("--claude-home", metavar="PATH")
    validate_parser.add_argument("--codex-home", metavar="PATH")
    validate_parser.add_argument("--launcher-dir", metavar="PATH")
    validate_parser.add_argument("--report", metavar="PATH")
    validate_parser.add_argument(
        "--provider-evidence",
        action="append",
        default=[],
        metavar="SURFACE=SOURCE",
        help="Record non-secret provider-side attribution for a live surface",
    )
    validate_parser.add_argument(
        "--waive",
        action="append",
        default=[],
        metavar="SURFACE=REASON",
        help="Record an explicit user waiver; a waiver is never reported as a pass",
    )

    args = parser.parse_args(argv)

    if args.command == "run":
        asyncio.run(_run(args))
    elif args.command == "batch":
        asyncio.run(_batch(args))
    elif args.command == "install-codex":
        return _install_codex(args)
    elif args.command == "install-openlimits-stack":
        return _install_openlimits_stack(args)
    elif args.command == "validate-openlimits-stack":
        return _validate_openlimits_stack(args)
    return 0


def _install_codex(args):
    from src.codex_global import CodexInstallError, apply_plan, plan_install

    try:
        plan = plan_install(
            args.codex_home,
            force_model_routing=args.force_model_routing,
        )
        heading = "Apply plan" if args.apply else "Preview"
        print(f"{heading} for Codex routing (target-relative paths):")
        for entry in plan.entries:
            print(f"  {entry.summary}")

        if plan.conflicts:
            conflicts = ", ".join(
                entry.relative_path.as_posix() for entry in plan.conflicts
            )
            print(
                f"Error: unresolved conflict in {conflicts}; "
                "pass --force-model-routing only after reviewing that file.",
                file=sys.stderr,
            )
            if not args.apply:
                print("Preview complete; no files were written.")
            return 2

        if not args.apply:
            print("Preview complete; no files were written.")
            return 0

        def report_backup(backup_directory):
            backup_relative = backup_directory.relative_to(plan.codex_home)
            print(f"Backup: {backup_relative.as_posix()}")

        result = apply_plan(plan, backup_reporter=report_backup)
        if not result.changed:
            print("No-op: the managed Codex routing bundle is already current.")
            return 0
        print(f"Applied {len(result.changed_paths)} managed destination(s).")
        return 0
    except CodexInstallError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.exit_code


def _install_openlimits_stack(args):
    from src.dual_harness_global import (
        StackCredentialError,
        StackInstallError,
        apply_stack,
        plan_stack,
        resolve_stack_paths,
        rollback_transaction,
    )

    try:
        if args.rollback:
            if args.backup_root:
                backup_root = Path(args.backup_root)
            else:
                backup_root = resolve_stack_paths(
                    claude_home=args.claude_home,
                    codex_home=args.codex_home,
                    launcher_dir=args.launcher_dir,
                )[3]
            result = rollback_transaction(args.rollback, backup_root=backup_root)
            print(
                f"Rolled back transaction {result.transaction_id}: "
                f"{len(result.changed_keys)} destination(s) restored."
            )
            return 0

        plan = plan_stack(
            claude_home=args.claude_home,
            codex_home=args.codex_home,
            launcher_dir=args.launcher_dir,
            backup_root=args.backup_root,
            keychain_service=args.keychain_service,
            keychain_account=args.keychain_account,
            resolve_conflicts=args.resolve_conflicts,
        )
        heading = "Apply plan" if args.apply else "Preview"
        print(f"{heading} for OpenLimits dual-harness stack:")
        print(f"  Claude home: {plan.claude_home}")
        print(f"  Codex home: {plan.codex_home}")
        print(f"  Launcher directory: {plan.launcher_dir}")
        print(f"  Backup root: {plan.backup_root}")
        print(
            "  Keychain: "
            f"service={plan.keychain_service!r}, account={plan.keychain_account!r}"
        )
        for target in plan.targets:
            print(f"  {target.summary}")
        for path in plan.legacy_credential_paths:
            print(f"  credential-conflict: {path}")

        if plan.conflicts or plan.legacy_credential_paths:
            if plan.conflicts:
                keys = ", ".join(target.key for target in plan.conflicts)
                print(
                    f"Error: unresolved conflict in {keys}; review before "
                    "--resolve-conflicts.",
                    file=sys.stderr,
                )
            if plan.legacy_credential_paths:
                print(
                    "Error: rotate and remove each reported plaintext credential "
                    "before apply.",
                    file=sys.stderr,
                )
            if not args.apply:
                print("Preview complete; no files or credentials were changed.")
            return 2
        if not args.apply:
            print("Preview complete; no files or credentials were changed.")
            return 0

        result = apply_stack(plan)
        if not result.changed:
            print("No-op: the OpenLimits dual-harness stack is already current.")
            return 0
        print(
            f"Applied {len(result.changed_keys)} managed destination(s); "
            f"transaction: {result.transaction_id}."
        )
        return 0
    except StackCredentialError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        command = [
            "/usr/bin/security",
            "add-generic-password",
            "-a",
            args.keychain_account,
            "-s",
            args.keychain_service,
            "-U",
            "-w",
        ]
        print(
            "Provision interactively (the final -w prompts without storing the token "
            f"in shell history): {shlex.join(command)}",
            file=sys.stderr,
        )
        return exc.exit_code
    except StackInstallError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.exit_code


def _parse_assignments(values, label):
    assignments = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"{label} must use SURFACE=VALUE")
        surface, detail = value.split("=", 1)
        if not surface.strip() or not detail.strip():
            raise ValueError(f"{label} requires a non-empty surface and value")
        assignments[surface.strip()] = detail.strip()
    return assignments


def _validate_openlimits_stack(args):
    from src.dual_harness_global import StackInstallError, resolve_stack_paths
    from src.dual_harness_validation import (
        ValidationReport,
        apply_waivers,
        build_live_canaries,
        guided_canary_steps,
        run_isolated_canary,
        run_live_cli_canaries,
        write_report,
    )

    try:
        evidence = _parse_assignments(args.provider_evidence, "--provider-evidence")
        waivers = _parse_assignments(args.waive, "--waive")
        isolated = run_isolated_canary(inject_failure=args.inject_failure)
        rows = isolated.rows
        mode = "isolated"
        if args.live:
            claude_home, codex_home, launcher_dir, _ = resolve_stack_paths(
                claude_home=args.claude_home,
                codex_home=args.codex_home,
                launcher_dir=args.launcher_dir,
            )
            canaries = build_live_canaries(
                claude_home=claude_home,
                codex_home=codex_home,
                launcher_dir=launcher_dir,
            )
            print("Explicit live canary plan (each line may incur provider usage):")
            for canary in canaries:
                print(
                    f"  surface={canary.surface} provider={canary.provider} "
                    f"model={canary.model} path={canary.executable_path} "
                    f"billing={canary.billing_destination} prompt={canary.prompt!r}"
                )
            live_rows = run_live_cli_canaries(
                canaries,
                provider_evidence=evidence,
            )
            print("Guided app/plugin canaries (user-recorded evidence):")
            for step in guided_canary_steps(codex_home):
                print(f"  {step}")
            replaced = {row.surface for row in live_rows}
            rows = tuple(row for row in rows if row.surface not in replaced) + live_rows
            mode = "live"
        rows = apply_waivers(rows, waivers)
        report = ValidationReport(rows, mode)
        print(report.to_text(), end="")
        if args.report:
            write_report(report, Path(args.report))
            print(f"Redacted report: {Path(args.report)}")
        if any(row.status == "fail" for row in rows):
            return 1
        if args.live and not report.ready:
            return 2
        return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except StackInstallError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.exit_code


async def _run(args):
    from src.manifest import Manifest
    from src.engine import Engine

    if not Path(args.manifest).exists():
        print(f"Error: manifest not found: {args.manifest}", file=sys.stderr)
        sys.exit(1)

    manifest = Manifest.from_file(args.manifest)
    if args.approve_all:
        manifest.settings.require_approval = False
        for agent in manifest.agents:
            agent.approval_required = False

    engine = Engine(manifest)
    result = await engine.run()
    result.print_summary()


async def _batch(args):
    from src.manifest import Manifest
    from src.engine import Engine

    manifest = Manifest.from_file(args.manifest)
    engine = Engine(manifest)
    await engine.run_batch(args.input_csv, args.output_csv)


if __name__ == "__main__":
    raise SystemExit(main())
