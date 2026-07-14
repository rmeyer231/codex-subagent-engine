## Context

The selected operating stack is OpenLimits Max plus Claude Pro plus ChatGPT Free. The desired experience spans Claude Desktop, the ordinary Claude Code CLI, explicit OpenLimits-backed Claude launchers, RepoPrompt CE's generated Claude wrapper, Codex CLI, Codex App, and Claude's official Codex plugin. These surfaces currently lack a single provider boundary and handoff policy.

The machine's existing Codex routing documents name advisory aliases that do not match the current OpenLimits catalog. The verified catalog uses `anthropic/fable-5`, `anthropic/claude-sonnet-5`, and `anthropic/claude-haiku-4.5` for the Claude-compatible lane, and `openai/gpt-5.6-sol`, `openai/gpt-5.6-terra`, and `openai/gpt-5.6-luna` for the Responses-compatible Codex lane. The effective Codex runtime is nevertheless still using the built-in `openai` provider with `gpt-5.6-sol`; an OpenLimits provider/profile exists but is not the effective default. Claude's global settings contain OpenLimits gateway overrides and a credential value, which makes native-versus-gateway billing hard to reason about and leaves a reusable token in plaintext.

Codex 0.144.3 and the current Codex manual establish two useful constraints. First, Codex CLI, IDE, and desktop surfaces share user configuration layers. Second, custom providers support command-backed bearer authentication through `[model_providers.<id>.auth]`. That permits one user-level OpenLimits provider to serve Codex CLI, Codex App, and plugin-launched Codex without persisting the token. Claude needs a different boundary because its ordinary desktop and CLI surfaces must stay on native Claude Pro.

The repository already has a preview-first `cse install-codex` implementation with deterministic rendering, managed markers, target-state conflict checks, backups, atomic writes, and post-write validation. The new workflow should reuse its pure planning output without changing the existing command contract.

## Goals / Non-Goals

**Goals:**

- Make the active provider and expected billing destination unambiguous for every Claude, Codex, plugin, and desktop surface.
- Keep Claude Desktop and ordinary `claude` on native Claude Pro while offering an explicit `claude-openlimits` lane.
- Keep RepoPrompt CE's `claude-rpce` wrapper native while offering `claude-openlimits-rpce` as the explicit composed OpenLimits + RepoPrompt CE lane.
- Make OpenLimits the managed provider for Codex CLI, Codex App, and plugin-launched Codex, with Terra as the default and advisory Sol/Luna phase routing.
- Retrieve the OpenLimits token from macOS Keychain only at process startup and keep it out of configuration, repository files, command lines, logs, diffs, backups, and reports.
- Provide preview, apply, rollback, idempotence, and isolated/live canary workflows across both homes and the launcher.
- Preserve unrelated global configuration and the existing `cse install-codex`, `cse run`, and `cse batch` behavior.
- Define a single phase owner, a sole writer for shared checkouts, explicit handoff metadata, and bounded cross-harness review.

**Non-Goals:**

- Purchasing, cancelling, downgrading, or renewing any subscription.
- Automatically importing, rotating, or deleting a plaintext OpenLimits credential.
- Making ChatGPT Free act like API capacity or a transparent provider fallback.
- Replacing Claude Desktop's native authentication or routing its ordinary sessions through OpenLimits.
- Replacing or modifying RepoPrompt CE's generated `claude-rpce` wrapper.
- Automatically driving desktop UI canaries; those remain guided, user-observed checks whose evidence is recorded by the validator.
- Changing the behavior of existing CSE commands or refactoring the current Codex installer beyond small reusable interfaces required by the composite planner.
- Proving that every advertised OpenLimits alias is available before a live provider catalog and request canary run.

## Decisions

### 1. Use explicit provider lanes instead of process-wide gateway overrides

