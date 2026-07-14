# Dual-Harness Global Installation Specification

## Purpose

Define safe, reversible installation of the selected OpenLimits, Claude Pro,
and ChatGPT Free operating stack across global Claude and Codex configuration.

## Requirements

### Requirement: Explicit preview-first stack installer
The CLI SHALL expose a dedicated dual-harness stack installer that previews resolved targets and planned actions by default and mutates global state only when the user explicitly selects apply mode. The command SHALL report the Claude home, Codex home, launcher destination, managed files, backups, credential preconditions, and validation steps before applying.

#### Scenario: User runs the installer without apply mode
- **WHEN** the user invokes the stack installer without the explicit apply option
- **THEN** it reports the full plan and leaves all files, credentials, and subscriptions unchanged

#### Scenario: User supplies alternate homes
- **WHEN** the user provides alternate Claude home, Codex home, or launcher directory values
- **THEN** preview and apply resolve every target from those values instead of assuming the real user home

### Requirement: Managed merge preserves unrelated configuration
The installer SHALL own only documented OpenLimits provider keys, phase-routing blocks, launcher assets, and OpenLimits overrides that it is explicitly migrating. It MUST preserve unrelated Claude settings, plugins, MCP servers, hooks, Codex providers, profiles, project trust entries, agent definitions, and user-authored prose.

#### Scenario: Claude settings contain non-secret OpenLimits global overrides
- **WHEN** apply mode processes managed `ANTHROPIC_BASE_URL` or gateway-discovery overrides after any plaintext credential has been removed
- **THEN** it removes those managed global overrides so the ordinary Claude surfaces return to native authentication while preserving unrelated settings

#### Scenario: Codex configuration contains unrelated providers and profiles
- **WHEN** apply mode configures the OpenLimits provider and default model in Codex
- **THEN** it preserves all unrelated provider tables, profiles, MCP configuration, and project trust entries

#### Scenario: An existing managed block is present
- **WHEN** a routing document already contains the installer's managed markers
- **THEN** apply mode replaces only the marked block and preserves prose before and after it

### Requirement: Runtime-only OpenLimits credential retrieval
The installer SHALL configure macOS Keychain as the default OpenLimits credential store and SHALL retrieve the credential only at process startup through a command-backed Codex provider or the `claude-openlimits` launcher. It MUST NOT accept the raw token as a command-line argument, copy an existing plaintext token into the Keychain, persist the token in generated files, or print it in preview, errors, diffs, logs, or validation evidence.

#### Scenario: Keychain entry is available
- **WHEN** apply mode validates the configured OpenLimits Keychain service and account
- **THEN** it writes credential-free provider and launcher configuration that retrieves the secret at runtime

#### Scenario: Keychain entry is missing
- **WHEN** apply mode cannot retrieve the required Keychain entry
- **THEN** it stops before mutating files and prints a redacted manual provisioning command that does not contain the secret

#### Scenario: Legacy plaintext credential is detected
- **WHEN** preview detects an OpenLimits credential in a managed global configuration field
- **THEN** it reports the affected path without displaying the value and apply mode refuses to mutate any target until the user rotates the credential, provisions the replacement Keychain entry, and removes the legacy field

#### Scenario: Generated artifacts are inspected
- **WHEN** tests scan configuration, backups, launcher files, output, and logs
- **THEN** no OpenLimits credential value is present

### Requirement: Explicit OpenLimits Claude launchers
The installer SHALL create `claude-openlimits` and `claude-openlimits-rpce` executables in the resolved launcher directory. Both launchers MUST retrieve the OpenLimits token from the configured Keychain entry, set OpenLimits variables only for their child process, preserve user arguments and exit status, and leave the ordinary `claude` command unchanged. The RepoPrompt CE launcher MUST invoke the externally generated `claude-rpce` wrapper so RepoPrompt CE remains responsible for its MCP discovery environment.

#### Scenario: Launcher starts successfully
- **WHEN** the user runs `claude-openlimits` with Claude arguments
- **THEN** the launcher passes the arguments to Claude with process-scoped OpenLimits endpoint and credential variables

#### Scenario: Launcher cannot retrieve the credential
- **WHEN** Keychain lookup fails at launcher runtime
- **THEN** the launcher exits nonzero with a redacted remediation message and does not start Claude

#### Scenario: User combines OpenLimits with RepoPrompt CE
- **WHEN** the user runs `claude-openlimits-rpce` with Claude arguments
- **THEN** the launcher supplies process-scoped OpenLimits variables to `claude-rpce`, which supplies RepoPrompt CE discovery variables before starting Claude

#### Scenario: RepoPrompt CE regenerates its wrapper
- **WHEN** RepoPrompt CE updates `/usr/local/bin/claude-rpce`
- **THEN** the managed composed launcher continues to invoke that external wrapper without overwriting or copying it

### Requirement: Reversible cross-home installation
Before its first mutation, apply mode SHALL create timestamped backups of every existing target file. Writes SHALL be atomic per file, and a failure after mutation begins MUST restore every target changed by that invocation or report an explicit rollback failure with the untouched backups retained.

#### Scenario: All writes succeed
- **WHEN** apply mode updates both homes and the launcher successfully
- **THEN** it reports every backup and installed path and leaves no temporary files behind

#### Scenario: A later write fails
- **WHEN** a write fails after one or more earlier targets were changed
- **THEN** the installer restores the earlier targets from that invocation and returns a nonzero status

### Requirement: Idempotent convergent installation
Repeated apply operations with unchanged inputs SHALL converge to byte-identical managed content, SHALL NOT duplicate routing blocks, and SHALL report unchanged targets without rewriting them or creating unnecessary backups.

#### Scenario: Installer is applied twice
- **WHEN** the second apply uses the same targets and configuration as the first
- **THEN** it reports all managed targets as unchanged and produces no duplicate blocks or additional backups

### Requirement: Existing CSE workflows remain compatible
The new stack installer SHALL be opt-in and MUST NOT change the behavior of `cse install-codex`, `cse run`, or `cse batch` unless the user invokes the new command. It SHALL reuse existing Codex installation behavior where compatible rather than changing the existing command contract.

#### Scenario: User runs an existing CSE command
- **WHEN** the user invokes `cse install-codex`, `cse run`, or `cse batch` after the new feature is installed
- **THEN** the command retains its existing options, target resolution, and behavior

### Requirement: Installer does not manage subscriptions
The stack installer MUST NOT purchase, cancel, downgrade, or renew OpenLimits, Anthropic, or OpenAI subscriptions. It SHALL present OpenLimits Max plus Claude Pro plus ChatGPT Free as the selected operating assumption and leave every billing change to an explicit manual user action after validation.

#### Scenario: Installation and canaries pass
- **WHEN** all managed configuration and provider canaries succeed
- **THEN** the installer reports readiness for the user to make any desired manual subscription change without changing billing state itself
