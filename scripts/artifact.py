#!/usr/bin/env python3
"""
Register a file as an artifact linked to the current conversation.

Usage:
    artifact.py <path> [--description "..."] [--message-id N]

The path is stored as-is (use absolute paths for durability).
Prints the artifact id on success.
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"
CONV_FILE = Path(__file__).parent.parent / "db" / ".current_conversation"


def get_conn():
    if not DB_PATH.exists():
        print("DB not found. Run scripts/init-db.py first.", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_current_conversation_id():
    if not CONV_FILE.exists():
        return None
    val = CONV_FILE.read_text().strip()
    return int(val) if val.isdigit() else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Path to the artifact file")
    parser.add_argument("--description", default="")
    parser.add_argument("--message-id", type=int, default=None)
    args = parser.parse_args()

    conv_id = get_current_conversation_id()
    if not conv_id:
        print("No active conversation. Log a message first.", file=sys.stderr)
        sys.exit(1)

    conn = get_conn()
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur = conn.execute(
            """INSERT INTO artifacts (conversation_id, message_id, path, description, created_at)
               VALUES (?,?,?,?,?)""",
            (conv_id, args.message_id, args.path, args.description or None, ts)
        )
        artifact_id = cur.lastrowid
        conn.commit()
        print(artifact_id)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
