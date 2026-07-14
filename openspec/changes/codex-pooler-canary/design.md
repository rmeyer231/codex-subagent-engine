## Context

CSE has two intentionally separate execution paths: the legacy Anthropic-backed manifest engine and a native Codex routing bundle installed under `CODEX_HOME`. The native bundle manages agent roles, `[agents]` limits, global routing guidance, and model inheritance; it deliberately preserves unrelated provider configuration. The user's ordinary Codex configuration currently selects OpenLimits, and the existing phase-routing aliases depend on that provider.

Codex Pooler is a separately deployed gateway that can expose a Codex backend-compatible provider while selecting among authorized upstream accounts. It may add useful credential isolation, capacity routing, and sanitized operational metadata, but it also introduces third-party release churn, centralized credentials, a database-backed service, and account-authorization and license constraints. The prior native-routing work was merged into the fork's `master` through PR #1, so this change is based on that merged capability.

## Goals / Non-Goals

**Goals:**

- Produce repeatable evidence about whether a pinned Pooler release preserves native CSE behavior.
- Keep the experiment isolated from the ordinary Codex home, OpenLimits provider, phase aliases, and existing sessions.
- Prove with a synthetic regression test that CSE installer reruns preserve provider and MCP tables.
- Define observable pass, fail, blocked, and not-applicable outcomes across both CSE and Pooler.
- Make rollback consist of revoking test credentials and removing disposable state rather than repairing the user's primary configuration.

**Non-Goals:**

- Make Pooler the default Codex provider or add provider selection to `cse install-codex`.
- Vendor Pooler code, add it as a dependency, deploy it from CSE, or offer it as a managed service.
- Replace OpenLimits model aliases or pin CSE agent roles to Pooler-specific model identifiers.
- Migrate or retag existing Codex JSONL or SQLite session state.
- Add Pooler as a backend for `cse run` or `cse batch`.
- Treat one successful request as evidence of retry, failover, or production readiness.

## Decisions

### Prefer a disposable Codex home over modifying the ordinary profile

The first canary will use a dedicated temporary or operator-named `CODEX_HOME`. CSE will install its normal routing bundle there, and the Pooler provider block will exist only in that target. A named provider profile may be documented later, but it is not the primary isolation mechanism.

This is preferred over editing `~/.codex/config.toml` because it gives the canary independent provider, agent, and session state and makes rollback a directory-level operation. It also avoids relying on profile precedence details before native behavior has been proven.

### Keep provider setup operator-owned and explicit

The guide will describe the minimum backend-compatible provider fields for the pinned Pooler version, but CSE will not generate them. The Pool API key will be read from a dedicated environment variable. Pooler's operator MCP connection will be omitted from the first run and, if evaluated later, will use a separate operator token.

An installer flag was considered and rejected for this change because automation would imply a supported integration before the live compatibility evidence exists. Persisting raw keys in TOML was rejected because it broadens secret exposure and conflicts with the existing environment-key pattern.

### Separate deterministic preservation coverage from the live canary

`tests/test_codex_install.py` will gain a synthetic configuration fixture containing a selected provider, a Pooler-shaped `[model_providers.*]` table, and an optional MCP table. The test will preview, apply, and rerun the installer and will assert that only CSE-managed content changes.

This test will not contact Pooler and will not use real credentials. Networked integration in ordinary CI was rejected because it would require third-party infrastructure and secrets and could turn release drift into unrelated CI failures.

### Use a bounded native explorer task as the control-plane probe

The live canary will ask `cse_explorer` to map one small, non-sensitive area of this repository. The root will record the selected role, read-only sandbox, open-thread count, lack of nested delegation, completion, and root synthesis. A single task minimizes spend and isolates provider compatibility from broader workflow complexity.

Implementation or write-enabled roles were rejected for the first canary because they add repository mutation risk without improving evidence about transport or routing compatibility.

### Test the native backend route and websocket path first

The isolated Codex client will use Pooler's `/backend-api/codex` route with a Responses provider and websocket support. The narrow `/v1` SDK route is outside the native canary contract. Websocket failure will be recorded before any optional HTTP comparison, so an HTTP success cannot conceal a native websocket incompatibility.

