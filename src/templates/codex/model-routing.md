# Model Routing

This file maps workflow phases to recommended model identifiers for the
active Codex session. It is the canonical reference for the CSE managed
block installed into `~/.codex/AGENTS.md`.

Repository-local AGENTS.md rules win over this file; this file wins over the
CSE managed routing block when the two disagree on a phase assignment.

## Phase-to-alias rows

| Phase                                          | Alias               |
| ---------------------------------------------- | ------------------- |
| proposal, spec, architecture                   | Codex-opus-4-8      |
| implementation, TDD, coding                    | Codex-sonnet-4-6    |
| summary, lookup, low-stakes                    | Codex-haiku-4-5     |
| default                                        | Codex-sonnet-4-6    |

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

This file lives at `~/.codex/model-routing.md`. The CSE managed routing
block references it by this exact lowercase path.