The ordinary Claude command, Claude Desktop, and direct `claude-rpce` executions will have no managed OpenLimits `ANTHROPIC_*` overrides, so they use native Claude Pro. `claude-openlimits` will set the OpenLimits endpoint and token only for direct Claude, while `claude-openlimits-rpce` will set the same process-scoped values and then invoke the external `claude-rpce` wrapper. Codex's user-level configuration will select `model_provider = "openlimits"`, which applies consistently to Codex CLI, Codex App, and plugin-launched Codex because those surfaces share the same configuration layer.

ChatGPT Free remains a separate interactive fallback. It is not an automatic fallback from an OpenLimits failure because that would silently change capabilities and billing. If the user uses it, the result returns through an explicit read-only or write-ownership handoff.

Alternatives considered:

- Global Claude environment overrides were rejected because they also affect the ordinary CLI and can affect desktop-launched sessions, defeating the native-Pro boundary.
- Separate Codex homes for CLI and App were rejected as the default because they split sessions, plugins, skills, and instructions and make provider drift more likely. Alternate homes remain available for isolated tests.
- Silent fallback between OpenLimits and native providers was rejected because a successful answer would no longer prove its billing destination.

### 2. Use a Keychain-backed credential command for both OpenLimits lanes

The default credential reference will use the configurable macOS Keychain tuple service `OpenLimits` and account `api-key`, with no secret accepted as a CLI option. Codex will use its supported nested provider auth block to execute `/usr/bin/security find-generic-password ... -w`; the command's stdout goes directly to Codex's bearer-token loader. `claude-openlimits` will execute the same lookup, export the required OpenLimits variables only to the child process, and then `exec` the real Claude binary with the original arguments.

The installer will validate that the Keychain item is addressable but will not create it from a supplied token. Tests will inject a fake credential command into temporary homes. Preview and error reporting will display only the service/account identifiers and command path, never command output.

Claude Code requires a one-time interactive approval before it uses an
`ANTHROPIC_API_KEY`; its UI names the variable rather than the gateway. The
operator guide will direct OpenLimits launcher users to enable **Use custom API
key** in `/config`. Declining it is remembered and makes interactive requests
fall through to native login, while non-interactive `-p` requests continue to
use the supplied OpenLimits credential.

A legacy plaintext OpenLimits credential is a hard preflight conflict. Apply stops before backups or writes until the user has rotated the exposed token, added the replacement to Keychain, and removed the legacy value. This preserves exact rollback and ensures backups cannot retain the retired secret.

Alternatives considered:

- `env_key` was rejected for the desktop default because GUI-launched Codex processes do not reliably inherit shell-only variables.
- A static bearer token in `config.toml` was rejected because it repeats the current exposure.
- Automatically copying the detected token into Keychain was rejected because it would reuse a possibly exposed credential and make a security-sensitive external mutation without a distinct user action.

### 3. Add a composite planner and transaction without changing `install-codex`

Add `cse install-openlimits-stack` backed by a new `src/dual_harness_global.py` module. The command will default to preview and accept explicit Claude home, Codex home, and launcher-directory targets so tests never touch real global state. Its plan will contain absolute destinations internally but expose only redacted, home-relative summaries.

The composite planner will call `codex_global.plan_install()` to obtain the existing Codex bundle's validated rendered and observed state, then layer the OpenLimits provider, command-backed auth, default model, and dual-harness routing additions onto the rendered Codex configuration. It will independently render Claude settings, `CLAUDE.md`, Claude model routing, and both launchers. Small public helpers may be extracted from `codex_global.py`, but `cse install-codex` will continue through its existing plan/apply path and tests.

Apply will recheck every observed target, create one transaction manifest and timestamped backup set, perform atomic writes, and post-validate every destination. If a later write or validation step fails, the composite transaction restores every target changed by that invocation. The printed transaction identifier will also support an explicit rollback operation. Keychain content and subscription state are outside the transaction.

Alternatives considered:

- Calling the existing `apply_plan()` and then editing Claude files was rejected because it cannot provide cross-home rollback.
- Replacing `install-codex` with the composite installer was rejected because it would change established behavior for users who only want the native CSE routing bundle.
- Shell-only installation was rejected because structured TOML/JSON merges, conflict detection, and deterministic tests are safer in the existing Python package.

