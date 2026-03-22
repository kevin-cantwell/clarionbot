#!/usr/bin/env python3
"""
PostToolUse hook: automatically log assistant Telegram replies to ClarionBot DB.

Receives a JSON payload on stdin from Claude Code with shape:
{
  "tool_name": "mcp__plugin_telegram_telegram__reply",
  "tool_input": {"chat_id": "...", "text": "...", ...},
  ...
}
"""

import json
import subprocess
import sys
from pathlib import Path

LOG_SCRIPT = Path(__file__).parent / "log.py"


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    if payload.get("tool_name") != "mcp__plugin_telegram_telegram__reply":
        sys.exit(0)

    text = payload.get("tool_input", {}).get("text", "")
    if not text:
        sys.exit(0)

    subprocess.run(
        ["python3", str(LOG_SCRIPT), "assistant", text],
        check=False,
        capture_output=True,
    )


if __name__ == "__main__":
    main()
