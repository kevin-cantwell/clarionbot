#!/usr/bin/env python3
"""
Tag the current conversation with a topic and/or project name.

Usage:
    tag.py <topic> [<topic2> ...]
    tag.py --project <project-name> [<topic> ...]

Topics are free-form labels; projects are named work contexts (e.g. "wileygame",
"clarionbot") that group conversations for retrieval via `context.py <project>`.
"""

import argparse
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


def get_conv_id():
    if not CONV_FILE.exists():
        print("No active conversation.", file=sys.stderr)
        sys.exit(1)
    val = CONV_FILE.read_text().strip()
    if not val.isdigit():
        print("Invalid conversation file.", file=sys.stderr)
        sys.exit(1)
    return int(val)


def main():
    parser = argparse.ArgumentParser(description="Tag the current conversation")
    parser.add_argument("topics", nargs="*", help="Topic labels")
    parser.add_argument("--project", "-p", help="Project name to link this conversation to")
    args = parser.parse_args()

    if not args.topics and not args.project:
        print("Usage: tag.py <topic> [<topic2> ...] [--project <project>]", file=sys.stderr)
        sys.exit(1)

    conv_id = get_conv_id()
    conn = get_conn()
    tagged = []
    try:
        for topic in args.topics:
            conn.execute(
                "INSERT OR IGNORE INTO conversation_topics (conversation_id, topic) VALUES (?,?)",
                (conv_id, topic.lower())
            )
            tagged.append(topic)

        if args.project:
            # Upsert the project record
            conn.execute(
                "INSERT OR IGNORE INTO projects (name) VALUES (?)",
                (args.project.lower(),)
            )
            row = conn.execute(
                "SELECT id FROM projects WHERE lower(name)=?",
                (args.project.lower(),)
            ).fetchone()
            project_id = row[0]
            conn.execute(
                "INSERT OR IGNORE INTO conversation_projects (conversation_id, project_id) VALUES (?,?)",
                (conv_id, project_id)
            )
            tagged.append(f"project:{args.project}")

        conn.commit()
        print(f"Tagged conversation {conv_id} with: {', '.join(tagged)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
