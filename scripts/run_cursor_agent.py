#!/usr/bin/env python3
"""
Optional: run a Cursor SDK agent against a forged project directory.

Requires: pip install cursor-sdk
Docs: https://cursor.com/docs/sdk/python

Usage:
  export CURSOR_API_KEY=...
  python scripts/run_cursor_agent.py /path/to/project "Implement task T-abc123"
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: run_cursor_agent.py <project_dir> <prompt>")
        return 2

    project_dir = sys.argv[1]
    prompt = " ".join(sys.argv[2:])
    api_key = os.environ.get("CURSOR_API_KEY")
    if not api_key:
        print("Set CURSOR_API_KEY")
        return 1

    try:
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
    except ImportError:
        print("Install cursor-sdk: pip install cursor-sdk")
        return 1

    result = Agent.prompt(
        prompt,
        AgentOptions(
            api_key=api_key,
            model="composer-2.5",
            local=LocalAgentOptions(cwd=project_dir),
        ),
    )
    print(result.status)
    print(result.result)
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
