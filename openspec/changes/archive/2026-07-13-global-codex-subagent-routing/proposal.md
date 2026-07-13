## Why

The current project orchestrates Anthropic API calls but cannot configure or route native Codex subagents across repositories. Codex now supports global custom-agent profiles and delegation guidance, so this project can provide a tracked, repeatable way to install that routing without replacing Codex's own orchestration runtime.

## What Changes

- Add a version-controlled global Codex routing bundle with focused explorer, planner, implementer, and reviewer agent profiles.
- Add explicit routing policy that delegates only bounded, independent work, prevents overlapping parallel edits, and keeps synthesis in the root thread.
- Add a safe CLI installation workflow with dry-run output, backups, idempotent updates, and validation for the user's Codex home.
- Repair the missing model-routing document while allowing custom agents to inherit the active parent model by default.
- Document installation, verification, rollback, and the distinction between native Codex routing and the existing Anthropic-backed manifest engine.
- Preserve the behavior of the existing `run` and `batch` commands.

## Capabilities

### New Capabilities

- `codex-subagent-routing`: Defines the global native Codex agent roles, delegation criteria, concurrency boundaries, permissions, and result-synthesis behavior.
- `codex-global-installation`: Defines safe, repeatable installation and validation of the routing bundle under the user's Codex home.

### Modified Capabilities

None.

## Impact

- Affected repository areas: CLI command registration, a new global-installation module, packaged Codex templates, tests, dependency metadata, and user documentation.
- Affected user configuration: `~/.codex/config.toml`, `~/.codex/AGENTS.md`, `~/.codex/model-routing.md`, and `~/.codex/agents/cse_*.toml`.
- The installer writes outside the repository only after an explicit apply action and must preserve unrelated existing global configuration.
- No existing application API or manifest format changes are required.
