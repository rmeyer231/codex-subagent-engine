# Dual-Harness Routing Specification

## Purpose

Define provider, model, ownership, review, and handoff boundaries across Claude,
Codex, RepoPrompt CE, OpenLimits, and ChatGPT Free surfaces.

## Requirements

### Requirement: Provider boundaries by application surface
The routing policy SHALL keep Claude Desktop, the ordinary `claude` command, and RepoPrompt CE's `claude-rpce` wrapper authenticated through native Claude Pro; SHALL route only the explicit `claude-openlimits` and `claude-openlimits-rpce` launchers through OpenLimits; and SHALL route Codex CLI, Codex App, and Codex jobs invoked by Claude's official Codex plugin through the configured OpenLimits provider. The policy MUST NOT silently move a session between native and OpenLimits billing paths.

#### Scenario: User opens Claude Desktop or runs the ordinary Claude command
- **WHEN** the user starts Claude Desktop, Claude Code Desktop, Cowork, or the ordinary `claude` command
- **THEN** the session uses native Claude Pro authentication without global OpenLimits base URL or credential overrides

#### Scenario: User explicitly selects the OpenLimits Claude lane
- **WHEN** the user runs `claude-openlimits`
- **THEN** the launcher obtains the OpenLimits credential at runtime and starts Claude against the OpenLimits endpoint

#### Scenario: User selects RepoPrompt CE with native Claude
- **WHEN** the user runs RepoPrompt CE's generated `claude-rpce` wrapper
- **THEN** RepoPrompt CE configures MCP discovery while Claude remains on native authentication

#### Scenario: User selects RepoPrompt CE with OpenLimits
- **WHEN** the user runs `claude-openlimits-rpce`
- **THEN** the managed launcher obtains the OpenLimits credential at runtime and invokes `claude-rpce` with process-scoped gateway variables

#### Scenario: User starts a managed Codex surface
- **WHEN** the user starts Codex CLI, Codex App, or a Codex job through Claude's official Codex plugin under the managed profile
- **THEN** the Codex process uses the OpenLimits provider configured in the shared Codex home

#### Scenario: A configured provider is unavailable
- **WHEN** a native or OpenLimits provider cannot authenticate or serve the requested model
- **THEN** the surface reports the provider failure without silently switching to a different billing path

### Requirement: Canonical advisory model routing
The installed routing policy SHALL use the same phase semantics with surface-appropriate OpenLimits models. Claude SHALL recommend `anthropic/fable-5` for explicit architecture and synthesis, `anthropic/claude-sonnet-5` for implementation, TDD, and general coding, and `anthropic/claude-haiku-4.5` for summarization and low-stakes work. Codex SHALL recommend `openai/gpt-5.6-sol` for planning, review, and hard debugging, SHALL default to `openai/gpt-5.6-terra` for implementation, and SHALL recommend `openai/gpt-5.6-luna` for routine low-cost work. These mappings MUST remain advisory and MUST NOT block work or require a model switch.

#### Scenario: Proposal or architecture work begins
- **WHEN** a harness selects a model for proposal, specification, brainstorming, or architecture work
- **THEN** it recommends `openai/gpt-5.6-sol` in Codex or `anthropic/fable-5` in the OpenLimits Claude lane and continues with the active model if the user does not switch

#### Scenario: Implementation work begins
- **WHEN** a harness selects a model for implementation, TDD, or general coding
- **THEN** it recommends and defaults to `openai/gpt-5.6-terra` in Codex or recommends `anthropic/claude-sonnet-5` in the OpenLimits Claude lane

#### Scenario: Low-stakes work begins
- **WHEN** a task is limited to summarization, a quick lookup, or another low-stakes operation
- **THEN** the harness recommends `openai/gpt-5.6-luna` in Codex or `anthropic/claude-haiku-4.5` in the OpenLimits Claude lane without making the recommendation a phase gate

### Requirement: One OpenSpec phase owner
Exactly one root harness SHALL own OpenSpec phase gates, user interaction, and the final completion claim for a change. A receiving harness SHALL treat an OpenSpec artifact or explicit handoff as bounded delegated work and MUST NOT independently advance the change to a later phase.

#### Scenario: Claude delegates implementation to Codex
- **WHEN** Claude owns the OpenSpec change and invokes Codex for an approved implementation task
- **THEN** Codex performs only the delegated task and returns evidence without applying a new phase transition

#### Scenario: Codex owns the OpenSpec change
- **WHEN** Codex is the declared root harness for the change
- **THEN** Codex owns proposal, apply, verify, and archive gates and Claude contributes only through explicit bounded handoffs

### Requirement: Bounded review loops
The workflow SHALL limit routine cross-harness review to one planning review before implementation and one final review after implementation. The workflow SHALL permit at most one correction and re-review cycle after a failed final review; additional cycles MUST require explicit user direction.

#### Scenario: A plan is ready for review
- **WHEN** the owning harness completes the proposal and design artifacts
- **THEN** it requests at most one independent planning review before implementation begins

#### Scenario: Final review finds actionable defects
- **WHEN** the independent final review reports accepted defects
- **THEN** the owner runs at most one correction and re-review cycle and then stops for user direction if blocking findings remain

### Requirement: Explicit handoff and sole-writer ownership
Every Claude-to-Codex or Codex-to-Claude handoff that can modify a shared checkout SHALL identify the owning harness, branch or worktree, objective, permitted file set, artifact paths, current phase, and required validation. At most one harness SHALL hold write ownership of a checkout at a time.

#### Scenario: Write ownership moves to Codex App
- **WHEN** Claude hands an implementation task to Codex App in the same checkout
- **THEN** the handoff records Codex as the sole writer and Claude performs no writes until ownership is returned

#### Scenario: Both harnesses need concurrent implementation access
- **WHEN** Claude and Codex need to implement independent work concurrently
- **THEN** they use separate worktrees with disjoint write sets rather than sharing write ownership

#### Scenario: A handoff is missing ownership metadata
- **WHEN** a receiving harness cannot determine the active writer, worktree, or permitted files
- **THEN** it remains read-only and requests a corrected handoff before modifying files

### Requirement: ChatGPT Free remains an unmanaged fallback
The workflow SHALL preserve ChatGPT Free as a separate interactive fallback and MUST NOT represent it as API capacity, an OpenLimits credential source, or a substitute for the managed Codex provider.

#### Scenario: OpenLimits is unavailable
- **WHEN** the user elects to use ChatGPT Free while OpenLimits is unavailable
- **THEN** the workflow treats that work as a separate manual session and requires an explicit handoff before its output changes the managed checkout