### 4. Represent phase routing once and validate both harness renderings

Add a small declarative routing policy resource under `src/templates/dual_harness/` containing normalized phases, default selection, provider boundaries, review limits, and handoff fields. The stack renderer will use it for new Claude guidance and the cross-harness managed blocks. The existing Codex model-routing document remains a supported standalone-install asset, but package validation will assert that its phase rows match the declarative policy.

The provider contract uses `https://openlimits.app` for Claude-compatible Messages requests and `https://openlimits.app/v1` for Codex Responses requests. Both Claude launchers set `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, and the three `ANTHROPIC_DEFAULT_*_MODEL` variables only in their child process, matching the current OpenLimits Claude Code setup contract; they explicitly unset `ANTHROPIC_AUTH_TOKEN` so a stale inherited override cannot win. Claude identifiers use `anthropic/fable-5`, `anthropic/claude-sonnet-5`, and `anthropic/claude-haiku-4.5`. Codex identifiers use `openai/gpt-5.6-sol`, `openai/gpt-5.6-terra`, and `openai/gpt-5.6-luna`, with Terra selected as the default. Codex command-backed authentication serializes the executable as `auth.command` and its remaining arguments as `auth.args`, matching the installed Codex configuration schema. Guidance remains advisory: it can recommend a phase model but cannot pause work, require `/model`, or override an explicit user choice.

Alternatives considered:

- Two independently maintained Markdown tables were rejected because they can drift without detection.
- Pinning every CSE subagent model was rejected because the existing inheritance policy is safer until role-specific identifiers are independently verified.

### 5. Make cross-harness ownership an explicit protocol

The root harness recorded in the handoff owns OpenSpec phase gates, user communication, result synthesis, and the completion claim. A handoff capable of writes records the owner, worktree and branch, objective, allowed files, relevant artifacts, current phase, and required validation. The receiver remains read-only if any ownership field is missing.

Claude plugin jobs count as the first delegation boundary. A routine plugin-launched Codex job executes directly in its receiving root instead of spawning another CSE implementer. Native Codex delegation remains available only when the handoff explicitly identifies independent bounded subwork and current depth/write-isolation rules permit it.

Routine review is capped at one planning review and one final review, with one correction/re-review cycle after accepted final findings. More cycles require user direction. Concurrent writers must use separate worktrees with disjoint file sets.

Alternatives considered:

- Allowing both desktop apps to edit the same checkout was rejected because application-level session awareness does not provide file ownership isolation.
- Always delegating plugin work into CSE was rejected because it adds a redundant context and orchestration layer to work that Claude already delegated.

### 6. Separate deterministic validation from live provider proof

Add `cse validate-openlimits-stack`. Its default mode uses temporary homes, a temporary launcher directory, fake executables, and a fake credential command. It verifies merge preservation, routing output, argument forwarding, secret redaction, idempotence, rollback, and the absence of real-home or network access.

`--live` prints the exact surface, provider, model, and expected billing destination before running bounded requests, including separate direct-Claude and RepoPrompt CE OpenLimits rows. CLI canaries may be automated; Codex App and Claude plugin canaries are guided because they cross interactive application boundaries. The validator records a result matrix rather than inferring success from a model response. Effective configuration, Codex diagnostics, request identifiers, and provider dashboard attribution are stronger evidence than asking a model to identify itself.

The readiness result requires the isolated canary plus native Claude, OpenLimits Claude, Codex CLI, Codex App, and Claude-plugin evidence, unless the user records a specific waiver. Ambiguous provider or billing attribution is unresolved, not passing.

Alternatives considered:

- Running live requests in the test suite was rejected because it creates cost, nondeterminism, and secret-handling risk.
- Trusting model self-identification was rejected because gateways can map aliases and models can report stale or incorrect names.

### 7. Keep billing actions outside the tool

The installer and validator will report the intended OpenLimits Max plus Claude Pro plus ChatGPT Free stack, but they will not call billing APIs or automate cancellation. After every required canary passes, the user may keep Claude Pro, activate or retain OpenLimits Max, and move any paid ChatGPT subscription to Free manually. Until then, no subscription change is implied.

## Risks / Trade-offs

- [OpenLimits model identifiers or endpoint behavior change after implementation] -> Recheck the provider catalog and run one bounded request per selected model before marking live validation complete; keep the exact identifiers configurable in the declarative policy.
- [Keychain lookup prompts or fails when Codex App is launched from the GUI] -> Test the real app surface before apply-ready status; document Keychain access settings and leave the old configuration recoverable through the transaction backup.
- [Claude's Codex plugin launches with a different `CODEX_HOME`] -> Record the effective home in the plugin canary and treat a mismatch as a blocking validation result rather than copying configuration into another location automatically.
- [RepoPrompt CE regenerates or removes `claude-rpce`] -> Keep that wrapper outside CSE ownership, invoke it by command name, and report a visible executable failure rather than falling back to direct Claude.
- [Claude Code labels the OpenLimits credential as an Anthropic/custom API key] -> Document the one-time `/config` approval, preserve the explicit OpenLimits base URL boundary, and treat `Not logged in` after rejection as a local approval-state failure rather than a Keychain failure.
- [A cross-home apply fails halfway] -> Snapshot all target state first, use atomic writes, restore earlier mutations, retain the transaction manifest, and test injected failures at every write boundary.
- [Managed JSON or TOML merging removes comments or user ordering] -> Use `tomlkit` for Codex and a narrow key-level JSON merge for Claude; compare unrelated semantic content in tests and disclose formatting-only changes in preview.
- [Legacy plaintext credentials survive elsewhere in shell profiles, logs, or backups not managed by this installer] -> Scan documented managed paths, report only path-level findings, require token rotation, and clearly state the scan is not a complete secret audit.
- [One shared Codex config makes OpenLimits unavailable when the gateway is down] -> Fail visibly and use an explicit manual ChatGPT Free/native profile or session rather than silent provider fallback.
- [The declarative policy and prose templates drift] -> Validate rendered phase rows, model aliases, managed markers, and required handoff fields as package invariants.
- [Guided desktop canaries depend on user observation] -> Save the exact steps and non-secret evidence source, distinguish user-recorded results from automated results, and never upgrade a waiver to a pass.

## Migration Plan

1. Implement the declarative policy, renderers, and isolated test fixtures without touching global state.
2. Add the composite preview/apply/rollback command and validation command; run unit tests, lint, package-data checks, injected-failure rollback tests, and the isolated canary in a disposable home.
3. Run a real-home preview. Review every target, legacy credential finding, conflict, and expected provider/model change.
4. Manually rotate the exposed OpenLimits token, store the replacement in the documented Keychain service/account, and remove the legacy plaintext field. Re-run preview until credential preflight and conflicts are clean.
5. Apply the stack once. Confirm post-write validation and rerun apply to prove a no-op.
6. Run bounded live canaries in order: ordinary Claude, `claude-openlimits`, `claude-openlimits-rpce`, Codex CLI, Codex App, then Claude's Codex plugin. Confirm the effective provider and dashboard attribution after each request before continuing.
7. Exercise one Claude-to-Codex App handoff in a disposable repository to confirm sole-writer and phase-owner behavior.
8. Only after the validation matrix is complete, make any desired subscription changes manually.

Rollback uses the transaction identifier printed by apply to restore all managed non-secret files and launcher state. It does not delete the replacement Keychain item, restore a retired plaintext credential, or change subscriptions. After rollback, rerun ordinary Claude and Codex diagnostics to confirm their effective providers.

## Open Questions

- Does Claude's installed official Codex plugin inherit the default Codex home in both CLI and desktop-launched Claude sessions? Resolve with the plugin canary before production apply.
- What non-secret request identifier or dashboard timestamp provides the strongest billing attribution for OpenLimits and native Claude in this account? Record the chosen evidence source in validation documentation.
