# Codex Global Installation Specification

## Purpose

Define safe, reversible installation of the native Codex routing bundle while preserving unrelated user configuration and existing CLI behavior.

## Requirements

### Requirement: Preview before global writes
The installer SHALL run in preview mode unless the user supplies an explicit apply flag, and preview mode MUST NOT modify the target Codex home.

#### Scenario: Installer runs without apply
- **WHEN** the user runs `cse install-codex`
- **THEN** it reports the files and managed settings that would change without writing them

#### Scenario: Installer runs with apply
- **WHEN** the user runs `cse install-codex --apply`
- **THEN** it performs only the previously described managed changes after validating the rendered bundle

### Requirement: Configurable Codex home
The installer SHALL resolve the target in the order `--codex-home`, `CODEX_HOME`, then `~/.codex`.

#### Scenario: Explicit target is supplied
- **WHEN** `--codex-home` is present
- **THEN** all preview, backup, validation, and write operations use that directory regardless of environment defaults

#### Scenario: No override is supplied
- **WHEN** neither the option nor `CODEX_HOME` is set
- **THEN** the installer targets the current user's `~/.codex` directory

### Requirement: Preserve unrelated configuration
The installer MUST preserve unrelated keys, comments, rules, prompts, skills, and prose already present in the target Codex home.

#### Scenario: Config contains unrelated tables and comments
- **WHEN** the installer updates the `[agents]` settings
- **THEN** unrelated TOML content and comments remain unchanged

#### Scenario: Global AGENTS contains user guidance
- **WHEN** the installer adds or refreshes routing guidance
- **THEN** it replaces only the content between its managed markers and preserves all other guidance byte-for-byte

### Requirement: Back up and write atomically
Before changing any existing destination, the installer SHALL create a timestamped backup containing every file that will be modified, then SHALL replace destinations atomically.

#### Scenario: Existing global files will change
- **WHEN** apply mode detects one or more modified destinations
- **THEN** it creates a backup and reports its path before replacing any destination

#### Scenario: A write fails
- **WHEN** rendering, validation, temporary-file creation, or replacement fails
- **THEN** the installer returns a failure and does not report a successful installation

### Requirement: Idempotent managed updates
Applying the same routing bundle repeatedly SHALL produce no additional content changes after the first successful installation.

#### Scenario: Bundle is already current
- **WHEN** the user runs preview or apply against an up-to-date Codex home
- **THEN** the installer reports no managed changes and creates no unnecessary backup

### Requirement: Validate the complete bundle
The installer SHALL validate generated TOML syntax, required custom-agent fields, managed concurrency values, the routing marker pair, and the presence of the model-routing document before reporting success.

#### Scenario: Agent template is invalid
- **WHEN** a rendered agent file is missing a required field or contains invalid TOML
- **THEN** installation stops before global files are modified and identifies the invalid template

#### Scenario: Applied bundle is valid
- **WHEN** all managed files are written successfully
- **THEN** a post-write validation pass reads the target files and confirms the installed state matches the rendered bundle

### Requirement: Existing CLI behavior remains compatible
Adding global Codex installation SHALL NOT change the parsing or execution behavior of the existing `cse run` and `cse batch` commands.

#### Scenario: Existing command tests run after installation support is added
- **WHEN** the test suite executes manifest and batch command coverage
- **THEN** existing behavior remains unchanged and all compatibility tests pass
