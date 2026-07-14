# codex-pooler-interoperability Specification

## Purpose
TBD - created by archiving change codex-pooler-canary. Update Purpose after archive.
## Requirements
### Requirement: Opt-in canary isolation
The interoperability canary SHALL require an explicitly selected disposable `CODEX_HOME` or named opt-in provider profile and MUST NOT change the provider selected by the user's ordinary Codex configuration.

#### Scenario: Disposable Codex home is selected
- **WHEN** the operator prepares the first canary run
- **THEN** all canary provider, agent, and session state is written under an explicitly identified disposable target rather than the ordinary Codex home

#### Scenario: No isolated target is supplied
- **WHEN** the operator cannot identify an isolated `CODEX_HOME` or opt-in profile
- **THEN** the canary stops before installing CSE files or configuring Codex Pooler

### Requirement: Pinned backend-compatible provider
The canary SHALL pin an exact Codex Pooler release and SHALL configure Codex CLI against Pooler's `/backend-api/codex` compatibility route using a websocket-capable Responses provider. The canary MUST NOT use the narrow `/v1` SDK route as a substitute for native Codex compatibility.

#### Scenario: Provider configuration is prepared
- **WHEN** the operator configures the isolated Codex client
- **THEN** the configuration records the Pooler release, backend base URL, Responses wire API, websocket support, and environment-variable key name without embedding a credential value

#### Scenario: Only the narrow SDK route is available
- **WHEN** the candidate Pooler deployment cannot serve the native backend compatibility route
- **THEN** the native CSE canary is blocked and the result is recorded as incompatible

### Requirement: Separate credential boundaries
The canary MUST use a dedicated Pool API key supplied through an environment variable, MUST omit the optional operator MCP connection from the first runtime test, and MUST NOT copy upstream credentials or `auth.json` material into repository files, evidence, prompts, or shell history examples.

#### Scenario: Runtime authentication is configured
- **WHEN** the isolated Codex client starts the canary
- **THEN** it reads only the dedicated Pool API key from the named environment variable and no raw secret is persisted in the canary artifacts

#### Scenario: Operator metadata is evaluated later
- **WHEN** an operator chooses to test Pooler's MCP endpoint after the runtime canary passes
- **THEN** a separate operator-scoped MCP token is used and the Pool API key is not reused for MCP authentication

### Requirement: Preserve unrelated provider configuration
The CSE installer SHALL preserve an existing top-level `model_provider`, all `[model_providers.*]` tables, and any optional Pooler MCP table while updating only its managed `[agents]` keys and managed files.

#### Scenario: Synthetic Pooler configuration is installed
- **WHEN** `cse install-codex` previews, applies, and reruns against a temporary Codex home containing synthetic Pooler provider and MCP tables
- **THEN** the unrelated provider and MCP values remain semantically unchanged and the second apply reports no managed changes

#### Scenario: Existing OpenLimits configuration is present
- **WHEN** the ordinary user configuration selects `openlimits`
- **THEN** the canary workflow leaves that selection and its provider table unchanged

### Requirement: Native CSE behavior evidence
The live canary SHALL run one bounded unfamiliar-code exploration through `cse_explorer` and SHALL collect evidence that the agent is read-only, does not recursively delegate, returns to the root thread for synthesis, and operates within the configured thread limit.

#### Scenario: Explorer canary succeeds
- **WHEN** the root thread delegates the bounded exploration through the Pooler-backed parent session
- **THEN** the observed role, sandbox, delegation depth, thread count, completion status, and root synthesis all match the native CSE routing specification

#### Scenario: CSE control behavior differs
- **WHEN** the Pooler-backed session loses role selection, read-only enforcement, depth-one delegation, thread limits, or root synthesis
- **THEN** the canary fails and no Pooler interoperability recommendation is made

### Requirement: Pooler routing and transport evidence
The live canary SHALL verify that the request reaches the pinned Pooler deployment, uses the expected model and backend route, selects an eligible upstream, and completes over the configured transport without exposing request payloads.

#### Scenario: Pooler-backed request completes
- **WHEN** the explorer task finishes successfully
- **THEN** sanitized Pooler metadata identifies the route family, model, upstream label, status class, duration, and timestamp for the canary request

#### Scenario: Websocket transport is unavailable
- **WHEN** the configured websocket provider cannot complete the native canary
- **THEN** the failure is recorded before any optional HTTP fallback is evaluated, and the websocket result is not reported as passing

### Requirement: Session continuity and bounded failover
The canary SHALL prove that a new Pooler-backed session can resume on its owning upstream. If the authorized test Pool has multiple eligible upstreams, a separate controlled retry test SHALL prove that stateless failover is bounded without moving an existing session to a different upstream.

#### Scenario: Session resumes
- **WHEN** the root session is closed and resumed from the isolated canary state
- **THEN** the resumed turn remains attached to the upstream assignment that owns the session and completes without retagging existing user sessions

#### Scenario: Multiple test upstreams are available
- **WHEN** a retryable failure is safely induced for a stateless synthetic request
- **THEN** Pooler records the bounded retry or failover while session-bound work remains pinned

#### Scenario: Only one authorized upstream is available
- **WHEN** the pilot Pool has one eligible upstream
- **THEN** stateless failover is recorded as not applicable rather than inferred from an ordinary successful request

### Requirement: Redacted evidence and explicit outcome
The canary SHALL produce a redacted evidence record that distinguishes pass, fail, blocked, and not-applicable checks. It MUST NOT contain prompts, completions, repository contents, raw account identifiers, emails, tokens, cookies, request bodies, response bodies, or session transcripts.

#### Scenario: Required evidence is complete
- **WHEN** every mandatory CSE, transport, routing, preservation, and session check passes
- **THEN** the result may recommend documenting Pooler as an optional interoperable provider for the pinned versions tested

#### Scenario: Evidence is missing or contradictory
- **WHEN** a mandatory check is failed, blocked, unobserved, or supported only by an assumption
- **THEN** the result does not recommend provider automation or a default-provider change

### Requirement: Reversible external integration
The canary SHALL keep Codex Pooler external to CSE, SHALL avoid existing-session migration, and SHALL provide rollback by removing the disposable target or opt-in profile and stopping the test deployment without altering the ordinary Codex home.

#### Scenario: Canary is rolled back
- **WHEN** the pilot is complete or fails
- **THEN** the isolated client configuration, Pool API key, and test deployment can be revoked or removed without restoring user session databases or repository code

#### Scenario: Deeper integration is proposed
- **WHEN** a later change would vendor Pooler code, add a runtime dependency, modify default provider selection, or route `cse run` or `cse batch` through Pooler
- **THEN** that work requires a separate approved OpenSpec proposal and is not authorized by this capability

