## 1. Prerequisites and Scope Gates

- [x] 1.1 Confirm upstream PR #1 is merged and record the merged `master` base dependency before preparing a merge-ready branch.
- [x] 1.2 Re-verify the current Codex Pooler release, Codex CLI provider schema, backend route, license, and public compatibility guidance; pin the exact versions used by the guide and canary.
- [ ] 1.3 Confirm the pilot's upstream account and client use is authorized, and obtain separate explicit approval before provisioning Pooler, creating credentials, or running the live canary.

## 2. Synthetic Installer Coverage

- [x] 2.1 Extend `tests/test_codex_install.py` with synthetic top-level `model_provider`, `[model_providers.codex-pooler-ws]`, and optional `[mcp_servers.codex_pooler]` configuration containing no real hosts or secrets.
- [x] 2.2 Assert preview, first apply, and second apply preserve all unrelated provider and MCP values while the second apply reports no managed changes.
- [x] 2.3 Run the focused installer tests and confirm the new preservation scenarios pass without network access.

## 3. Experimental Interoperability Guide

- [x] 3.1 Add `docs/codex-pooler-canary.md` with version prerequisites, the disposable `CODEX_HOME` workflow, backend-compatible websocket provider fields, environment-only Pool API key handling, and an explicit experimental label.
- [x] 3.2 Document the native `cse_explorer` probe, session-resume procedure, conditional multi-upstream retry check, pass/fail/blocked/not-applicable evidence table, and payload-free evidence rules.
- [x] 3.3 Document rollback, key revocation, ordinary OpenLimits configuration protection, the ban on existing-session migration, and the separate Pool API key versus operator MCP token boundary.
- [x] 3.4 Add a concise optional-interoperability link to `README.md` without changing quick-start defaults or implying Pooler is installed or supported automatically.

## 4. Repository Validation

- [x] 4.1 Run the focused installer tests, the full test suite, and Ruff; resolve only failures caused by this change.
- [x] 4.2 Run an isolated synthetic `cse install-codex` preview/apply/no-op cycle and compare the provider and MCP tables before and after.
- [x] 4.3 Run `openspec validate codex-pooler-canary` and `git diff --check`, then inspect the exact changed-file set for scope compliance.
- [x] 4.4 Ask `cse_reviewer` for an independent read-only review of the guide, preservation test, security boundaries, and validation evidence; triage every finding in the root thread.

## 5. Authorized Live Canary

- [ ] 5.1 After the explicit external-action approval in task 1.3, provision or select the pinned external Pooler deployment, one dedicated test Pool, one dedicated Pool API key, and at least one authorized upstream account.
- [ ] 5.2 Record hashes and paths sufficient to prove the ordinary Codex configuration and session stores are unchanged, then configure and validate a disposable canary `CODEX_HOME` without copying existing sessions.
- [ ] 5.3 Run one bounded `cse_explorer` task and record redacted evidence for role selection, read-only sandbox, delegation depth, open-thread count, completion, and root synthesis.
- [ ] 5.4 Record sanitized Pooler evidence for release, route family, model, upstream label, status class, duration, timestamp, and websocket result without retaining request or response payloads.
- [ ] 5.5 Resume the canary-created session and verify upstream continuity; do not retag or edit any pre-existing user session.
- [ ] 5.6 If multiple authorized upstreams are available, run a separately controlled stateless retry test; otherwise record failover as not applicable.

## 6. Outcome and Rollback

- [ ] 6.1 Classify every required check as pass, fail, blocked, or not applicable and issue an interoperability recommendation only if all mandatory checks pass.
- [ ] 6.2 Revoke the dedicated Pool API key, remove disposable client state, and stop or separately hand off the external Pooler deployment while proving the ordinary Codex home remains unchanged.
- [x] 6.3 If the canary fails or evidence is incomplete, keep the guide experimental and make no provider-automation or default-provider recommendation.
- [ ] 6.4 If repeated canaries later justify provider automation, open a separate OpenSpec proposal rather than expanding this change.
