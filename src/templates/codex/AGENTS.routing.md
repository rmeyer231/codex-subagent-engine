<!-- BEGIN CSE-MANAGED -->
<!--
  Packaged source for the CSE managed routing block.

  This file is the packaged source filename shipped inside the distribution
  wheel. Codex does NOT auto-discover it; the standalone global instructions
  Codex auto-discovers are ~/.codex/AGENTS.override.md and ~/.codex/AGENTS.md.

  The cse install-codex installer (Task 3) reads the managed block between
  the BEGIN/END markers in this source and inserts it into ~/.codex/AGENTS.md,
  which is the auto-discovery destination for global instructions. This file
  itself is never copied to ~/.codex/AGENTS.routing.md.
-->

# CSE Native Subagent Routing

The Codex Subagent Engine (CSE) routes bounded, independent work to focused
native Codex roles. The root thread owns decomposition, phase gates, steering,
result synthesis, and the final completion claim; custom subagents never
recursively delegate under the depth-one global default.

## Role-to-phase rows

| Phase                                | Role               | Default sandbox_mode |
| ------------------------------------ | ------------------ | -------------------- |
| Exploration of unfamiliar code       | cse_explorer       | read-only            |
| Proposal / spec / architecture draft | cse_planner        | read-only            |
| Approved implementation work         | cse_implementer    | workspace-write      |
| Independent review of completed work | cse_reviewer       | read-only            |

The selected role inherits the parent model. Parent session sandbox and
approval overrides remain authoritative.

## Phase gates owned by the root thread

The root thread is the only place where phase transitions happen. Before
dispatching work from the next phase it MUST wait for:

1. PLAN / SPEC proposals to be approved or revised.
2. Implementer reports to be reviewed (by cse_reviewer when independent
   verification is requested, otherwise by the root itself).
3. Reviewer findings to be triaged and either accepted (open issues for the
   implementer) or rejected (with rationale).

The root thread MUST consult ~/.codex/model-routing.md before selecting a phase model.

Subagents MUST NOT advance to the next phase on their own; they report and
return. The root thread is the only place where the final answer is
synthesized and the work is claimed complete.

## When NOT to delegate

The root thread performs the work directly without spawning a subagent when:

- the task is trivial (a single file lookup, a one-line edit, a small
  reformat) and delegation would add more overhead than it saves;
- the work is strictly sequential and each step depends on the prior step's
  result, so there is nothing to parallelize;
- the user asked a direct question whose answer fits in the root context;
- multiple owners would otherwise be required for the same file set
  (see parallel write isolation below).

## Result synthesis

Subagent output is raw material, not the answer. The root thread evaluates
each delegated result against the original request, cross-checks citations,
resolves conflicts between reviewers, and writes the synthesized reply itself.
Forwarding an unreviewed subagent report to the user is a phase-gate failure.

## Parallel write isolation

Concurrent subagents MUST NOT own overlapping files or dependent write steps.
When two proposed parallel slices would touch the same file or one slice's
output is required as another's input, the root thread serializes them or
assigns the combined work to one cse_implementer. Parallel delegation is
permitted only when write sets are disjoint AND there is no ordering
dependency. The configured max_threads = 4 cap is the upper bound on
concurrent open agents, not a target.

## Packaged source vs. installed destination

This file is the **packaged source** for the CSE managed routing block
inside the distribution wheel. Its filename (`AGENTS.routing.md`) is
preserved so the source can be tracked, reviewed, and re-rendered by the
installer.

The installed destination for the managed block is `~/.codex/AGENTS.md`,
which Codex auto-discovers as global instructions (alongside the
optional `~/.codex/AGENTS.override.md`). The installer extracts the
managed block from this packaged source and inserts it into
`~/.codex/AGENTS.md`; nothing in this bundle is written to
`~/.codex/AGENTS.routing.md`.

<!-- END CSE-MANAGED -->
