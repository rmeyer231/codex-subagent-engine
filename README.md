# codex-subagent-engine

> Parallel subagent spawning with TOML configuration, batch CSV processing, and human approval workflows.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Anthropic](https://img.shields.io/badge/Powered%20by-Claude-8B5CF6?logo=anthropic)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## What It Does

A CLI tool that reads a TOML task manifest, spawns parallel AI subagents (explorer, worker, reviewer), and orchestrates their full lifecycle — from spawning through dependency resolution, approval gating, and result collection.

Inspired by [OpenAI Codex subagents](https://developers.openai.com/codex/subagents): the idea that complex coding tasks are best handled by specialized parallel agents rather than a single monolithic prompt.

## Quick Start

```bash
pip install -e .
export ANTHROPIC_API_KEY=your_key

# Run a PR review with 3 parallel specialist agents
cse run examples/pr-review.toml

# Run batch migration: one agent per CSV row
cse batch examples/migration-task.toml examples/migration-batch.csv results.csv
```

## Manifest Format

```toml
[task]
description = "Review this PR for security issues"

[[agents]]
type = "explorer"
instructions = "Map all files and their purpose"

[[agents]]
type = "reviewer"
instructions = "Review for security vulnerabilities"
depends_on = [0]          # runs after explorer finishes
approval_required = true  # pause for human review

[[agents]]
type = "worker"
instructions = "Summarize findings and give a recommendation"
depends_on = [1]

[settings]
max_threads = 3           # parallel agents
job_max_runtime_seconds = 90
```

## Built-in Agent Types

| Type | System Prompt Focus | Best For |
|------|--------------------|-|
| `explorer` | Mapping and understanding | Initial codebase analysis |
| `reviewer` | Quality validation | Security, performance review |
| `worker` | Making targeted changes | Refactoring, migrations |

Custom types are supported — any name you use will generate a generic focused prompt.

## Batch Mode

Process a CSV file with one row per task. Each row spawns a separate subagent:

```csv
file,task
src/auth.py,Add type annotations to all public methods
src/payments.py,Replace SQL strings with parameterized queries
src/notifications.py,Convert sync HTTP calls to async
```

```bash
cse batch manifest.toml input.csv output.csv
```

Output CSV has all original columns plus `output` and `status`.

## Approval Workflows

Set `approval_required = true` on any agent to pause before applying its output:

```
⏸ Approval Required
────────────────────
Agent: agent-2 (reviewer)
Task: Summarize findings

[diff shown here]

  a — Approve and apply
  r — Reject (discard output)
  s — Skip approval (apply anyway)

Decision [a/r/s]: _
```

Or enable globally: `require_approval = true` in `[settings]`.

## Dependency Ordering

Agents can declare dependencies via `depends_on = [index]`. Independent agents run in parallel; dependent agents wait for their dependencies:

```
agent-0 (explorer) ──────────────┐
                                  ├─▶ agent-3 (worker) [runs after 1 & 2]
agent-1 (security reviewer) ─────┤
agent-2 (perf reviewer) ─────────┘
```

## Project Structure

```
src/
├── cli.py          # CLI entrypoint: cse run / cse batch
├── engine.py       # Core: spawning, dependency ordering, approval
├── manifest.py     # TOML parser and config dataclasses
├── subagent.py     # Subagent lifecycle: init → execute → report
├── approval.py     # Human approval gate with diff display
└── batch.py        # CSV batch processing
examples/
├── pr-review.toml       # 3 parallel reviewers (security, perf, summary)
├── frontend-debug.toml  # map → diagnose → fix
├── migration-task.toml  # batch migration config
└── migration-batch.csv  # 5 files to migrate
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```
