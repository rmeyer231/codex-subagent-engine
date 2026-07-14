## 1. Resolve Contracts and Establish Baselines

- [x] 1.1 Map callers of `codex_global.plan_install()` and `apply_plan()`, record the current CLI/test baseline, and identify the smallest reusable interfaces that leave `install-codex` behavior unchanged.
- [x] 1.2 Verify the current OpenLimits endpoint, Keychain service/account convention, Claude gateway environment variables, Max-plan model catalog, and exact Claude/Codex model aliases; record any approved corrections in the change artifacts before coding provider constants.
- [x] 1.3 Verify the installed Claude Codex plugin's command and effective `CODEX_HOME`, and add a disposable plugin-canary fixture that does not call a live provider.
- [x] 1.4 Add failing tests for provider boundaries, advisory phase mappings, plugin delegation limits, required handoff fields, and package-data consistency.

## 2. Canonical Policy and Packaged Assets

- [x] 2.1 Add a declarative dual-harness routing policy resource containing phase semantics, Claude/Codex aliases, default model, surface providers, review limits, and handoff fields.
- [x] 2.2 Add packaged Claude routing, model-routing, and `claude-openlimits` launcher templates that render from the canonical policy without embedding a credential.
- [x] 2.3 Extend the Codex managed routing guidance for plugin-origin delegation and cross-application sole-writer ownership while retaining the existing four CSE roles and inheritance behavior.
- [x] 2.4 Add package validators and tests that prove both harness renderings match the canonical policy, managed markers are complete, and wheel/sdist package data includes every new asset.

## 3. Composite Planning and Safe Merges

- [x] 3.1 Add `src/dual_harness_global.py` plan/result/error types and target resolution for explicit Claude home, Codex home, launcher directory, and backup root values.
- [x] 3.2 Reuse the existing Codex install plan and layer the OpenLimits provider, command-backed auth, `openai/gpt-5.6-terra` default, and cross-harness guidance without changing unrelated TOML tables or existing `install-codex` output.
- [x] 3.3 Implement narrow Claude JSON and managed-Markdown merges that remove only documented non-secret OpenLimits overrides, preserve plugins/hooks/MCP/prose, and leave ordinary Claude authentication native.
- [x] 3.4 Implement redacted Keychain and legacy-credential preflight checks that reject raw-token arguments, never execute or print secret output during preview, and stop apply before mutation when plaintext is detected or the Keychain item is unavailable.
- [x] 3.5 Render the launcher with process-scoped OpenLimits variables, exact argument/exit-status forwarding, missing-credential failure handling, and executable permissions.
- [x] 3.6 Add preservation, conflict, redaction, alternate-home, and preview-no-write tests using only temporary homes and fake credential commands.

## 4. Transactional Apply and Rollback

- [x] 4.1 Implement target-state rechecks, timestamped transaction manifests, backups of all existing non-secret targets, and atomic writes across Claude, Codex, and launcher destinations.
- [x] 4.2 Implement post-write bundle validation plus automatic restoration of every earlier mutation when any write or validation step fails.
- [x] 4.3 Implement explicit rollback by transaction identifier without modifying Keychain content or subscription state.
- [x] 4.4 Add injected-failure tests at every write and validation boundary, including rollback-failure reporting, missing-file restoration, launcher mode restoration, and retained backups.
- [x] 4.5 Add double-apply tests proving byte-identical managed output, no duplicate blocks, no unnecessary backups, and no writes for an unchanged plan.

## 5. CLI Integration and Compatibility

- [x] 5.1 Add preview-first `cse install-openlimits-stack` arguments for apply, rollback, alternate targets, Keychain identifiers, and explicit conflict resolution, with redacted deterministic output and stable exit codes.
- [x] 5.2 Add CLI tests for preview, conflict, apply, no-op, rollback, missing Keychain, legacy plaintext credential, and operational failure paths.
- [x] 5.3 Run the existing `install-codex`, `run`, and `batch` CLI tests unchanged and add regression assertions that their options and behavior remain compatible.

## 6. Isolated and Live Validation Workflow

- [x] 6.1 Add preview-first `cse validate-openlimits-stack` with a default no-network canary using temporary homes, stub Claude/Codex executables, a fake credential command, and injected provider evidence.
- [x] 6.2 Make the isolated canary verify target resolution, merge preservation, model routing, launcher forwarding, rollback, idempotence, real-home isolation, and credential redaction.
- [x] 6.3 Add explicitly gated live Claude and Codex CLI canaries that print the provider, model, path, bounded prompt, and expected billing destination before each request.
- [x] 6.4 Add guided Codex App and Claude-plugin canary steps that use a disposable checkout, record effective `CODEX_HOME`, enforce sole-writer ownership, and distinguish user-recorded evidence from automated evidence.
- [x] 6.5 Add the redacted validation matrix with pass, fail, unresolved, and waived states; require an evidence source and reason for every billing attribution or waiver.
- [x] 6.6 Add tests proving default validation performs no network or real-home access and secret-bearing subprocess/provider errors are redacted in output and saved reports.

## 7. Documentation and Repository Validation

- [x] 7.1 Update README and operator guidance for the OpenLimits Max plus Claude Pro plus ChatGPT Free surface map, model workflow, handoff protocol, Keychain provisioning, preview/apply/rollback, and failure recovery.
- [x] 7.2 Update `openspec/config.yaml` project context with the new commands, managed destinations, security boundary, and validation expectations.
- [x] 7.3 Run the full test suite, Ruff checks, package build, installed-wheel smoke tests, secret scans over fixtures/output, and `openspec validate openlimits-dual-harness-routing`; fix every regression before rollout.
- [x] 7.4 Run the isolated canary twice plus an injected-failure rollback canary and save redacted evidence that the second apply is a no-op and real global state was untouched.

## 8. User-Approved Global Rollout

- [x] 8.1 Run a read-only real-home preview and review the exact targets, provider/default-model changes, conflicts, credential findings, backup root, and canary plan with the user.
- [x] 8.2 Pause for the user to rotate the exposed OpenLimits token, provision the replacement Keychain item, remove the legacy plaintext field, and confirm OpenLimits Max plus Claude Pro plus ChatGPT Free billing intent.
- [x] 8.3 After explicit approval, apply the stack to the real homes, verify post-write checks, and rerun apply to prove a no-op without changing subscription state.
- [x] 8.4 Run and attribute the bounded live canaries in order: ordinary Claude, `claude-openlimits`, Codex CLI, Codex App, and Claude's Codex plugin; leave any ambiguous surface unresolved.
- [x] 8.5 Exercise one disposable Claude-to-Codex App write handoff, verify single-writer and phase-owner behavior, and record the final redacted validation matrix.
- [x] 8.6 Only after all required evidence passes or the user records explicit waivers, hand off the separate manual decision to retain Claude Pro and OpenLimits Max and use ChatGPT Free.

## 9. RepoPrompt CE Composition Correction

- [x] 9.1 Update the provider-boundary artifacts to distinguish legacy `claude-rp`, native RepoPrompt CE `claude-rpce`, and the composed OpenLimits `claude-openlimits-rpce` lane.
- [x] 9.2 Add the packaged composed launcher, transactional install/rollback support, canonical-policy mapping, and TDD coverage without modifying RepoPrompt CE's generated wrapper.
- [x] 9.3 Regenerate isolated evidence, apply the new launcher to the real launcher directory, run its bounded live canary, and document the final workflow and attribution state.
