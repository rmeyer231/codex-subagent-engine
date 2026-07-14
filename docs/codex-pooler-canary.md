# Experimental Codex Pooler Canary

This procedure evaluates whether a specific Codex Pooler release preserves the native CSE subagent workflow. It is experimental: CSE does not install, deploy, authenticate to, or support Codex Pooler automatically.

Do not use this procedure to change the ordinary Codex provider, migrate existing sessions, share an unauthorized account, or offer Pooler as a hosted or managed service.

## Verified documentation baseline

The guide was last checked on 2026-07-13 against:

- CSE base revision `4a1ba32` (`feat/global-codex-routing`)
- Codex CLI `0.144.3`
- Codex Pooler [`codex-pooler-v0.4.26`](https://github.com/icoretech/codex-pooler/releases/tag/codex-pooler-v0.4.26)
- OpenAI's [Codex configuration reference](https://developers.openai.com/codex/config-reference/)
- Pooler's [Codex CLI and Desktop guide](https://docs.codex-pooler.com/clients/codex-cli/)
- Pooler's [routing reference](https://docs.codex-pooler.com/reference/routing-strategies/)
- Pooler's [Elastic License 2.0 at `codex-pooler-v0.4.26`](https://github.com/icoretech/codex-pooler/blob/codex-pooler-v0.4.26/LICENSE.md)

These versions are a canary target, not a general compatibility guarantee. Re-check the current Codex schema, Pooler release notes, backend route, and license before every new evidence run. Record the exact CSE commit rather than assuming the baseline revision is still current.

## Required boundaries

Proceed only when all of these are true:

- The Pooler deployment and every upstream account are authorized for the proposed client and operator use.
- Pooler is deployed and maintained outside CSE, with a versioned image rather than `latest`.
- The test uses a dedicated Pool and Pool API key that can be revoked after the run.
- The test uses a disposable `CODEX_HOME`; it does not copy the ordinary `auth.json`, sessions, or state databases.
- The selected model is actually exposed by the test Pool. Do not change CSE's OpenLimits phase aliases to make the canary work.
- All examples and prompts use non-sensitive repository content and contain no PHI or PII.
- Evidence contains metadata only. Never record prompts, completions, repository contents, raw account identifiers, emails, tokens, cookies, bodies, frames, or transcripts.

If any boundary is unresolved, classify the canary as `BLOCKED` and stop before configuration or credential creation.

## 1. Record the ordinary state

Close every Codex process that uses the ordinary home and keep it closed for the canary. In the shell that will run the canary, record the ordinary Codex home before setting an override, then create a deterministic manifest of the configuration, SQLite state (including sidecars), and active and archived session JSONL files:

```zsh
ordinary_codex_home="${CODEX_HOME:-$HOME/.codex}"
ordinary_manifest_before="$(mktemp)"

snapshot_ordinary_codex_home() (
  cd "$ordinary_codex_home" || exit 1
  {
    if [[ -f config.toml ]]; then
      printf '%s\n' config.toml
    fi
    find . -maxdepth 1 -type f -name 'state_*.sqlite*' -print
    for session_dir in sessions archived_sessions; do
      if [[ -d "$session_dir" ]]; then
        find "$session_dir" -type f -name '*.jsonl' -print
      fi
    done
  } | LC_ALL=C sort | while IFS= read -r file_path; do
    shasum -a 256 "$file_path"
  done
)

snapshot_ordinary_codex_home > "$ordinary_manifest_before"
printf 'ORDINARY_CODEX_HOME=%s\n' "$ordinary_codex_home"
printf 'ORDINARY_MANIFEST_BEFORE=%s\n' "$ordinary_manifest_before"
shasum -a 256 "$ordinary_manifest_before"
```

Keep the manifest locally until rollback. It contains relative paths and SHA-256 hashes, never file contents. In the evidence record, use a redacted label such as `ordinary-before` and the manifest hash; do not publish raw session paths or copy configuration or session contents.

## 2. Create an isolated CSE installation

Create and record a disposable directory, preview the CSE bundle, then apply it explicitly:

```zsh
canary_codex_home="$(mktemp -d)"
printf 'CANARY_CODEX_HOME=%s\n' "$canary_codex_home"
.venv/bin/cse install-codex --codex-home "$canary_codex_home"
.venv/bin/cse install-codex --codex-home "$canary_codex_home" --apply
```

Inspect the preview before applying. The target must equal the recorded disposable path. Stop if it resolves to the ordinary Codex home.

## 3. Add the Pooler provider manually

Edit the disposable `config.toml` only. Insert this block before its existing `[agents]` table and replace the example host with the authorized, version-pinned deployment:

```toml
model_provider = "codex-pooler-ws"

[model_providers.codex-pooler-ws]
name = "OpenAI"
base_url = "https://codex-pooler.example.com/backend-api/codex"
env_key = "CODEX_POOLER_API_KEY"
wire_api = "responses"
supports_websockets = true
requires_openai_auth = true
```

Use `/backend-api/codex`, not Pooler's narrow `/v1` SDK route. Do not set `chatgpt_base_url`; Pooler does not proxy Codex account, identity, realtime, or other app-server helper routes.

Load `CODEX_POOLER_API_KEY` from an approved secret manager into the environment. Do not paste the value into `config.toml`, this guide, a command example, a prompt, or the evidence record. Confirm only that the variable is present:

```zsh
test -n "$CODEX_POOLER_API_KEY"
```

The first runtime test intentionally omits Pooler's operator MCP endpoint.

## 4. Prove CSE preserves the provider

Hash the disposable configuration, rerun preview and apply, then confirm the hash is unchanged and the installer reports no managed changes:

```zsh
shasum -a 256 "$canary_codex_home/config.toml"
.venv/bin/cse install-codex --codex-home "$canary_codex_home"
.venv/bin/cse install-codex --codex-home "$canary_codex_home" --apply
shasum -a 256 "$canary_codex_home/config.toml"
```

The two hashes must match. A changed hash is a `FAIL`, even if the resulting TOML still parses.

## 5. Run the bounded native canary

Choose a model identifier exposed by the test Pool and start Codex from this repository with strict configuration checking:

```zsh
pool_model="<pool-exposed-model>"
CODEX_HOME="$canary_codex_home" codex --strict-config -m "$pool_model" -C "$(pwd)"
```

Use this bounded, non-sensitive request:

> Delegate to `cse_explorer` to map the callers of `plan_install` in `src/codex_global.py`. Stay read-only, do not delegate recursively, and return file and function names to the root for synthesis.

In Codex and its native agent UI, verify:

- the selected custom role is `cse_explorer`;
- the role remains read-only;
- the child creates no nested agent;
- no more than four agent threads are open;
- the root waits for the child and synthesizes the result; and
- the task completes through the websocket-capable provider.

Do not save the prompt, response, or repository details in the evidence record. Record only the check status and sanitized operational metadata.

## 6. Verify Pooler routing metadata

Using Pooler's operator UI, identify the canary request without copying its payload. Record only:

- pinned Pooler release;
- route family and endpoint class;
- requested model;
- synthetic Pool and upstream labels;
- status class;
- duration;
- retry count; and
- timestamp.

The route must be the Codex backend family. An ordinary HTTP success does not prove the websocket check passed.

## 7. Resume only the canary-created session

Exit the canary session, then resume the latest session from the same disposable home:

```zsh
CODEX_HOME="$canary_codex_home" codex resume --last --strict-config -m "$pool_model" -C "$(pwd)"
```

Ask for a one-sentence confirmation based on the existing canary context without new exploration. Verify through sanitized Pooler metadata that the resumed turn remains attached to the upstream assignment that owns the session.

Never run Pooler's session-retagging examples against the ordinary Codex home. This canary does not edit JSONL transcripts or SQLite state.

## 8. Optional multi-upstream retry check

Run this check only with separate approval and at least two authorized upstreams in a dedicated test Pool. Use Pooler's documented operator controls to safely induce a retryable condition for a new stateless synthetic request, then verify a bounded retry or failover in sanitized metadata.

Do not disturb an active user session, invalidate account authentication, or claim failover from a normal successful request. With only one eligible upstream, record this check as `NOT_APPLICABLE`.

## Evidence record

Use `PASS`, `FAIL`, `BLOCKED`, or `NOT_APPLICABLE` for every row.

| Check | Required | Status | Sanitized evidence |
| --- | --- | --- | --- |
| Exact CSE commit recorded | Yes |  | Commit only |
| Codex CLI version is `0.144.3` or newly re-verified | Yes |  | Version only |
| Pooler release is pinned | Yes |  | Release tag only |
| Ordinary config and state hashes unchanged | Yes |  | Before/after hashes |
| Disposable `CODEX_HOME` used | Yes |  | Redacted path label |
| CSE installer preview/apply/no-op preserved provider config | Yes |  | Actions and hashes |
| Native backend websocket request completed | Yes |  | Route, status, timestamp |
| `cse_explorer` selected and read-only | Yes |  | Role and sandbox |
| Delegation depth remained one | Yes |  | Thread count only |
| Root synthesized child output | Yes |  | Boolean result |
| Pooler selected an eligible upstream | Yes |  | Synthetic upstream label |
| Canary session resumed on owning upstream | Yes |  | Continuity result |
| Multi-upstream stateless retry | Conditional |  | Retry count or `NOT_APPLICABLE` |
| Dedicated Pool API key revoked | Yes |  | Revocation status only |
| Disposable state removed | Yes |  | Boolean result |

Recommend Pooler only as an optional interoperable provider when every required row is `PASS`. Any required `FAIL` or `BLOCKED` result prevents a compatibility recommendation. Missing evidence is not a pass.

## Rollback

1. Exit every Codex process using the disposable home.
2. Revoke the dedicated Pool API key in Pooler.
3. Unset `CODEX_POOLER_API_KEY` and any canary-only shell variables.
4. Review, then delete only the recorded disposable Codex directory.
5. Recompute the ordinary manifest and compare it byte-for-byte with the initial manifest:

   ```zsh
   ordinary_manifest_after="$(mktemp)"
   snapshot_ordinary_codex_home > "$ordinary_manifest_after"
   shasum -a 256 "$ordinary_manifest_before" "$ordinary_manifest_after"
   if ! cmp -s "$ordinary_manifest_before" "$ordinary_manifest_after"; then
     diff -u "$ordinary_manifest_before" "$ordinary_manifest_after"
     printf 'FAIL: ordinary Codex state changed\n' >&2
     exit 1
   fi
   ```

6. Stop or hand off the external Pooler deployment under its own approved operational plan.

If the ordinary hashes differ, stop and investigate; do not overwrite the ordinary Codex home from the disposable copy.

## Optional operator MCP follow-up

Pooler's MCP endpoint is not required for model traffic. If the runtime canary passes and an operator separately approves metadata access, configure it with a distinct operator token:

```toml
[mcp_servers.codex_pooler]
url = "https://codex-pooler.example.com/mcp"
bearer_token_env_var = "CODEX_POOLER_MCP_KEY"
```

Never use the Pool API key for MCP, and connect only hosts trusted with the operator's metadata view.
