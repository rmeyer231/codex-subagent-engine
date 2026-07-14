# OpenLimits dual-harness operator guide

This workflow assumes OpenLimits Max, Claude Pro, and ChatGPT Free. CSE manages
configuration and validation only; it never purchases, cancels, downgrades, or
renews a subscription.

## Surface and billing boundaries

| Surface | Provider | Default or recommended model | Expected billing |
| --- | --- | --- | --- |
| Claude Desktop, Claude Code Desktop, Cowork, ordinary `claude` | Anthropic native | Native subscription selection | Claude Pro |
| RepoPrompt CE `claude-rpce` | Anthropic native + RepoPrompt CE MCP | Native subscription selection | Claude Pro |
| `claude-openlimits` architecture | OpenLimits Messages | `anthropic/fable-5` | OpenLimits Max |
| `claude-openlimits` implementation | OpenLimits Messages | `anthropic/claude-sonnet-5` | OpenLimits Max |
| `claude-openlimits` quick work | OpenLimits Messages | `anthropic/claude-haiku-4.5` | OpenLimits Max |
| `claude-openlimits-rpce` | OpenLimits Messages + RepoPrompt CE MCP | Same advisory Claude models | OpenLimits Max |
| Codex planning/review | OpenLimits Responses | `openai/gpt-5.6-sol` | OpenLimits Max |
| Codex CLI/App/plugin implementation | OpenLimits Responses | `openai/gpt-5.6-terra` | OpenLimits Max |
| Codex routine work | OpenLimits Responses | `openai/gpt-5.6-luna` | OpenLimits Max |
| ChatGPT app | OpenAI interactive product | Free-plan availability | ChatGPT Free |

The model rows are advisory. They never stop work, require a model switch, or
override an explicit user selection. Fable is intentionally reserved for short
architecture and synthesis passes; Terra/Sonnet handle token-heavy editing.

Claude Desktop remains a native Claude Pro surface. Codex CLI and Codex App
share `~/.codex/config.toml`; Claude's official Codex plugin launches `codex
app-server` and normally resolves the same `${CODEX_HOME:-~/.codex}`. A guided
plugin canary must record the effective home rather than assuming it.

RepoPrompt CE generates `/usr/local/bin/claude-rpce`; CSE does not replace it.
Choose the command by desired provider boundary:

```text
claude-rpce                 # RepoPrompt CE + native Claude Pro
claude-openlimits-rpce      # RepoPrompt CE + OpenLimits Max
claude-openlimits           # OpenLimits Max without RepoPrompt CE
```

Do not use the legacy `claude-rp` wrapper for RepoPrompt CE. It points to the
older RepoPrompt application's discovery file and does not select OpenLimits.

On the first interactive launch, Claude Code describes any value delivered in
`ANTHROPIC_API_KEY` as a custom or Anthropic API key even when
`ANTHROPIC_BASE_URL` routes it to OpenLimits. In `/config`, scroll to **Use
custom API key** and enable it. This is the expected choice for both managed
OpenLimits launchers; do not run `/login`, which belongs to the native Claude
Pro lane. Non-interactive `-p` requests use the supplied key automatically.

## How future sessions route models

Model routing supplies defaults and recommendations; it does not detect phase
changes or switch a running session automatically. Future sessions should:

1. Identify the active surface and its provider lane.
2. Load the repository's `AGENTS.md` or `CLAUDE.md`, as applicable.
3. Consult `~/.codex/model-routing.md` or `~/.claude/model-routing.md` for the
   canonical model identifiers.
4. Start with the coding model for ordinary work.
5. Recommend high reasoning for bounded architecture, specification, security,
   risky reconciliation, ambiguous debugging, or hard-review work.
6. Recommend the fast model for standalone summaries, lookups, status, and
   low-risk documentation when switching overhead is worthwhile.
7. Continue on the current model if the user does not request a switch.
8. Reassess routing only when the task phase materially changes.

For this repository, high-reasoning examples include OpenSpec proposals,
installer transaction and rollback design, credential or provider security,
and cross-harness ownership. Coding examples include CLI changes, template
rendering, tests, focused refactors, and normal bug fixes. Fast-model examples
include command lookups, artifact inventories, status summaries, and low-risk
documentation.

A file named `.:model-routing-bootstrap.md` is prompt text, not an instruction
file recognized by Codex or Claude, and has no runtime routing effect. A normal
Claude Desktop chat and the ChatGPT Free app also do not automatically consume
repository routing guidance; use an explicit handoff for those surfaces.

## Credential provisioning

The default Keychain tuple is service `OpenLimits`, account `api-key`. The
installer accepts service/account identifiers but has no raw-token option. Use
the final `-w` with no value so macOS prompts interactively and the token does
not enter shell history:

```bash
/usr/bin/security add-generic-password -a api-key -s OpenLimits -U -w
```

If a token has ever been stored in plaintext Claude settings, rotate it first,
provision the replacement Keychain item, and manually remove the legacy value.
Preview reports only the path. Apply refuses to create backups or write files
while a managed plaintext credential remains.

## Preview, apply, and rollback

Preview resolves every target without executing the credential command:

```bash
cse install-openlimits-stack
```

Review the Claude home, Codex home, launcher directory, backup root, Keychain
identifiers, every create/update/no-op/conflict action, any `apiKeyHelper`, and
every legacy-credential path. The managed launcher targets are
`claude-openlimits` and `claude-openlimits-rpce`. An existing unrelated launcher or uncertain
`apiKeyHelper` requires explicit resolution:

```bash
cse install-openlimits-stack --resolve-conflicts
```

After the token is rotated, the Keychain item exists, plaintext is removed, and
the preview is acceptable:

```bash
cse install-openlimits-stack --apply --resolve-conflicts
cse install-openlimits-stack --apply --resolve-conflicts  # must be a no-op
```

Apply rechecks previewed state, backs up all existing non-secret targets, writes
atomically, validates the entire bundle, and automatically restores earlier
mutations if a later boundary fails. It prints a transaction identifier. To
restore that applied transaction:

```bash
cse install-openlimits-stack \
  --backup-root ~/.codex/backups/openlimits-stack \
  --rollback txn-YYYYMMDDTHHMMSS.ffffffZ
