#!/usr/bin/env python3
"""
Stop hook: summarize the current conversation using the local Ollama model.

Fires when Claude stops responding. Reads the current conversation ID from
db/.current_conversation and regenerates its summary via summarize.py.
Skips if no active conversation or if Ollama is unreachable.
"""

import subprocess
import sys
from pathlib import Path

CONV_FILE = Path(__file__).parent.parent / "db" / ".current_conversation"
SUMMARIZE = Path(__file__).parent / "summarize.py"


def main():
    if not CONV_FILE.exists():
        sys.exit(0)

    val = CONV_FILE.read_text().strip()
    if not val.isdigit():
        sys.exit(0)

    conv_id = val
    subprocess.run(
        ["python3", str(SUMMARIZE), "--conv", conv_id],
        capture_output=True,  # don't pollute Claude's output
        timeout=45,
    )


if __name__ == "__main__":
    main()
