"""
Core engine — orchestrates subagent lifecycle.

The engine:
1. Loads a manifest (TOML) or batch (CSV)
2. Spawns subagents in parallel (up to max_threads)
3. Handles dependency ordering
4. Runs approval gates when configured
5. Collects and returns all results
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .approval import ApprovalRequest, Decision, request_approval
from .batch import BatchItem, load_batch, save_batch_results
from .manifest import AgentConfig, Manifest
from .subagent import SubagentResult, SubagentStatus, run_subagent

console = Console()


@dataclass
class EngineResult:
    manifest_description: str
    results: list[SubagentResult]
    approved: list[SubagentResult] = field(default_factory=list)
    rejected: list[SubagentResult] = field(default_factory=list)

    def print_summary(self) -> None:
        table = Table(title="Subagent Results", show_lines=True)
        table.add_column("Agent", style="cyan")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Output (preview)", max_width=60)

        for r in self.results:
            status_color = {"completed": "green", "failed": "red", "rejected": "yellow"}.get(r.status.value, "white")
            preview = r.output[:80] + "..." if len(r.output) > 80 else r.output
            table.add_row(
                f"agent-{r.agent_index}",
                r.agent_type,
                f"[{status_color}]{r.status.value}[/{status_color}]",
                preview,
            )
        console.print(table)


class Engine:
    def __init__(self, manifest: Manifest):
        self.manifest = manifest

    async def run(self) -> EngineResult:
        """Execute all agents defined in the manifest."""
        agents = self.manifest.agents
        settings = self.manifest.settings
        semaphore = asyncio.Semaphore(settings.max_threads)

        console.print(Panel(
            f"[bold]{self.manifest.description}[/bold]\n"
            f"Agents: {len(agents)} | Threads: {settings.max_threads}",
            title="🚀 CSE Engine",
        ))

        # Track completed results by index for dependency context
        completed: dict[int, SubagentResult] = {}
        all_results: list[SubagentResult] = [None] * len(agents)  # type: ignore

        async def run_one(index: int, config: AgentConfig) -> SubagentResult:
            # Wait for dependencies
            for dep_idx in config.depends_on:
                while dep_idx not in completed:
                    await asyncio.sleep(0.1)

            # Build context from dependencies
            context_parts = []
            for dep_idx in config.depends_on:
                dep = completed[dep_idx]
                context_parts.append(f"### Output from agent-{dep_idx} ({dep.agent_type})\n{dep.output}")
            context = "\n\n".join(context_parts)

            async with semaphore:
                console.print(f"  ▶ Starting [cyan]agent-{index}[/cyan] ({config.type})")
                result = await run_subagent(
                    config, index, context,
                    timeout_seconds=settings.job_max_runtime_seconds,
                )

            # Approval gate
            if result.status == SubagentStatus.COMPLETED:
                needs_approval = config.approval_required or settings.require_approval
                if needs_approval:
                    req = ApprovalRequest(
                        agent_name=f"agent-{index} ({config.type})",
                        description=config.instructions,
                        original="",
                        proposed=result.output,
                    )
                    approval = request_approval(req)
                    if approval.decision == Decision.REJECT:
                        result.status = SubagentStatus.REJECTED

            status_icon = "✓" if result.status == SubagentStatus.COMPLETED else "✗"
            console.print(f"  {status_icon} [cyan]agent-{index}[/cyan] → {result.status.value}")
            completed[index] = result
            return result

        tasks = [run_one(i, cfg) for i, cfg in enumerate(agents)]
        results = await asyncio.gather(*tasks)

        approved = [r for r in results if r.status == SubagentStatus.COMPLETED]
        rejected = [r for r in results if r.status == SubagentStatus.REJECTED]

        return EngineResult(
            manifest_description=self.manifest.description,
            results=list(results),
            approved=approved,
            rejected=rejected,
        )

    async def run_batch(self, csv_path: str, output_path: str) -> None:
        """Run the manifest's first agent config against each row in a CSV."""
        if not self.manifest.agents:
            console.print("[red]No agents defined in manifest.[/red]")
            return

        agent_config = self.manifest.agents[0]
        items = load_batch(csv_path)
        semaphore = asyncio.Semaphore(self.manifest.settings.max_threads)

        console.print(Panel(
            f"Batch: {csv_path}\nItems: {len(items)} | Agent: {agent_config.type}",
            title="📋 Batch Mode",
        ))

        async def process_item(item: BatchItem) -> str:
            instructions = item.get_instructions()
            cfg = AgentConfig(
                type=agent_config.type,
                instructions=instructions,
                model=agent_config.model,
                sandbox=agent_config.sandbox,
            )
            async with semaphore:
                result = await run_subagent(cfg, item.row_index)
            return result.output

        outputs = await asyncio.gather(*[process_item(item) for item in items])
        save_batch_results(items, list(outputs), output_path)
        console.print(f"[green]✓ Results saved to {output_path}[/green]")
