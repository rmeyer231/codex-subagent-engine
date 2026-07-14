# Claude Code Repository Guidance

This file supplements the global Claude Code instructions. Existing phase
gates, OpenSpec lifecycle rules, validation requirements, and Git rules remain
authoritative.

## Model and provider routing

At task start and at a meaningful phase transition, consult
`~/.claude/model-routing.md`. That global file is the canonical source for
model identifiers; do not duplicate its identifiers here.

Choose the provider lane before recommending a model:

- Ordinary `claude` and RepoPrompt CE's `claude-rpce` use native Claude Pro.
- `claude-openlimits` and `claude-openlimits-rpce` use OpenLimits.

Use the coding model as the normal default. Reserve high reasoning for
OpenSpec proposals, installer transaction or rollback design, credential and
provider security, cross-harness ownership, ambiguous debugging, and hard
final review. Use the fast model for standalone summaries, command lookups,
artifact inventories, and low-risk documentation.

Routing is advisory. Recommend a switch once when a meaningful phase change
would materially benefit from another model, but do not claim that a switch
happened automatically or block work when the user keeps the current model.

A normal Claude Desktop chat does not automatically consume this repository
file merely because the checkout exists locally. Claude Code sessions launched
against this checkout do.
