# Model Routing

This file maps workflow phases to recommended model identifiers for the
active Codex session. It is the canonical reference for the global CSE
routing policy in `~/.codex/AGENTS.md`.

Repository-local AGENTS.md rules win over this file; this file wins over the
CSE managed routing block when the two disagree on a phase assignment.

## Phase table

| Phase                              | Default model       | Notes                                                  |
| ---------------------------------- | ------------------- | ------------------------------------------------------ |
| Brainstorming, proposal, specs     | `claude-opus-4-8`   | Use when the task requires broad reasoning or design.  |
| Implementation, TDD, general code  | `claude-sonnet-4-6` | Default for routine engineering work.                  |
| Summarization, quick lookups      | `claude-haiku-4-5`  | Use for low-stakes reads and short summaries.          |

## Inheritance by default

Custom agent profiles in `~/.codex/agents/cse_*.toml` deliberately omit a
`model` key so they inherit the parent session's active model. Pin a role
to a specific model only after the native identifier has been verified in
the active Codex distribution; until then, leave the inheritance in place.

## Switching models

The root thread may switch the active model for the next phase; subagents
inherit whichever model the parent session is running when they are spawned.
This means a single session can hand off between phases without restarting
Codex, provided the parent session itself moves to the new model first.

## Path

This file lives at `~/.codex/model-routing.md`. The CSE managed AGENTS block
references it by this exact lowercase path.