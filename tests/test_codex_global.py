"""Tests for the packaged Codex template resource loader.

The installer (Task 3) will need to render and write Codex agent/AGENTS/
model-routing templates that ship inside the distribution wheel. The
loader here is the single read-side interface to those packaged
resources.

It must:
- resolve resource names relative to the package data root,
- return the raw bytes/text content,
- raise a clear error when a packaged template is missing so callers
  can surface actionable messages instead of cryptic FileNotFoundError,
- fall back to importlib.resources when the direct filesystem
  path is unavailable (for example when the code lives inside a wheel
  installed to a read-only location where the absolute on-disk path
  does not exist).

Task 2 adds native Codex routing templates that the loader must surface:
four custom-agent profiles (cse_explorer, cse_planner,
cse_implementer, cse_reviewer), a managed global AGENTS.routing.md
block, a canonical model-routing.md template, and the managed
[agents] defaults for config.toml.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tomlkit

from src import codex_global


# --- Resource loader contract ------------------------------------------------


def test_package_data_root_exists() -> None:
    """The codex_global module exposes a discoverable data root."""
    root = codex_global.package_data_root()
    assert root.exists(), f"package data root missing: {root}"
    assert root.is_dir(), f"package data root is not a directory: {root}"


def test_load_template_returns_text() -> None:
    """load_template reads a packaged resource and returns its text contents."""
    text = codex_global.load_template("AGENTS.routing.md")
    assert isinstance(text, str)
    assert text.strip(), "AGENTS.routing.md template should not be empty"


def test_load_missing_template_raises_actionable_error() -> None:
    """Missing templates raise CodexTemplateNotFound with the package + name."""
    missing_resource = "missing-resource.md"
    with pytest.raises(codex_global.CodexTemplateNotFound) as excinfo:
        codex_global.load_template(missing_resource)
    msg = str(excinfo.value)
    assert missing_resource in msg
    assert "templates/codex" in msg


def test_load_template_rejects_path_traversal() -> None:
    """Resource names must not escape the package via '..' segments."""
    with pytest.raises(ValueError):
        codex_global.load_template("../pyproject.toml")


def test_load_template_falls_back_to_importlib_resources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When the direct filesystem path is unavailable, the loader uses
    importlib.resources to read from the src package's templates/codex
    subdirectory."""
    missing = tmp_path / "definitely-not-on-disk"
    monkeypatch.setattr(codex_global, "package_data_root", lambda: missing)

    text = codex_global.load_template("AGENTS.routing.md")
    assert isinstance(text, str)
    assert text.strip(), "AGENTS.routing.md template should not be empty"


# --- Task 2: Native Codex Routing Bundle -------------------------------------

AGENT_PROFILES = (
    "cse_explorer",
    "cse_planner",
    "cse_implementer",
    "cse_reviewer",
)

# Names that must NOT be reused (would collide with Codex built-ins).
BUILTIN_NAMES = {"default", "worker", "explorer"}


def _load_agent_toml(name: str) -> tomlkit.TOMLDocument:
    """Load and parse a packaged agent TOML profile."""
    text = codex_global.load_template(f"agents/{name}.toml")
    return tomlkit.parse(text)


@pytest.mark.parametrize("agent_name", AGENT_PROFILES)
def test_agent_profile_exists_and_parses(agent_name: str) -> None:
    """Every required agent TOML is shipped under agents/ and parses cleanly."""
    doc = _load_agent_toml(agent_name)
    assert doc is not None


@pytest.mark.parametrize("agent_name", AGENT_PROFILES)
def test_agent_profile_has_required_fields(agent_name: str) -> None:
    """Each profile declares name, description, and developer_instructions."""
    doc = _load_agent_toml(agent_name)
    assert "name" in doc, f"{agent_name}: missing 'name'"
    assert "description" in doc, f"{agent_name}: missing 'description'"
    assert "developer_instructions" in doc, f"{agent_name}: missing 'developer_instructions'"
    assert str(doc["name"]).strip(), f"{agent_name}: 'name' is empty"
    assert str(doc["description"]).strip(), f"{agent_name}: 'description' is empty"
    assert str(doc["developer_instructions"]).strip(), (
        f"{agent_name}: 'developer_instructions' is empty"
    )


