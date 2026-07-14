"""Contract tests for the canonical dual-harness routing policy."""

from __future__ import annotations

import json
from pathlib import Path

import tomlkit

from src import dual_harness_global


FIXTURES = Path(__file__).parent / "fixtures"


def test_plugin_canary_fixture_is_non_networked_and_uses_app_server() -> None:
    fixture = json.loads(
        (FIXTURES / "claude_codex_plugin.json").read_text(encoding="utf-8")
    )
    assert fixture["command"] == ["codex", "app-server"]
    assert fixture["codex_home_resolution"] == "${CODEX_HOME:-~/.codex}"
    assert fixture["network_allowed"] is False
    assert fixture["provider_request_allowed"] is False


def test_policy_has_verified_provider_boundaries_and_models() -> None:
    policy = dual_harness_global.load_policy()
    assert policy["providers"]["claude_native"]["billing"] == "Claude Pro"
    assert policy["providers"]["claude_openlimits"]["base_url"] == (
        "https://openlimits.app"
    )
    assert policy["providers"]["codex_openlimits"]["base_url"] == (
        "https://openlimits.app/v1"
    )
    assert policy["providers"]["codex_openlimits"]["wire_api"] == "responses"
    assert policy["models"]["claude"]["architecture"] == "anthropic/fable-5"
    assert policy["models"]["claude"]["implementation"] == (
        "anthropic/claude-sonnet-5"
    )
    assert policy["models"]["claude"]["low_stakes"] == (
        "anthropic/claude-haiku-4.5"
    )
    assert policy["models"]["codex"]["planning_review"] == (
        "openai/gpt-5.6-sol"
    )
    assert policy["models"]["codex"]["implementation"] == (
        "openai/gpt-5.6-terra"
    )
    assert policy["models"]["codex"]["low_stakes"] == (
        "openai/gpt-5.6-luna"
    )
    assert policy["defaults"]["codex_model"] == "openai/gpt-5.6-terra"
    assert policy["surfaces"]["claude_repoprompt_ce"] == "claude_native"
    assert (
        policy["surfaces"]["claude_openlimits_repoprompt_ce"]
        == "claude_openlimits"
    )


def test_policy_keeps_model_routing_advisory_and_handoffs_complete() -> None:
    policy = dual_harness_global.load_policy()
    assert policy["advisory"] is True
    assert policy["review_limits"] == {
        "planning_reviews": 1,
        "final_reviews": 1,
        "correction_cycles": 1,
    }
    assert policy["handoff_fields"] == [
        "owner",
        "worktree",
        "branch",
        "objective",
        "allowed_files",
        "artifacts",
        "phase",
        "validation",
    ]


def test_packaged_assets_validate_against_canonical_policy() -> None:
    dual_harness_global.validate_packaged_policy()
    policy = dual_harness_global.load_policy()
    rendered = (
        dual_harness_global.render_claude_routing()
        + dual_harness_global.render_claude_model_routing()
    )
    for model in policy["models"]["claude"].values():
        assert rendered.count(model) == 2


def test_launcher_is_runtime_only_and_forwards_arguments() -> None:
    launcher = dual_harness_global.render_launcher(
        credential_command=("/tmp/fake credential", "--print"),
        claude_command=("/tmp/fake claude",),
    )
    assert "{{" not in launcher
    assert "'/tmp/fake credential' --print" in launcher
    assert "exec '/tmp/fake claude' \"$@\"" in launcher
    assert "unset ANTHROPIC_AUTH_TOKEN" in launcher
    assert "ANTHROPIC_API_KEY=\"$token\"" in launcher
    assert "ANTHROPIC_AUTH_TOKEN=\"$token\"" not in launcher
    assert "sk-" not in launcher


def test_repoprompt_ce_launcher_composes_runtime_auth_and_forwards_arguments() -> None:
    launcher = dual_harness_global.render_repoprompt_ce_launcher(
        credential_command=("/tmp/fake credential", "--print"),
        repoprompt_ce_command=("/tmp/fake claude-rpce",),
    )
    assert "{{" not in launcher
    assert "'/tmp/fake credential' --print" in launcher
    assert "exec '/tmp/fake claude-rpce' \"$@\"" in launcher
    assert "unset ANTHROPIC_AUTH_TOKEN" in launcher
    assert 'ANTHROPIC_API_KEY="$token"' in launcher
    assert "RepoPrompt CE" in launcher
    assert "sk-" not in launcher


def test_codex_templates_match_policy_and_plugin_delegation_contract() -> None:
    policy = dual_harness_global.load_policy()
    routing = dual_harness_global.load_codex_template("AGENTS.routing.md")
    model_routing = dual_harness_global.load_codex_template("model-routing.md")
    normalized_routing = " ".join(routing.split())
    for model in policy["models"]["codex"].values():
        assert model in model_routing
    assert "already delegated" in routing
    assert "sole writer" in routing
    assert "MUST NOT create a second CSE delegation layer" in normalized_routing
    for field in policy["handoff_fields"]:
        assert f"`{field}`" in routing


def test_rendered_codex_provider_uses_command_auth_not_env_key() -> None:
    rendered = dual_harness_global.render_codex_config(
        "[projects.\"/tmp/example\"]\ntrust_level = \"trusted\"\n",
        keychain_service="OpenLimits",
        keychain_account="api-key",
    )
    doc = tomlkit.parse(rendered)
    provider = doc["model_providers"]["openlimits"]
    assert provider["base_url"] == "https://openlimits.app/v1"
    assert provider["wire_api"] == "responses"
    assert "env_key" not in provider
    assert provider["auth"]["command"] == "/usr/bin/security"
    assert list(provider["auth"]["args"]) == [
        "find-generic-password",
        "-s",
        "OpenLimits",
        "-a",
        "api-key",
        "-w",
    ]
    assert doc["model_provider"] == "openlimits"
    assert doc["model"] == "openai/gpt-5.6-terra"
    assert doc["projects"]["/tmp/example"]["trust_level"] == "trusted"
