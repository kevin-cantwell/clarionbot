#!/usr/bin/env python3
"""
Tag the current conversation with a topic name.

Usage:
    tag.py <topic> [<topic2> ...]

This makes the conversation retrievable via `context.py <topic>`.
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"
CONV_FILE = Path(__file__).parent.parent / "db" / ".current_conversation"


def get_conn():
    if not DB_PATH.exists():
        print("DB not found. Run scripts/init-db.py first.", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    return conn


def main():
    if len(sys.argv) < 2:
        print("Usage: tag.py <topic> [<topic2> ...]", file=sys.stderr)
        sys.exit(1)

    topics = sys.argv[1:]

    if not CONV_FILE.exists():
        print("No active conversation.", file=sys.stderr)
        sys.exit(1)

    val = CONV_FILE.read_text().strip()
    if not val.isdigit():
        print("Invalid conversation file.", file=sys.stderr)
        sys.exit(1)
    conv_id = int(val)

    conn = get_conn()
    try:
        for topic in topics:
            conn.execute(
                "INSERT OR IGNORE INTO conversation_topics (conversation_id, topic) VALUES (?,?)",
                (conv_id, topic.lower())
            )
        conn.commit()
        print(f"Tagged conversation {conv_id} with: {', '.join(topics)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