@pytest.mark.parametrize("agent_name", AGENT_PROFILES)
def test_agent_profile_uses_developer_instructions_not_instructions(
    agent_name: str,
) -> None:
    """Profiles use the native 'developer_instructions' field, not 'instructions'."""
    doc = _load_agent_toml(agent_name)
    assert "instructions" not in doc, (
        f"{agent_name}: must not contain legacy 'instructions'; "
        f"native schema requires 'developer_instructions'"
    )


@pytest.mark.parametrize("agent_name", AGENT_PROFILES)
def test_agent_profile_name_matches_filename(agent_name: str) -> None:
    """Each profile's name matches its filename (1:1 with native schema)."""
    doc = _load_agent_toml(agent_name)
    assert str(doc["name"]) == agent_name, (
        f"{agent_name}: profile 'name' must equal filename (got {doc['name']!r})"
    )


@pytest.mark.parametrize("agent_name", AGENT_PROFILES)
def test_agent_profile_name_is_not_builtin(agent_name: str) -> None:
    """Custom profiles never reuse Codex built-in names."""
    assert agent_name not in BUILTIN_NAMES, (
        f"{agent_name} collides with a Codex built-in"
    )
    assert len(set(AGENT_PROFILES)) == len(AGENT_PROFILES)


def test_read_only_agents_default_to_read_only_sandbox() -> None:
    """Explorer, planner, and reviewer default to read-only operation."""
    read_only = ("cse_explorer", "cse_planner", "cse_reviewer")
    for agent_name in read_only:
        doc = _load_agent_toml(agent_name)
        sandbox_mode = str(doc.get("sandbox_mode", "")).strip().lower()
        assert sandbox_mode == "read-only", (
            f"{agent_name} should be read-only by default, "
            f"sandbox_mode={sandbox_mode!r}"
        )


def test_implementer_uses_workspace_write_sandbox() -> None:
    """The implementer is limited to workspace-scoped writes by default."""
    doc = _load_agent_toml("cse_implementer")
    sandbox_mode = str(doc.get("sandbox_mode", "")).strip().lower()
    assert sandbox_mode == "workspace-write", (
        f"cse_implementer should default to workspace-write, "
        f"sandbox_mode={sandbox_mode!r}"
    )


@pytest.mark.parametrize("agent_name", AGENT_PROFILES)
def test_agent_profile_uses_sandbox_mode_key(agent_name: str) -> None:
    """Profiles use the native 'sandbox_mode' key, not legacy 'sandbox'."""
    doc = _load_agent_toml(agent_name)
    assert "sandbox" not in doc, (
        f"{agent_name}: must not contain legacy 'sandbox'; "
        f"native schema requires 'sandbox_mode'"
    )
    assert "sandbox_mode" in doc, (
        f"{agent_name}: missing required 'sandbox_mode' key"
    )


@pytest.mark.parametrize("agent_name", AGENT_PROFILES)
def test_agent_profile_omits_model_pin(agent_name: str) -> None:
    """Profiles inherit the parent model; no 'model' key is set."""
    doc = _load_agent_toml(agent_name)
    assert "model" not in doc, (
        f"{agent_name}: custom profile must inherit parent model "
        f"(found 'model' = {doc.get('model')!r})"
    )


def test_agent_profiles_distinct_names() -> None:
    """Each profile name is unique across the bundle."""
    names = [str(_load_agent_toml(p)["name"]) for p in AGENT_PROFILES]
    assert len(set(names)) == len(names), f"duplicate agent names: {names}"


# --- Managed global AGENTS routing source -----------------------------------

# Packaged-source filename for the CSE managed routing block.
# AGENTS.routing.md is the packaged source shipped inside the distribution
# wheel; it is NOT a Codex auto-discovery target. The installer (Task 3)
# extracts the managed block from this source and inserts it into
# ~/.codex/AGENTS.md (Codex auto-discovers ~/.codex/AGENTS.override.md if
# non-empty, otherwise ~/.codex/AGENTS.md). The packaged source itself is
# never copied to ~/.codex/AGENTS.routing.md. The legacy agents/AGENTS.md
# placeholder from Task 1 is also removed from the bundle.
ROUTING_SOURCE_NAME = "AGENTS.routing.md"


