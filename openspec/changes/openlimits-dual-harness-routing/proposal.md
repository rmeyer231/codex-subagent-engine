## Why

The current global configuration mixes Claude Desktop, Claude Code CLI, Codex, and OpenLimits credentials in ways that make provider billing ambiguous, keep an expensive Codex model as the default, and persist a gateway token in plaintext. The selected OpenLimits Max + Claude Pro + ChatGPT Free stack needs explicit provider boundaries, secure credential delivery, and a reproducible cross-app workflow before subscriptions or live defaults change.

## What Changes

- Define a dual-lane Claude policy: Claude Desktop and the ordinary `claude` command use native Claude Pro, while a dedicated `claude-openlimits` launcher uses OpenLimits with `anthropic/fable-5` for explicit architecture work, `anthropic/claude-sonnet-5` for implementation, and `anthropic/claude-haiku-4.5` for quick work.
- Preserve RepoPrompt CE's generated `claude-rpce` wrapper as a native-Claude lane and add `claude-openlimits-rpce` to compose the same RepoPrompt CE MCP discovery with process-scoped OpenLimits authentication.
- Configure Codex CLI, Codex App, and Codex jobs launched by Claude's official Codex plugin to use OpenLimits, with `openai/gpt-5.6-terra` as the default and advisory phase routing to `openai/gpt-5.6-sol` or `openai/gpt-5.6-luna` when appropriate.
- Add a preview-first, reversible installer for the combined Claude/Codex stack that preserves unrelated user configuration and never embeds credentials in repository or global config files.
- Move the OpenLimits credential to macOS Keychain and retrieve it only at runtime through a command-backed provider or launcher.
- Install one consistent routing policy across Claude and Codex, including OpenSpec phase ownership, bounded review loops, session handoff, and a single-writer rule for shared checkouts.
- Add isolated and live canaries that prove provider selection, desktop/plugin session continuity, redacted output, and expected billing destinations before any subscription downgrade.
- Preserve the existing `cse install-codex`, `cse run`, and `cse batch` behaviors unless the new stack installer is explicitly invoked.
- **BREAKING**: remove global OpenLimits environment overrides from Claude settings so the ordinary `claude` command returns to Claude Pro; OpenLimits Claude usage moves to the explicit `claude-openlimits` launcher.

## Capabilities

### New Capabilities
- `dual-harness-routing`: Defines provider, model, phase, app-surface, review-loop, and handoff rules for Claude Desktop, Claude Code CLI, the Codex plugin, Codex CLI, and Codex App.
- `dual-harness-global-installation`: Defines safe installation, preservation, credential boundaries, launcher creation, backup, rollback, and idempotence for the selected global stack.
- `provider-routing-validation`: Defines isolated and live evidence required to prove Claude, Codex, plugin, desktop-session, and billing routing before applying the production configuration or changing subscriptions.

### Modified Capabilities
- `codex-subagent-routing`: Treats work received through Claude's Codex plugin as already delegated by default, preventing an unnecessary nested CSE layer and enforcing sole-writer ownership when a session moves between Claude and Codex App.

## Impact

- Repository code and templates: `src/codex_global.py`, a new Claude/global-stack installer module, `src/cli.py`, packaged Claude/Codex routing templates, launcher assets, tests, package data, and README guidance.
- Existing specifications: `codex-subagent-routing` receives a delta requirement; existing `codex-global-installation` and Pooler preservation behavior remain compatible.
- Global destinations: `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, `~/.claude/model-routing.md`, `~/.local/bin/claude-openlimits`, `~/.local/bin/claude-openlimits-rpce`, `~/.codex/config.toml`, `~/.codex/AGENTS.md`, and `~/.codex/model-routing.md`.
- External state: one macOS Keychain credential and provider/billing dashboards used only for approved live validation. Subscription changes remain manual and occur only after validation evidence passes.
