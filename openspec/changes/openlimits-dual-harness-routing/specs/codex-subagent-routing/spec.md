## ADDED Requirements

### Requirement: Claude plugin delegation boundary
Codex work invoked through Claude's official Codex plugin SHALL be treated as already delegated by default. The receiving Codex root MUST perform the bounded task directly and MUST NOT create a second CSE delegation layer unless the handoff explicitly requests independent, non-overlapping subwork and the active depth and concurrency policies permit it.

#### Scenario: Claude plugin sends a routine implementation task
- **WHEN** Codex receives an approved bounded implementation task through Claude's official Codex plugin
- **THEN** the receiving Codex root performs the task directly and returns validation evidence without spawning a CSE implementer

#### Scenario: Plugin handoff explicitly requests independent review dimensions
- **WHEN** a Claude plugin handoff identifies independent read-only review dimensions and authorizes delegation
- **THEN** the Codex root delegates only to the appropriate CSE roles and remains within the configured depth, concurrency, and synthesis rules

### Requirement: Cross-application writer ownership
The Codex routing policy SHALL honor the sole-writer owner declared by a cross-harness handoff. Codex agents MUST remain read-only when another harness owns the shared checkout and SHALL accept write ownership only through an explicit handoff that identifies the active worktree and permitted file set.

#### Scenario: Claude retains write ownership
- **WHEN** Codex receives context from Claude but the handoff declares Claude as the writer
- **THEN** Codex limits its work to exploration or review and makes no repository changes

#### Scenario: Codex receives write ownership
- **WHEN** a valid handoff declares Codex as the sole writer for the identified worktree and files
- **THEN** Codex performs only the approved changes while Claude refrains from writing to that checkout
