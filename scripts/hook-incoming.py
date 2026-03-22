#!/usr/bin/env python3
"""
UserPromptSubmit hook: auto-log incoming Telegram messages to ClarionBot DB.

Only logs messages that contain a <channel source="plugin:telegram:telegram"> tag.
Terminal and other prompts are silently ignored.

Claude Code passes a JSON payload on stdin. The exact schema isn't fully
documented, so we defensively search for the channel tag across all string
fields.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

LOG_SCRIPT = Path(__file__).parent / "log.py"

CHANNEL_RE = re.compile(
    r'<channel\s[^>]*source="plugin:telegram:telegram"[^>]*>',
    re.IGNORECASE,
)
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
CONTENT_RE = re.compile(
    r'<channel\b[^>]*>(.*?)</channel>',
    re.DOTALL | re.IGNORECASE,
)


def extract_channel(text: str):
    """Return (content, ts) from the first telegram channel tag, or None."""
    tag_match = CHANNEL_RE.search(text)
    if not tag_match:
        return None

    attrs = dict(ATTR_RE.findall(tag_match.group(0)))
    ts = attrs.get("ts", "")

    content_match = CONTENT_RE.search(text, tag_match.start())
    if not content_match:
        return None

    content = content_match.group(1).strip()
    return content, ts


def search_strings(obj, depth=0):
    """Recursively search all string values in a JSON object."""
    if depth > 5:
        return None
    if isinstance(obj, str):
        result = extract_channel(obj)
        if result:
            return result
    elif isinstance(obj, dict):
        for v in obj.values():
            result = search_strings(v, depth + 1)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = search_strings(item, depth + 1)
            if result:
                return result
    return None


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)

    # Try JSON parse first; fall back to treating raw as plain text
    try:
        payload = json.loads(raw)
        result = search_strings(payload)
    except json.JSONDecodeError:
        result = extract_channel(raw)

    if not result:
        sys.exit(0)

    content, ts = result
    if not content:
        sys.exit(0)

    cmd = ["python3", str(LOG_SCRIPT), "user", content]
    if ts:
        cmd += ["--ts", ts]

    subprocess.run(cmd, check=False, capture_output=True)


if __name__ == "__main__":
    main()