def test_routing_source_resource_loads_from_packaged_path() -> None:
    """The packaged source resource loads from the bundled AGENTS.routing.md path."""
    text = codex_global.load_template(ROUTING_SOURCE_NAME)
    assert isinstance(text, str)
    assert text.strip(), "AGENTS.routing.md template should not be empty"


def test_agents_md_template_is_not_shipped() -> None:
    """The legacy agents/AGENTS.md placeholder is removed from the bundle."""
    with pytest.raises(codex_global.CodexTemplateNotFound):
        codex_global.load_template("agents/AGENTS.md")


def test_routing_source_has_managed_markers() -> None:
    """The routing source uses the BEGIN/END marker pair for managed-block updates."""
    text = codex_global.load_template(ROUTING_SOURCE_NAME)
    assert "<!-- BEGIN CSE-MANAGED -->" in text
    assert "<!-- END CSE-MANAGED -->" in text


def test_routing_source_contains_role_to_phase_rows() -> None:
    """The routing source contains an explicit role-to-phase row for each cse_* role."""
    text = codex_global.load_template(ROUTING_SOURCE_NAME)
    # Each row pairs a phase keyword with a cse_* role on the same line.
    required_rows = (
        "cse_explorer",
        "cse_planner",
        "cse_implementer",
        "cse_reviewer",
    )
    for role in required_rows:
        # Same line must mention both the role and a phase verb stem.
        matched = False
        for line in text.splitlines():
            lowered = line.lower()
            if role in lowered and (
                "explor" in lowered
                or "plan" in lowered
                or "implement" in lowered
                or "review" in lowered
            ):
                matched = True
                break
        assert matched, (
            f"routing source missing same-line role-to-phase row for {role!r}"
        )


def test_routing_source_requires_root_owned_phase_gates() -> None:
    """The routing source asserts the root owns phase gates and synthesis."""
    text = codex_global.load_template(ROUTING_SOURCE_NAME).lower()
    assert "phase gate" in text or "phase-gate" in text or "gates" in text
    assert "root" in text
    assert "synthes" in text


def test_routing_source_makes_canonical_model_routing_advisory() -> None:
    """The installed block consults canonical routing without gating work."""
    text = codex_global.load_template(ROUTING_SOURCE_NAME).lower()
    assert "~/.codex/model-routing.md" in text
    assert "mappings are advisory" in text
    assert "must not block work" in text
    assert "unless the user explicitly requests a change" in text


def test_routing_source_states_non_delegation_criteria() -> None:
    """The source enumerates when NOT to delegate (trivial/sequential work)."""
    text = codex_global.load_template(ROUTING_SOURCE_NAME).lower()
    assert "trivial" in text, "routing source must list trivial-work non-delegation"
    assert "sequential" in text, (
        "routing source must list sequential-work non-delegation"
    )


def test_routing_source_enforces_parallel_write_isolation() -> None:
    """The source forbids concurrent subagents from owning overlapping files."""
    text = codex_global.load_template(ROUTING_SOURCE_NAME).lower()
    assert "overlap" in text or "disjoint" in text
    assert "parallel" in text
    assert "serial" in text or "one owner" in text or "serializ" in text


def test_routing_source_does_not_advertise_routing_path_destination() -> None:
    """The routing source does not claim to be installed at ~/.codex/AGENTS.routing.md."""
    text = codex_global.load_template(ROUTING_SOURCE_NAME)
    forbidden_phrases = (
        "copy this file to ~/.codex/AGENTS.routing.md",
        "copies it to ~/.codex/AGENTS.routing.md",
        "install this file at ~/.codex/AGENTS.routing.md",
        "destination ~/.codex/AGENTS.routing.md",
        "writes this file to ~/.codex/AGENTS.routing.md",
    )
    lowered = text.lower()
    for phrase in forbidden_phrases:
        assert phrase.lower() not in lowered, (
            f"routing source must not advertise itself as an installed file "
            f"at ~/.codex/AGENTS.routing.md; found forbidden phrase: {phrase!r}"
        )


