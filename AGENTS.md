# Codex Repository Guidance

This file supplements the global Codex instructions. Existing phase gates,
OpenSpec lifecycle rules, validation requirements, and Git rules remain
authoritative.

## Model routing

At task start and at a meaningful phase transition, consult
`~/.codex/model-routing.md`. That global file is the canonical source for
model identifiers; do not copy its identifiers into repository guidance.

Use the coding model as the normal default. Route by the work being performed:

| Task class | Examples in this repository |
| --- | --- |
| High reasoning | OpenSpec proposals, installer transaction or rollback design, credential and provider security, cross-harness ownership, ambiguous debugging, and hard final review |
| Coding | CLI implementation, template rendering, tests, focused refactors, and normal bug fixes |
| Fast | Status summaries, command lookups, artifact inventories, and low-risk documentation |

Routing is advisory. Recommend a switch once when a meaningful phase change
would materially benefit from another model, but never block work, require
`/model`, or repeatedly announce a routine mismatch. Continue with the current
model when the user does not request a switch.
