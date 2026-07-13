"""
Human-in-the-loop approval gate.

Before applying subagent outputs, the engine can pause and present
a diff for human review. The user can: approve, reject, or modify.

This mirrors how Codex handles approval workflows: the agent proposes
changes, the human reviews, and only approved changes are applied.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


class Decision(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    SKIP = "skip"


@dataclass
class ApprovalRequest:
    agent_name: str
    description: str
    original: str
    proposed: str
    file_path: str | None = None


@dataclass
class ApprovalResult:
    decision: Decision
    approved_content: str | None = None


def show_diff(original: str, proposed: str, filename: str = "output") -> None:
    """Display a colored diff between original and proposed content."""
    diff = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        proposed.splitlines(keepends=True),
        fromfile=f"original/{filename}",
        tofile=f"proposed/{filename}",
    ))
    if diff:
        diff_text = "".join(diff)
        console.print(Syntax(diff_text, "diff", theme="monokai"))
    else:
        console.print("[yellow]No changes proposed.[/yellow]")


def request_approval(req: ApprovalRequest) -> ApprovalResult:
    """
    Present an approval gate to the user and collect their decision.
    Returns the decision and (if approved) the content to apply.
    """
    console.print(Panel(
        f"[bold]Agent:[/bold] {req.agent_name}\n"
        f"[bold]Task:[/bold] {req.description}",
        title="⏸ Approval Required",
        border_style="yellow",
    ))

    show_diff(req.original, req.proposed, req.file_path or "output")

    console.print("\n[bold]Options:[/bold]")
    console.print("  [green]a[/green] — Approve and apply")
    console.print("  [red]r[/red] — Reject (discard this agent's output)")
    console.print("  [blue]s[/blue] — Skip approval (apply without review)\n")

    while True:
        choice = input("Decision [a/r/s]: ").strip().lower()
        if choice == "a":
            return ApprovalResult(decision=Decision.APPROVE, approved_content=req.proposed)
        elif choice == "r":
            return ApprovalResult(decision=Decision.REJECT)
        elif choice == "s":
            return ApprovalResult(decision=Decision.SKIP, approved_content=req.proposed)
        else:
            console.print("[red]Enter a, r, or s[/red]")
