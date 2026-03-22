#!/usr/bin/env python3
"""
Show recent conversation history.

Usage:
    recent.py [--conversations N] [--messages-per N] [--full]

Prints the last N conversations with their most recent messages.
Useful for orienting at the start of a session.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"


def get_conn():
    if not DB_PATH.exists():
        print("DB not found. Run scripts/init-db.py first.", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conversations", type=int, default=3,
                        help="Number of recent conversations to show")
    parser.add_argument("--messages-per", type=int, default=10,
                        help="Max messages to show per conversation")
    parser.add_argument("--full", action="store_true",
                        help="Print full message content")
    args = parser.parse_args()

    conn = get_conn()
    try:
        convs = conn.execute("""
            SELECT id, started_at, last_message_at, title, summary
            FROM conversations
            ORDER BY last_message_at DESC
            LIMIT ?
        """, (args.conversations,)).fetchall()

        if not convs:
            print("No conversations yet.")
            return

        for conv in convs:
            title = conv["title"] or "(untitled)"
            print(f"=== Conversation {conv['id']} | {conv['started_at']} → {conv['last_message_at']} | {title} ===")
            if conv["summary"]:
                print(f"Summary: {conv['summary']}")

            # Topics
            topics = conn.execute(
                "SELECT topic FROM conversation_topics WHERE conversation_id=?",
                (conv["id"],)
            ).fetchall()
            if topics:
                print(f"Topics: {', '.join(t['topic'] for t in topics)}")

            messages = conn.execute("""
                SELECT ts, role, content FROM messages
                WHERE conversation_id=?
                ORDER BY ts ASC
                LIMIT ?
            """, (conv["id"], args.messages_per)).fetchall()

            for msg in messages:
                content = msg["content"] if args.full else msg["content"][:200]
                if not args.full and len(msg["content"]) > 200:
                    content += "…"
                print(f"  [{msg['ts']}] {msg['role']}: {content}")
            print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
