# codex-subagent-engine

> Parallel subagent spawning with TOML configuration, batch CSV processing, and human approval workflows.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Anthropic](https://img.shields.io/badge/Powered%20by-Claude-8B5CF6?logo=anthropic)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## What It Does

A CLI tool that reads a TOML task manifest, spawns parallel AI subagents (explorer, worker, reviewer), and orchestrates their full lifecycle — from spawning through dependency resolution, approval gating, and result collection.

Inspired by [OpenAI Codex subagents](https://developers.openai.com/codex/subagents): the idea that complex coding tasks are best handled by specialized parallel agents rather than a single monolithic prompt.

The project now has two deliberately separate execution paths:

| Path | Runtime | Purpose |
|------|---------|---------|
| `cse run` / `cse batch` | This project's Anthropic-backed manifest engine | Executes TOML manifests, dependency ordering, CSV batches, and approval prompts. |
| `cse install-codex` | Native Codex subagents | Installs global routing policy and custom-agent profiles; Codex itself owns threads, tools, approvals, sandbox enforcement, and result synthesis. |

Installing the native routing bundle does not replace the manifest engine or change `run` and `batch` behavior. It configures Codex rather than making this project a second Codex orchestrator.

## Quick Start

```bash
pip install -e .
export ANTHROPIC_API_KEY=your_key

# Run a PR review with 3 parallel specialist agents
cse run examples/pr-review.toml

# Run batch migration: one agent per CSV row
cse batch examples/migration-task.toml examples/migration-batch.csv results.csv
```

## Native Codex Routing

`cse install-codex` installs a conservative global routing bundle for native Codex sessions. It defines four distinct profiles:

| Profile | Default sandbox | Use |
|---------|-----------------|-----|
| `cse_explorer` | `read-only` | Map unfamiliar code and identify callers. |
| `cse_planner` | `read-only` | Produce plans, specifications, and architecture analysis. |
| `cse_implementer` | `workspace-write` | Make an approved, bounded change inside the active workspace. |
| `cse_reviewer` | `read-only` | Independently validate code, tests, and requirements. |

All four profiles omit a `model` setting and inherit the active parent session model. The parent session's live approval and sandbox policy remains authoritative, including for the workspace-write implementer. The routing policy keeps phase gates, task decomposition, steering, and final synthesis in the root thread; it prevents recursive delegation and overlapping parallel write ownership.

### Preview and apply

Preview is the default and never writes to the selected Codex home:

```bash
cse install-codex
```

Review every reported `create`, `update`, `no-op`, or `conflict` action. Apply only after the preview is acceptable:

```bash
cse install-codex --apply
```

The target directory is resolved in this order:

1. `--codex-home PATH`
2. `CODEX_HOME`
3. `~/.codex`

This makes an isolated rehearsal straightforward:

```bash
codex_home="$(mktemp -d)"
cse install-codex --codex-home "$codex_home"
cse install-codex --codex-home "$codex_home" --apply
```

When scripting, assign the temporary path first so preview and apply use the same directory:

```bash
export CODEX_HOME="$(mktemp -d)"
cse install-codex
cse install-codex --apply
cse install-codex --apply  # reports a no-op
```

An existing, different `model-routing.md` is treated as user-owned content and causes a conflict. Inspect it before explicitly allowing replacement:

```bash
cse install-codex --force-model-routing
cse install-codex --apply --force-model-routing
```

The force flag applies only to the differing model-routing document; other validation and backup rules still apply.

### Managed files

The installer validates the complete bundle before writing and manages these destinations under the selected Codex home:

```text
config.toml                    # selected [agents] keys only
AGENTS.md                      # CSE marker-delimited block only
model-routing.md               # create, or replace only with explicit force
agents/cse_explorer.toml
agents/cse_planner.toml
agents/cse_implementer.toml
agents/cse_reviewer.toml
```

`src/templates/codex/AGENTS.routing.md` is the packaged source for the managed block. It is merged into the auto-discovered destination `AGENTS.md`; no `AGENTS.routing.md` file is installed. Existing comments and unrelated keys in `config.toml`, and prose outside the CSE markers in `AGENTS.md`, are preserved. If a non-empty `AGENTS.override.md` exists in the Codex home, Codex loads it instead of `AGENTS.md`, so resolve that override before expecting this routing block to take effect.

### Backup and rollback

Before changing any existing destination, apply creates a timestamped directory such as `backups/cse-20260713T120000.000000Z` and prints that target-relative path before destination writes begin. The backup mirrors every existing file that the plan will update. Files reported as `create` have no prior version and therefore are not present in the backup.

To roll back, stop Codex, copy every file from the reported backup to the same relative path under that Codex home, and remove only the destinations that the corresponding plan reported as newly created. Do not replace the entire Codex home: the backup contains the changed pre-install files, not an independent snapshot of unrelated configuration. Restart Codex after restoration.

### Restart and validate

Codex must be restarted after apply so it reloads global instructions and custom-agent profiles. Then run a bounded read-only canary, for example asking `cse_explorer` to map one small repository area. In the native agent UI (`/agent`), verify that:

- the delegated role is `cse_explorer` and remains read-only;
- no nested subagent is created;
- the root thread waits for the result and synthesizes the final answer; and
- at most four agent threads are open.

Re-run `cse install-codex` to confirm the installed bundle previews as all `no-op`. Repository validation is:

```bash
pytest -q
ruff check src tests
openspec validate global-codex-subagent-routing
```

For an isolated, opt-in evaluation of Codex Pooler as an external provider, see the [experimental Codex Pooler canary](docs/codex-pooler-canary.md). CSE does not install Pooler or change the default provider.

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
├── cli.py          # CLI entrypoint: cse run / cse batch / cse install-codex
├── codex_global.py # Native Codex bundle planning, validation, and installation
├── engine.py       # Core: spawning, dependency ordering, approval
├── manifest.py     # TOML parser and config dataclasses
├── subagent.py     # Subagent lifecycle: init → execute → report
├── approval.py     # Human approval gate with diff display
├── batch.py        # CSV batch processing
└── templates/codex # Packaged native Codex routing resources
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
