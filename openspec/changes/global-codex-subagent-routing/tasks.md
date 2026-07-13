## Task 1: Baseline and Packaging

- [x] 1.1 Restore jCodemunch access or document the approved source-based caller map for `src.cli:main`, then capture baseline `run`, `batch`, manifest, and batch test behavior.
- [x] 1.2 Add `tomlkit` as a runtime dependency plus `ruff` as a development dependency, configure linting, and configure Hatch to package the Codex template resources.
- [x] 1.3 Add a resource-loading layer for the routing templates and tests that fail clearly when a packaged template is missing.

## Task 2: Native Codex Routing Bundle

- [ ] 2.1 Add schema-valid templates for `cse_explorer`, `cse_planner`, `cse_implementer`, and `cse_reviewer` with the specified permission boundaries and parent-model inheritance.
- [ ] 2.2 Add the managed global AGENTS routing block with deterministic role selection, phase-gate ownership, non-delegation criteria, result synthesis, and parallel write isolation.
- [ ] 2.3 Add the canonical lowercase `model-routing.md` template from the supplied phase table without pinning unverified model identifiers in agent TOML.
- [ ] 2.4 Add the managed `[agents]` defaults for four threads, depth one, 1800-second CSV worker runtime, and visible interruption messages.

## Task 3: Safe Global Installer

- [ ] 3.1 Implement Codex-home resolution using `--codex-home`, then `CODEX_HOME`, then `~/.codex`, and build a deterministic installation plan without writing.
- [ ] 3.2 Implement comment-preserving `[agents]` TOML updates that modify only managed keys and preserve unrelated configuration.
- [ ] 3.3 Implement managed-block updates for `AGENTS.md` and non-destructive creation or explicit-force replacement for `model-routing.md`.
- [ ] 3.4 Implement template validation for TOML syntax, required agent fields, permissions, concurrency values, routing markers, and model-routing presence.
- [ ] 3.5 Implement timestamped backups, same-directory atomic replacement, no-op detection, and post-write validation.
- [ ] 3.6 Add `cse install-codex` with preview-only default behavior, explicit `--apply`, `--codex-home`, and force semantics plus actionable exit codes and redacted output.

## Task 4: Automated Validation

- [ ] 4.1 Test all four agent profiles for required schema, distinct non-built-in names, sandbox defaults, and omitted model pins.
- [ ] 4.2 Test preview mode, Codex-home precedence, invalid templates, and confirmation that preview performs no writes.
- [ ] 4.3 Test preservation of TOML comments and unrelated keys, preservation of global AGENTS prose, managed-block replacement, and model-routing force behavior.
- [ ] 4.4 Test backup contents, atomic-write failure handling, post-write validation, and idempotent second application.
- [ ] 4.5 Add CLI tests for `install-codex` and rerun existing `run`, `batch`, manifest, and batch tests to prove compatibility.

## Task 5: Documentation and Release Checks

- [ ] 5.1 Update the README with architecture boundaries, preview/apply commands, managed files, restart requirements, validation, and manual rollback from the reported backup.
- [ ] 5.2 Run the full test suite and Ruff checks, recording passing evidence and resolving any regressions before global installation.
- [ ] 5.3 Run preview and apply against a temporary `CODEX_HOME`, compare the complete before/after file set, and verify a second apply is a no-op.
- [ ] 5.4 Run `openspec validate global-codex-subagent-routing` and resolve every schema or scenario error.
- [ ] 5.5 After separate approval for external writes, preview the real `~/.codex` change, apply it, restart Codex, and validate one read-only delegated canary through the native agent UI.
