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
cse_implementer, cse_reviewer), a managed global AGENTS.md
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
    text = codex_global.load_template("agents/AGENTS.md")
    assert isinstance(text, str)
    assert text.strip(), "AGENTS.md template should not be empty"


def test_load_missing_template_raises_actionable_error() -> None:
    """Missing templates raise CodexTemplateNotFound with the package + name."""
    with pytest.raises(codex_global.CodexTemplateNotFound) as excinfo:
        codex_global.load_template("agents/does_not_exist.md")
    msg = str(excinfo.value)
    assert "agents/does_not_exist.md" in msg
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

    text = codex_global.load_template("agents/AGENTS.md")
    assert isinstance(text, str)
    assert text.strip(), "AGENTS.md template should not be empty"


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
    """Each profile declares name, description, and instructions."""
    doc = _load_agent_toml(agent_name)
    assert "name" in doc, f"{agent_name}: missing 'name'"
    assert "description" in doc, f"{agent_name}: missing 'description'"
    assert "instructions" in doc, f"{agent_name}: missing 'instructions'"
    assert str(doc["name"]).strip(), f"{agent_name}: 'name' is empty"
    assert str(doc["description"]).strip(), f"{agent_name}: 'description' is empty"
    assert str(doc["instructions"]).strip(), f"{agent_name}: 'instructions' is empty"


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
        sandbox = str(doc.get("sandbox", "")).strip().lower()
        assert sandbox == "read-only", (
            f"{agent_name} should be read-only by default, sandbox={sandbox!r}"
        )


def test_implementer_uses_workspace_write_sandbox() -> None:
    """The implementer is limited to workspace-scoped writes by default."""
    doc = _load_agent_toml("cse_implementer")
    sandbox = str(doc.get("sandbox", "")).strip().lower()
    assert sandbox == "workspace-write", (
        f"cse_implementer should default to workspace-write, sandbox={sandbox!r}"
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


# --- Managed global AGENTS routing block -------------------------------------


def test_agents_md_has_managed_markers() -> None:
    """AGENTS.md uses the BEGIN/END marker pair for managed-block updates."""
    text = codex_global.load_template("agents/AGENTS.md")
    assert "<!-- BEGIN CSE-MANAGED -->" in text
    assert "<!-- END CSE-MANAGED -->" in text


def test_agents_md_routing_block_maps_roles_to_phases() -> None:
    """The managed block maps each phase to a deterministic cse_* role."""
    text = codex_global.load_template("agents/AGENTS.md").lower()
    expected_pairs = {
        "cse_explorer": "explor",
        "cse_planner": "plan",
        "cse_implementer": "implement",
        "cse_reviewer": "review",
    }
    for role, hint in expected_pairs.items():
        assert role in text, f"managed block missing role {role}"
        assert hint in text, f"managed block missing phase keyword {hint!r}"


def test_agents_md_requires_root_owned_phase_gates() -> None:
    """The managed block asserts the root owns phase gates and synthesis."""
    text = codex_global.load_template("agents/AGENTS.md").lower()
    assert "phase gate" in text or "phase-gate" in text or "gates" in text
    assert "root" in text
    assert "synthes" in text


def test_agents_md_states_non_delegation_criteria() -> None:
    """The block enumerates when NOT to delegate (trivial/sequential work)."""
    text = codex_global.load_template("agents/AGENTS.md").lower()
    assert "trivial" in text, "managed block must list trivial-work non-delegation"
    assert "sequential" in text, (
        "managed block must list sequential-work non-delegation"
    )


def test_agents_md_enforces_parallel_write_isolation() -> None:
    """The block forbids concurrent subagents from owning overlapping files."""
    text = codex_global.load_template("agents/AGENTS.md").lower()
    assert "overlap" in text or "disjoint" in text
    assert "parallel" in text
    assert "serial" in text or "one owner" in text or "serializ" in text


def test_agents_md_references_model_routing_path() -> None:
    """The managed block points at the canonical lowercase model-routing.md."""
    text = codex_global.load_template("agents/AGENTS.md")
    assert "~/.codex/model-routing.md" in text, (
        "managed block must reference canonical lowercase ~/.codex/model-routing.md"
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


def test_model_routing_phase_table_present() -> None:
    """The model-routing.md template includes a phase table with phases."""
    text = codex_global.load_template("model-routing.md").lower()
    for phase in ("brainstorm", "implementation", "summarization"):
        assert phase in text, (
            f"model-routing.md phase table missing keyword {phase!r}"
        )


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