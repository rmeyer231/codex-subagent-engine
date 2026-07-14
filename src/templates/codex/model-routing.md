# Model Routing

This file maps workflow phases to recommended model identifiers for the
active Codex session. It is the canonical reference for the CSE managed
block installed into `~/.codex/AGENTS.md`.

Repository-local AGENTS.md rules win over this file; this file wins over the
CSE managed routing block when the two disagree on a phase assignment.

## Phase-to-model rows

| Phase                                          | OpenLimits model       |
| ---------------------------------------------- | ---------------------- |
| proposal, spec, architecture, hard review      | openai/gpt-5.6-sol     |
| implementation, TDD, coding                    | openai/gpt-5.6-terra   |
| summary, lookup, low-stakes                    | openai/gpt-5.6-luna    |
| default                                        | openai/gpt-5.6-terra   |

## Advisory routing

These mappings are recommendations, not phase gates. A mismatch MUST NOT stop
or block work, require `/model`, or ask the user to switch models. Continue
with the current session model unless the user explicitly requests a change.

## Inheritance by default

Custom agent profiles in `~/.codex/agents/cse_*.toml` deliberately omit a
`model` key so they inherit the parent session's active model. Pin a role
to a specific model only after the native identifier has been verified in
the active Codex distribution; until then, leave the inheritance in place.

## Switching models

The user may switch the active model for the next phase; subagents inherit
whichever model the parent session is running when they are spawned. The root
thread may recommend a model, but it continues with the current model when the
user does not request a switch.

## Path

This file lives at `~/.codex/model-routing.md`. The CSE managed routing
block references it by this exact lowercase path.
