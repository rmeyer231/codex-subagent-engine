## Why

Codex Pooler could complement CSE by supplying upstream-account capacity routing, but its value and compatibility with the existing OpenLimits-backed native Codex workflow are not yet proven. An isolated, opt-in canary is needed before CSE documents or automates any integration.

## What Changes

- Define a repeatable Codex Pooler interoperability canary that uses an isolated `CODEX_HOME` or explicit opt-in profile and leaves the user's default provider unchanged.
- Establish pass/fail evidence for native CSE role selection, sandboxing, depth and thread limits, root synthesis, provider routing, websocket behavior, and session continuity.
- Add synthetic regression coverage proving `cse install-codex` preserves unrelated model-provider and operator-MCP configuration.
- Document prerequisites, credential boundaries, version pinning, rollback, and the requirement to confirm authorized upstream-account use.
- Keep Pooler external and optional: do not vendor its code, add it as a runtime dependency, migrate existing Codex session state, change model-routing aliases, or route `cse run` and `cse batch` through its narrow `/v1` API.

## Capabilities

### New Capabilities

- `codex-pooler-interoperability`: Defines isolation, configuration-preservation, live-canary, evidence, security, and rollback requirements for optional Codex Pooler use with native CSE subagents.

### Modified Capabilities

None.

## Impact

- Repository impact is limited to an interoperability guide, synthetic installer regression coverage, and the OpenSpec artifacts for this change.
- The live canary requires a separately operated, version-pinned Codex Pooler instance, a dedicated Pool API key, and an authorized upstream account; none are bundled with CSE.
- The user's existing `openlimits` provider, model-routing aliases, global Codex home, sessions, and legacy Anthropic manifest engine remain unchanged.
- No public API, manifest format, default-provider behavior, or production dependency changes are introduced.
