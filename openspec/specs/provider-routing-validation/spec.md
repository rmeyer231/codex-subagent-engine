# Provider Routing Validation Specification

## Purpose

Define isolated and live evidence requirements for provider routing, billing
attribution, credential redaction, and subscription-readiness decisions.

## Requirements

### Requirement: Isolated configuration canary
The validation workflow SHALL support a no-network canary that uses temporary Claude and Codex homes, a temporary launcher directory, a fake credential command, and stub harness executables. The canary SHALL prove target resolution, merge preservation, model routing, argument forwarding, rollback, idempotence, and credential redaction without reading or changing the user's real homes or Keychain.

#### Scenario: Isolated canary succeeds
- **WHEN** the canary runs against representative existing Claude and Codex configuration
- **THEN** every managed target matches the expected configuration, unrelated content is preserved, a second apply is unchanged, and no real global state is accessed

#### Scenario: Stub write fails during the canary
- **WHEN** the canary injects a failure after an earlier target was changed
- **THEN** all earlier changes are rolled back and the failure evidence remains free of credential values

### Requirement: Explicitly approved live canaries
The validation workflow SHALL keep networked and real-home canaries behind an explicit live option and MUST display the affected provider, model, path, and expected billing destination before execution. A live canary MUST use a bounded prompt and MUST NOT modify a production repository.

#### Scenario: User runs validation without the live option
- **WHEN** the validation command is invoked in its default mode
- **THEN** it runs only isolated checks and performs no provider request or real-home mutation

#### Scenario: User approves a live canary
- **WHEN** the user explicitly selects the live option after reviewing the plan
- **THEN** the validator runs only the declared bounded requests and records redacted evidence for each surface

### Requirement: Native Claude routing evidence
Live validation SHALL prove that Claude Desktop or the ordinary `claude` command remains on native Claude authentication and that `claude-openlimits` reaches OpenLimits. It SHALL separately prove that `claude-openlimits-rpce` reaches OpenLimits through RepoPrompt CE's `claude-rpce` wrapper. Evidence SHALL combine local effective-configuration checks with provider-side usage or request identifiers when the provider exposes them.

#### Scenario: Ordinary Claude canary runs
- **WHEN** the validator executes the native Claude canary
- **THEN** the effective process lacks managed OpenLimits overrides and the request is attributable to the native Claude account

#### Scenario: OpenLimits Claude canary runs
- **WHEN** the validator executes the `claude-openlimits` canary
- **THEN** the request is attributable to OpenLimits and uses the selected Claude-compatible model without exposing the token

#### Scenario: OpenLimits RepoPrompt CE canary runs
- **WHEN** the validator executes the `claude-openlimits-rpce` canary
- **THEN** the request is attributable to OpenLimits, uses the selected Claude-compatible model, and retains RepoPrompt CE MCP discovery without exposing the token

### Requirement: Codex surface routing evidence
Live validation SHALL prove OpenLimits routing independently for Codex CLI, Codex App, and a Codex job invoked through Claude's official Codex plugin. Each canary SHALL record the requested model alias, resolved provider, success or failure, and provider-side attribution when available.

#### Scenario: Codex CLI canary runs
- **WHEN** the validator executes a bounded Codex CLI prompt under the managed Codex home
- **THEN** the request uses the OpenLimits provider and the expected default or explicitly selected phase model

#### Scenario: Codex App canary runs
- **WHEN** the user completes the documented Codex App canary in a disposable test checkout
- **THEN** the resulting evidence confirms that the app used the same managed OpenLimits provider without allowing another harness to write concurrently

#### Scenario: Claude plugin invokes Codex
- **WHEN** the documented Claude plugin canary delegates a bounded read-only task to Codex
- **THEN** the task uses OpenLimits, returns its result to the owning Claude session, and does not start an unrequested nested CSE delegation

### Requirement: Redacted validation report
The validator SHALL produce a human-readable result matrix for every required surface with status, provider, model, billing destination, evidence source, and remediation. It MUST redact credentials, authorization headers, Keychain output, and secret-bearing environment values from standard output, errors, captured commands, fixtures, and saved reports.

#### Scenario: Validation report is generated
- **WHEN** isolated or live validation completes
- **THEN** the report contains one row per attempted surface and enough non-secret evidence to distinguish native Claude, OpenLimits, and manual ChatGPT Free paths

#### Scenario: Provider returns a secret-bearing error
- **WHEN** a provider or subprocess error includes a credential or authorization value
- **THEN** the validator replaces the sensitive value before displaying or saving the error

### Requirement: Subscription changes are gated by evidence
The workflow SHALL report the selected stack as ready only after the isolated canary passes and every required live surface has either passed or been explicitly waived by the user with a recorded reason. A failed, skipped, or ambiguous routing check MUST NOT be represented as proof that a paid subscription can be safely changed.

#### Scenario: All required evidence passes
- **WHEN** isolated validation and the native Claude, OpenLimits Claude, Codex CLI, Codex App, and Claude-plugin canaries all pass
- **THEN** the report states that the technical routing is ready and that any subscription change remains a separate manual decision

#### Scenario: Billing attribution is ambiguous
- **WHEN** a request succeeds but its provider or billing destination cannot be proven
- **THEN** the report marks that surface unresolved and blocks the readiness conclusion

#### Scenario: User waives a live surface
- **WHEN** the user explicitly waives a required live canary
- **THEN** the report records the reason and distinguishes the waiver from a passing result
