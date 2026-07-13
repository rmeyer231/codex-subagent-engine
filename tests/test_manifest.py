"""Tests for manifest parsing."""

import pytest
from src.manifest import Manifest


SAMPLE_TOML = """
[task]
description = "Test task"

[[agents]]
type = "explorer"
instructions = "Explore the codebase"

[[agents]]
type = "reviewer"
instructions = "Review security"
depends_on = [0]
approval_required = true

[settings]
max_threads = 2
job_max_runtime_seconds = 60
require_approval = false
"""


def test_parse_manifest():
    m = Manifest.from_string(SAMPLE_TOML)
    assert m.description == "Test task"
    assert len(m.agents) == 2
    assert m.agents[0].type == "explorer"
    assert m.agents[1].type == "reviewer"
    assert m.agents[1].depends_on == [0]
    assert m.agents[1].approval_required is True


def test_parse_settings():
    m = Manifest.from_string(SAMPLE_TOML)
    assert m.settings.max_threads == 2
    assert m.settings.job_max_runtime_seconds == 60
    assert m.settings.require_approval is False


def test_default_settings():
    minimal = """
[task]
description = "Minimal"

[[agents]]
type = "worker"
instructions = "Do something"
"""
    m = Manifest.from_string(minimal)
    assert m.settings.max_threads == 4  # default
    assert m.settings.job_max_runtime_seconds == 120  # default
    assert m.agents[0].model == "claude-opus-4-6"  # default
    assert m.agents[0].sandbox is False  # default
