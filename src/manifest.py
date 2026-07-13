"""
TOML manifest parser for subagent task definitions.

Manifest format:
  [task]
  description = "Review this PR for security issues"

  [[agents]]
  type = "explorer"
  instructions = "Map all files changed in the PR"

  [[agents]]
  type = "reviewer"
  instructions = "Review for security vulnerabilities"
  model = "claude-opus-4-6"
  sandbox = true

  [settings]
  max_threads = 4
  job_max_runtime_seconds = 120
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentConfig:
    type: str                       # "explorer" | "worker" | "reviewer" | custom
    instructions: str
    model: str = "claude-opus-4-6"
    sandbox: bool = False
    depends_on: list[int] = field(default_factory=list)  # indices of agents that must finish first
    approval_required: bool = False  # pause for human review before applying


@dataclass
class Settings:
    max_threads: int = 4
    job_max_runtime_seconds: int = 120
    require_approval: bool = False  # global approval gate


@dataclass
class Manifest:
    description: str
    agents: list[AgentConfig]
    settings: Settings

    @classmethod
    def from_file(cls, path: str | Path) -> Manifest:
        data = tomllib.loads(Path(path).read_text())

        task = data.get("task", {})
        description = task.get("description", "")

        raw_agents = data.get("agents", [])
        agents = [
            AgentConfig(
                type=a["type"],
                instructions=a["instructions"],
                model=a.get("model", "claude-opus-4-6"),
                sandbox=a.get("sandbox", False),
                depends_on=a.get("depends_on", []),
                approval_required=a.get("approval_required", False),
            )
            for a in raw_agents
        ]

        raw_settings = data.get("settings", {})
        settings = Settings(
            max_threads=raw_settings.get("max_threads", 4),
            job_max_runtime_seconds=raw_settings.get("job_max_runtime_seconds", 120),
            require_approval=raw_settings.get("require_approval", False),
        )

        return cls(description=description, agents=agents, settings=settings)

    @classmethod
    def from_string(cls, toml_str: str) -> Manifest:
        path = Path("/tmp/_cse_manifest.toml")
        path.write_text(toml_str)
        return cls.from_file(path)
