## ADDED Requirements

### Requirement: Focused native agent roles
The routing bundle SHALL define distinct native Codex profiles named `cse_explorer`, `cse_planner`, `cse_implementer`, and `cse_reviewer`, each with a name, selection description, and bounded developer instructions.

#### Scenario: Agent profiles are installed
- **WHEN** the routing bundle is applied to a Codex home
- **THEN** all four agent files exist under `<CODEX_HOME>/agents/` and satisfy the native custom-agent schema

#### Scenario: Built-in profiles remain untouched
- **WHEN** the routing bundle is installed
- **THEN** it does not create custom profiles named `default`, `worker`, or `explorer`

### Requirement: Role-specific permissions
The explorer, planner, and reviewer profiles SHALL default to read-only operation, while the implementer profile SHALL be limited to workspace-scoped writes and SHALL remain subject to the parent session's live approval and sandbox policy.

#### Scenario: Read-only agent is selected
- **WHEN** Codex delegates discovery, planning, or review work
- **THEN** the selected profile cannot modify repository files by default

#### Scenario: Implementer is selected
- **WHEN** Codex delegates an approved implementation task
- **THEN** the profile may write only within the active workspace unless the parent session separately authorizes broader access

### Requirement: Deterministic task routing
The global routing policy SHALL map unfamiliar-code exploration to `cse_explorer`, PLAN and SPEC work to `cse_planner`, approved code changes to `cse_implementer`, and independent validation to `cse_reviewer`.

#### Scenario: Independent review dimensions are requested
- **WHEN** a task contains two or more bounded, independent review dimensions
- **THEN** the root thread delegates each dimension to the appropriate read-only role and waits for all results before synthesizing them

#### Scenario: Work is trivial or strictly sequential
- **WHEN** delegation would not materially improve speed, quality, or context isolation
- **THEN** the root thread performs the work directly without spawning a subagent

### Requirement: Parallel write isolation
The routing policy MUST prevent concurrent subagents from owning overlapping files or dependent write steps.

#### Scenario: Two implementation slices touch the same file
- **WHEN** proposed parallel tasks have overlapping write sets
- **THEN** the root thread serializes the tasks or assigns the combined work to one implementer

#### Scenario: Implementation slices are independent
- **WHEN** proposed write tasks have disjoint files and no ordering dependency
- **THEN** the root thread may delegate them in parallel within the configured thread limit

### Requirement: Root-owned orchestration and phase gates
The root thread SHALL retain responsibility for task decomposition, user-facing phase gates, subagent steering, result synthesis, and the final completion claim. Subagents MUST NOT recursively delegate under the initial configuration.

#### Scenario: A subagent finishes its assignment
- **WHEN** a delegated agent returns a result
- **THEN** the root thread evaluates and synthesizes that result rather than forwarding it unreviewed

#### Scenario: A phase requires user approval
- **WHEN** the global or project instructions require a phase gate
- **THEN** the root thread waits for approval before dispatching work from the next phase

### Requirement: Conservative concurrency
The global Codex configuration SHALL set `max_threads` to 4 and `max_depth` to 1, with interruption messages enabled.

#### Scenario: A broad request contains more than four work units
- **WHEN** more than four independent units are eligible for delegation
- **THEN** Codex runs no more than four open agent threads concurrently

#### Scenario: A child attempts delegation
- **WHEN** a depth-one subagent would otherwise spawn another agent
- **THEN** the configured depth limit prevents the nested spawn

### Requirement: Parent model inheritance
Custom agent files SHALL inherit the active parent model until role-specific native model identifiers are explicitly verified and approved.

#### Scenario: Parent model changes
- **WHEN** the user selects a different supported model for the root session
- **THEN** spawned custom roles inherit that model unless a later approved configuration explicitly pins one
