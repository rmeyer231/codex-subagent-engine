"""
Subagent lifecycle: init → execute → report.

Each subagent is an independent worker that:
1. Receives instructions and optional context
2. Calls Claude with its specific system prompt
3. Returns a structured result

Subagents are stateless — all context must be passed in explicitly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

import anthropic

from .manifest import AgentConfig


class SubagentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"  # human rejected the output


@dataclass
class SubagentResult:
    agent_index: int
    agent_type: str
    instructions: str
    output: str
    status: SubagentStatus
    error: str | None = None


SYSTEM_PROMPTS = {
    "explorer": """You are an Explorer agent. Your job is to map and understand a codebase or set of files.
When exploring:
- List all relevant files with their purpose
- Identify key patterns, dependencies, and entry points
- Note anything that looks unusual or important
Be thorough but concise. Output a structured summary.""",

    "worker": """You are a Worker agent. Your job is to make targeted, precise changes.
When working:
- Make only the changes explicitly requested
- Explain each change and why it's correct
- Flag any risks or side effects
Output the exact changes to be made, with clear before/after context.""",

    "reviewer": """You are a Reviewer agent. Your job is to validate quality and correctness.
When reviewing:
- Check for bugs, security issues, and logic errors
- Verify the proposed changes match the stated intent
- Rate each finding: 🔴 critical, 🟡 warning, 🔵 info
Output a structured review with a clear pass/fail recommendation.""",
}


async def run_subagent(
    config: AgentConfig,
    agent_index: int,
    context: str = "",
    timeout_seconds: int = 120,
) -> SubagentResult:
    """Execute a single subagent and return its result."""
    system_prompt = SYSTEM_PROMPTS.get(
        config.type,
        f"You are a {config.type} agent. Follow the instructions carefully and produce a high-quality output."
    )

    user_message = config.instructions
    if context:
        user_message = f"## Context from previous agents\n\n{context}\n\n## Your Task\n\n{config.instructions}"

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    try:
        response = client.messages.create(
            model=config.model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        output = response.content[0].text
        return SubagentResult(
            agent_index=agent_index,
            agent_type=config.type,
            instructions=config.instructions,
            output=output,
            status=SubagentStatus.COMPLETED,
        )
    except Exception as e:
        return SubagentResult(
            agent_index=agent_index,
            agent_type=config.type,
            instructions=config.instructions,
            output="",
            status=SubagentStatus.FAILED,
            error=str(e),
        )
