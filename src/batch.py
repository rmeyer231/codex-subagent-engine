"""
CSV batch processing — one row = one subagent task.

This enables bulk operations like:
- Migrating 50 files from callbacks to async/await
- Reviewing every API endpoint for security issues
- Generating docstrings for all public functions

CSV format:
  file,task
  src/auth.py,"Review for SQL injection vulnerabilities"
  src/payments.py,"Review for PCI compliance issues"
  src/users.py,"Add type annotations to all public functions"
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BatchItem:
    row_index: int
    data: dict[str, str]  # all CSV columns

    def get_instructions(self, instructions_column: str = "task") -> str:
        """Build the agent instructions from the CSV row."""
        task = self.data.get(instructions_column, "")
        context_parts = [f"{k}: {v}" for k, v in self.data.items() if k != instructions_column]
        if context_parts:
            return f"{task}\n\nContext: {', '.join(context_parts)}"
        return task


def load_batch(csv_path: str | Path, instructions_column: str = "task") -> list[BatchItem]:
    """Load a CSV file and return a list of BatchItems."""
    items = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            items.append(BatchItem(row_index=i, data=dict(row)))
    return items


def save_batch_results(
    items: list[BatchItem],
    outputs: list[str],
    output_path: str | Path,
) -> None:
    """Save batch results as a CSV with an added 'output' column."""
    if not items:
        return

    fieldnames = list(items[0].data.keys()) + ["output", "status"]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item, output in zip(items, outputs):
            row = {**item.data, "output": output, "status": "completed" if output else "failed"}
            writer.writerow(row)