This matches the runtime surface used by Codex CLI and preserves the features the CSE workflow depends on. Treating Pooler's SDK translation layer as equivalent was rejected because it has narrower route coverage.

### Require evidence from both control and provider layers

The evidence record will contain a checklist with pinned CSE, Codex, and Pooler versions; isolated target; CSE role/sandbox/depth/thread observations; Pooler route/model/upstream/status/duration/timestamp metadata; session-resume result; and explicit statuses for each check. It will contain no prompts, completions, repository contents, account identifiers, emails, tokens, request bodies, response bodies, or transcripts.

A canary passes only when every mandatory control-plane, transport, routing, preservation, and session check is observed. Multi-upstream failover is required only when the authorized pilot Pool actually has multiple eligible upstreams; otherwise it is marked not applicable.

### Do not migrate existing sessions

Session continuity will be tested by starting and resuming a conversation created entirely inside the disposable canary target. Existing user sessions will not be retagged or copied. This confines state changes and prevents an experiment from rewriting the ordinary Codex session database.

### Base the canary on the merged native-routing capability

This SPEC may be reviewed independently, but implementation and any follow-up PR must declare that it depends on the native routing capability merged into the fork's `master` by PR #1. The canary branch is based on that merged `master` commit rather than the pre-merge development branch.

Using the merged base keeps the dependency visible and makes the canary documentation usable against the fork's current `master`, which contains the native installer.

## Risks / Trade-offs

- **Third-party behavior and docs may drift rapidly** → Pin the exact Pooler image/release and record Codex and CSE revisions in every evidence run.
- **A successful single-account run can overstate pooling value** → Separate baseline compatibility from multi-upstream failover and mark unavailable dimensions not applicable.
- **Centralized upstream credentials increase blast radius** → Use a dedicated test Pool/key, operator-controlled encrypted storage, minimal scope, rotation, and prompt-free evidence.
- **Provider changes may affect account-dependent Codex features** → Keep the ordinary provider untouched and explicitly observe native threads, tools, websocket transport, and session resume in the disposable target.
- **A manual canary is less repeatable than CI** → Use a precise checklist and synthetic regression test while keeping secrets and external infrastructure out of CI.
- **Self-hosting creates operational cost without guaranteed ROI** → Stop after the pilot unless shared authorized capacity or centralized routing evidence solves a measured need.
- **ELv2 and upstream-account terms constrain deployment choices** → Keep Pooler external, do not offer it as a CSE-managed service, and require operator confirmation of authorized use.
- **The base feature may drift after merge** → Keep the canary branch based on the fork's current `master` and re-run the pinned validation when the native routing bundle changes.

## Migration Plan

1. After IMPLEMENT approval and a switch to the implementation model, add the synthetic provider-preservation test and the opt-in canary guide only.
2. Run repository tests, lint, OpenSpec validation, and an isolated installer preview/apply/no-op cycle using synthetic values.
3. Obtain explicit authorization before any external deployment or credential setup.
4. Deploy a version-pinned Pooler instance outside CSE, create a dedicated test Pool and key, and configure a disposable `CODEX_HOME`.
5. Run the bounded explorer and session-resume canary; run controlled stateless failover only if multiple authorized upstreams are available.
6. Record redacted evidence and classify the result. A failed or blocked run produces no recommendation to automate provider setup.
7. Revoke the test key, remove disposable client state, and stop or retain the external Pooler instance according to the operator's separate decision.
8. If repeated canaries establish value, propose any profile automation as a new OpenSpec change.

## Open Questions

- How many upstream Codex accounts and trusted clients are authorized for the pilot?
- Does the pinned Pooler release expose a model compatible with the active Codex session and the intended phase without changing the OpenLimits aliases?
- Which Codex CLI build will be the supported canary baseline?
- Is one baseline upstream sufficient for the first pass, with failover explicitly deferred, or are multiple authorized upstreams available now?
- Which future native-routing changes would require a new canary baseline?
- Has the organization accepted the Pooler credential boundary, upstream account terms, and ELv2 deployment constraints?
