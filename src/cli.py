"""
CLI entrypoint: `cse run <manifest.toml>`
"""

import argparse
import asyncio
import sys
from pathlib import Path


def main():
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

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(_run(args))
    elif args.command == "batch":
        asyncio.run(_batch(args))


async def _run(args):
    from src.engine import Engine
    from src.manifest import Manifest

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
    from src.engine import Engine
    from src.manifest import Manifest

    manifest = Manifest.from_file(args.manifest)
    engine = Engine(manifest)
    await engine.run_batch(args.input_csv, args.output_csv)


if __name__ == "__main__":
    main()