```

Rollback restores file contents, absence, and modes. It does not read or modify
Keychain content and does not change subscription state.

## Validation workflow

Run deterministic validation first:

```bash
cse validate-openlimits-stack
cse validate-openlimits-stack --inject-failure
```

This creates temporary Claude/Codex homes, fake credential and harness commands,
and a temporary launcher. It proves merge preservation, exact model routing,
argument forwarding, credential redaction, idempotence, explicit rollback, and
injected-failure rollback without network access or real-home mutation.

Live CLI requests are an explicit, potentially billed step:

```bash
cse validate-openlimits-stack --live
```

Before each request the command prints the surface, provider, model, executable
path, bounded prompt, and expected billing destination. A successful model
response is not billing proof. Record a non-secret OpenLimits dashboard
timestamp or request identifier with `--provider-evidence SURFACE=SOURCE`.
Without it, the surface remains `unresolved`.

The live plan includes a separate `openlimits-claude-rpce` request. It proves
that the composed command reaches Claude through RepoPrompt CE, but it still
requires provider-side attribution (or an explicit waiver) for billing proof.

Codex App and Claude's Codex plugin are guided checks because they cross desktop
application boundaries. Use a disposable checkout, record effective
`CODEX_HOME`, declare one sole writer, run only the displayed bounded task, and
record whether evidence is automated or user-observed. A user may record a
specific `--waive SURFACE=REASON`; a waiver remains distinct from a pass.

## Cross-application handoff

A write-capable Claude-to-Codex or Codex-to-Claude handoff contains:

```text
owner: claude | codex
worktree: /absolute/disposable/or/approved/worktree
branch: feature branch
objective: bounded outcome
allowed_files: exact file list
artifacts: relevant OpenSpec paths
phase: PLAN | SPEC | IMPLEMENT | VALIDATE
validation: exact commands/evidence required
```

Exactly one root harness owns OpenSpec gates and the final completion claim.
Exactly one harness writes a checkout. Plugin-origin Codex work is already
delegated and does not create a second CSE layer unless the handoff explicitly
authorizes independent, non-overlapping work.

Routine cross-harness review is limited to one planning review, one final
review, and one correction/re-review cycle. More cycles require user direction.

## Failure recovery

- Preview conflict: review the named managed path; use `--resolve-conflicts`
  only when replacement is intended.
- Plaintext credential: rotate, provision the replacement Keychain item, remove
  the reported field manually, and rerun preview.
- Missing Keychain item: use the interactive provisioning command above; CSE
  never accepts or copies the raw token.
- Apply failure with successful automatic rollback: retain the transaction for
  evidence, fix the cause, and generate a fresh preview.
- Automatic rollback failure: stop both harnesses, preserve the transaction
  directory, and restore only the manifest-listed targets from its backups.
- Provider outage: fail visibly. Use ChatGPT Free only as a separate manual
  session with an explicit handoff; never infer silent provider fallback.
