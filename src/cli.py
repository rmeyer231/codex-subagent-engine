"""
CLI entrypoint: `cse run <manifest.toml>`
"""

import argparse
import asyncio
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

    args = parser.parse_args(argv)

    if args.command == "run":
        asyncio.run(_run(args))
    elif args.command == "batch":
        asyncio.run(_batch(args))
    elif args.command == "install-codex":
        return _install_codex(args)
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
