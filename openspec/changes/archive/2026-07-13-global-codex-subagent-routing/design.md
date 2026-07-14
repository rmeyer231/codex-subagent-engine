## Context

Codex supports personal custom agents under `~/.codex/agents/`, global subagent limits under `[agents]` in `~/.codex/config.toml`, and durable delegation guidance in `~/.codex/AGENTS.md`. Codex auto-discovers global instructions from `~/.codex/AGENTS.override.md` if it is non-empty, otherwise from `~/.codex/AGENTS.md`; `AGENTS.routing.md` is the CSE packaged source filename and is never an installed auto-discovery destination. The current project instead calls Anthropic's synchronous Messages API and does not create native Codex threads, inherit Codex tools, or participate in Codex approval and sandbox handling.

The user's existing global guidance contains model and phase rules that must remain authoritative, but it references a missing `~/.Codex/model-routing.md`. Global configuration is outside Git, so the repository must hold the canonical templates and a controlled installer must deploy them.

## Goals / Non-Goals

**Goals:**

- Configure native Codex subagent routing consistently across repositories.
- Provide focused explorer, planner, implementer, and reviewer roles without overriding Codex built-ins.
- Preserve existing global configuration and require explicit approval before external writes.
- Make installation testable, idempotent, reversible, and safe to preview.
- Keep current `cse run` and `cse batch` behavior unchanged.

**Non-Goals:**

- Reimplement Codex's thread orchestration, approvals, sandbox, or `/agent` UI.
- Repair the existing Anthropic engine's concurrency, timeout, sandbox, or approval defects in this change.
- Permit recursive delegation or concurrent edits to overlapping files.
- Hard-code a model identifier that has not been verified in the active Codex environment.

## Decisions

### Use native Codex custom agents

The bundle will define `cse_explorer`, `cse_planner`, `cse_implementer`, and `cse_reviewer` as standalone TOML files. Distinct names avoid unexpectedly replacing Codex's built-in `explorer` or `worker` agents. Explorer, planner, and reviewer default to read-only; the implementer may use workspace-write. Live parent permission overrides remain authoritative.

Alternative considered: extend `run_subagent()` to call Codex. Rejected because that would duplicate Codex orchestration and would not integrate cleanly with native threads, tools, approvals, or UI.

### Put routing policy in a managed global AGENTS block

The installer will add a clearly delimited managed block to `~/.codex/AGENTS.md`. It will map discovery to the explorer, PLAN/SPEC work to the planner, approved changes to the implementer, and independent verification to the reviewer. It will require the root thread to own phase gates, resolve task boundaries, wait for results, and synthesize the final answer. It will prohibit delegation for trivial work, strictly sequential work, or overlapping writes.

Alternative considered: rely only on agent descriptions. Rejected because current Codex behavior delegates predictably when direct or applicable instruction guidance requests delegation; descriptions alone do not fully encode workflow boundaries.

### Keep model routing separate from role routing

Agent files will omit `model` initially and inherit the parent model. A tracked `model-routing.md` template will reproduce the user's supplied phase table, and the managed AGENTS block will reference the canonical lowercase `~/.codex/model-routing.md` path. Existing user-owned model routing content will not be overwritten without an explicit force option.

Alternative considered: pin each role to the supplied OpenLimits aliases. Rejected until those aliases are verified as valid native Codex configuration values.

### Provide an additive installer command

Add `cse install-codex`, implemented in a new module, with preview-only behavior by default and an explicit `--apply` flag. It will resolve `--codex-home`, then `CODEX_HOME`, then `~/.codex`; this makes tests isolated and supports non-default installations.

Canonical templates will be packaged with the project. The installer will:

1. render the intended file set;
2. validate all generated TOML and required fields;
3. show a redacted change plan;
4. back up every existing destination that will change;
5. update only managed configuration keys and blocks; and
6. write atomically with same-directory temporary files and rename.

`tomlkit` will be used to preserve comments and unrelated content in `config.toml`. Markdown routing guidance will use stable start/end markers so reruns replace only the managed block.

Alternative considered: direct shell copies into `~/.codex`. Rejected because they are not safely mergeable, testable, or reversible.

### Configure conservative global limits

The installer will manage `agents.max_threads = 4`, `agents.max_depth = 1`, `agents.job_max_runtime_seconds = 1800`, and `agents.interrupt_message = true`. Depth one prevents recursive fan-out. The routing policy will also cap requested parallel agents to the number of independent work units and forbid multiple owners for the same file set.

## Risks / Trade-offs

- **Global routing increases token and latency costs** → Delegate only independent, non-trivial work and cap concurrency at four.
- **Existing global files may contain unrelated user configuration** → Use comment-preserving TOML updates, managed Markdown markers, backups, and atomic writes.
- **Parent runtime overrides can supersede custom-agent sandbox defaults** → Document this explicitly and validate behavior with a canary session.
- **Model aliases may differ across Codex distributions** → Inherit the parent model until supported identifiers are verified.
- **Repository-local AGENTS rules can conflict with the global block** → State that closer project guidance wins and root phase gates remain authoritative.
- **OpenSpec-generated Codex prompts are global while skills are repo-local** → Track OpenSpec artifacts and skills in this branch, and document that Codex must restart after prompt refresh.

## Migration Plan

1. Implement and test the installer entirely against temporary `CODEX_HOME` directories.
2. Run `cse install-codex` to review the exact global diff without writing.
3. Run `cse install-codex --apply` only after approval; record the printed backup directory.
4. Restart Codex so custom agents and updated guidance are loaded.
5. Run a canary request that delegates one read-only task, inspect `/agent`, and confirm the root synthesizes the result.
6. If validation fails, restore the timestamped backup and restart Codex.

## Open Questions

- Which native Codex model identifiers, if any, should eventually be pinned per role instead of inheriting the parent model?
- Should the routing bundle later be distributed as a Codex plugin, once the direct global installation has proven stable?
