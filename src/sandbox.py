"""
Process isolation for subagents.

Sandboxed subagents run in a subprocess with:
- Restricted environment variables (only what's needed)
- Optional timeout enforcement
- stdout/stderr capture
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


async def run_sandboxed(
    script: str,
    env_vars: dict[str, str] | None = None,
    timeout_seconds: int = 120,
) -> SandboxResult:
    """
    Run a Python script in a sandboxed subprocess.
    The script receives only explicitly passed env vars.
    """
    # Build a minimal environment
    safe_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
    }
    if env_vars:
        safe_env.update(env_vars)

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=safe_env,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds,
        )
        return SandboxResult(
            exit_code=proc.returncode or 0,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )
    except TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return SandboxResult(exit_code=-1, stdout="", stderr="Timeout", timed_out=True)
    except Exception as e:
        return SandboxResult(exit_code=-1, stdout="", stderr=str(e))
