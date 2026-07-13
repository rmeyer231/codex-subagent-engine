<!-- BEGIN CSE-MANAGED -->
<!--
  Managed routing source for global Codex native subagent routing.
  Edit only by re-running the cse install-codex installer with an explicit
  --apply. The installer copies this file to ~/.codex/AGENTS.routing.md
  and inserts a managed block into the user's AGENTS.md that points at it.
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

## Canonical path

This file is the managed routing source. The installer copies it to the
canonical lowercase path `~/.codex/AGENTS.routing.md` so repository-local
guidance and the global managed AGENTS block can both reference it by the
same path on every machine.

<!-- END CSE-MANAGED -->