def test_routing_source_declares_itself_packaged_source() -> None:
    """The routing source explicitly states it is the packaged source for the managed block."""
    text = codex_global.load_template(ROUTING_SOURCE_NAME).lower()
    assert "packaged source" in text, (
        "routing source must declare itself the 'packaged source' for "
        "the managed block"
    )
    # Managed block is inserted into the user's AGENTS.md, not AGENTS.routing.md.
    assert "~/.codex/agents.md" in text, (
        "routing source must reference ~/.codex/AGENTS.md as the "
        "auto-discovery destination"
    )


def test_model_routing_references_agents_md_destination() -> None:
    """The model-routing.md template references the CSE managed block in ~/.codex/AGENTS.md."""
    text = codex_global.load_template("model-routing.md")
    assert "~/.codex/AGENTS.md" in text, (
        "model-routing.md must reference the CSE managed block in ~/.codex/AGENTS.md"
    )
    assert "~/.codex/AGENTS.routing.md" not in text, (
        "model-routing.md must not reference ~/.codex/AGENTS.routing.md; "
        "AGENTS.routing.md is the packaged source, not an installed destination"
    )


# --- Canonical model-routing.md ----------------------------------------------


def test_model_routing_template_exists() -> None:
    """A canonical model-routing.md template is shipped in the bundle."""
    text = codex_global.load_template("model-routing.md")
    assert isinstance(text, str)
    assert text.strip(), "model-routing.md template should not be empty"


def test_model_routing_uses_lowercase_path_reference() -> None:
    """The model-routing.md template references the canonical lowercase path."""
    text = codex_global.load_template("model-routing.md")
    assert "~/.codex/model-routing.md" in text


def test_model_routing_has_required_alias_rows() -> None:
    """The model-routing.md template contains each exact OpenLimits model row."""
    text = codex_global.load_template("model-routing.md")
    # Required (phase keyword, alias) pairs that must co-occur on the same line.
    required_rows = (
        ("proposal", "openai/gpt-5.6-sol"),
        ("spec", "openai/gpt-5.6-sol"),
        ("architecture", "openai/gpt-5.6-sol"),
        ("implementation", "openai/gpt-5.6-terra"),
        ("tdd", "openai/gpt-5.6-terra"),
        ("coding", "openai/gpt-5.6-terra"),
        ("summary", "openai/gpt-5.6-luna"),
        ("lookup", "openai/gpt-5.6-luna"),
        ("low-stakes", "openai/gpt-5.6-luna"),
    )
    for phase, alias in required_rows:
        matched = any(
            phase.lower() in line.lower() and alias in line
            for line in text.splitlines()
        )
        assert matched, (
            f"model-routing.md missing same-line alias row for "
            f"{phase!r} -> {alias!r}"
        )


def test_model_routing_default_alias_is_sonnet() -> None:
    """The default model is exactly OpenLimits Terra on a Markdown table row."""
    text = codex_global.load_template("model-routing.md")
    matched = any(
        "default" in line.lower()
        and "openai/gpt-5.6-terra" in line
        and "|" in line
        for line in text.splitlines()
    )
    assert matched, (
        "model-routing.md missing pipe-delimited Markdown table row "
        "containing 'default' and 'openai/gpt-5.6-terra'"
    )


def test_model_routing_is_advisory_and_non_blocking() -> None:
    """A phase/model mismatch never pauses work or requires a switch."""
    text = codex_global.load_template("model-routing.md").lower()
    assert "recommendations, not phase gates" in text
    assert "must not stop" in text
    assert "ask the user to switch models" in text
    assert "continues with the current model" in text


# --- Managed [agents] defaults in config.toml --------------------------------


def test_config_template_exists_and_parses() -> None:
    """The config.toml template is shipped and parses as valid TOML."""
    text = codex_global.load_template("config.toml")
    doc = tomlkit.parse(text)
    assert "agents" in doc, "config.toml missing required [agents] table"


def test_config_template_agents_defaults() -> None:
    """Managed [agents] defaults match the brief: 4 threads, depth 1, 1800s, interrupts on."""
    text = codex_global.load_template("config.toml")
    doc = tomlkit.parse(text)
    agents = doc["agents"]
    assert int(agents["max_threads"]) == 4
    assert int(agents["max_depth"]) == 1
    assert int(agents["job_max_runtime_seconds"]) == 1800
    assert bool(agents["interrupt_message"]) is True
