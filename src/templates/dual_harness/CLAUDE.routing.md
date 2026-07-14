<!-- BEGIN CSE-DUAL-HARNESS -->
# CSE Dual-Harness Routing

Claude Desktop, the ordinary `claude` command, and RepoPrompt CE's generated
`claude-rpce` wrapper stay on native Claude Pro. The explicit
`claude-openlimits` and `claude-openlimits-rpce` launchers use OpenLimits;
the latter composes the OpenLimits lane with RepoPrompt CE MCP discovery.
ChatGPT Free is a separate manual fallback and never supplies API capacity.

## Phase routing

| Phase | OpenLimits Claude model |
| --- | --- |
| Explicit architecture and synthesis | `{{CLAUDE_ARCHITECTURE_MODEL}}` |
| Implementation, TDD, general coding | `{{CLAUDE_IMPLEMENTATION_MODEL}}` |
| Summaries, quick lookups, low-stakes work | `{{CLAUDE_LOW_STAKES_MODEL}}` |

These mappings are advisory. Continue with the current model unless the user
explicitly requests a switch.

## Cross-harness ownership

Exactly one root harness owns OpenSpec phase gates, user communication, result
synthesis, and the completion claim. Exactly one harness is the sole writer for
a checkout. A write-capable handoff records `owner`, `worktree`, `branch`,
`objective`, `allowed_files`, `artifacts`, `phase`, and `validation`; a receiver
with missing ownership metadata remains read-only.

Claude's Codex plugin is already one delegation boundary. A routine plugin job
MUST NOT request a second CSE delegation layer. Routine cross-harness review is
limited to one planning review, one final review, and one correction/re-review
cycle unless the user directs otherwise.
<!-- END CSE-DUAL-HARNESS -->
