#!/usr/bin/env python3
"""
Retrieve relevant message history for a topic or project.

Usage:
    context.py <topic> [--limit N] [--full]

Searches message history for the topic keyword, groups by conversation,
and prints a digest useful for orienting at the start of a session.
--full prints complete message content instead of truncating.
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
    parser.add_argument("topic", help="Topic or project name to retrieve context for")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--full", action="store_true", help="Print full message content")
    args = parser.parse_args()

    conn = get_conn()
    try:
        # Find conversations tagged with this topic
        tagged = conn.execute("""
            SELECT DISTINCT c.id, c.started_at, c.title, c.summary
            FROM conversation_topics ct
            JOIN conversations c ON ct.conversation_id = c.id
            WHERE lower(ct.topic) = lower(?)
            ORDER BY c.started_at DESC
        """, (args.topic,)).fetchall()

        # Also find conversations via FTS match
        fts = conn.execute("""
            SELECT DISTINCT c.id, c.started_at, c.title, c.summary
            FROM messages_fts f
            JOIN messages m ON f.rowid = m.id
            JOIN conversations c ON m.conversation_id = c.id
            WHERE messages_fts MATCH ?
            ORDER BY c.started_at DESC
            LIMIT ?
        """, (args.topic, args.limit)).fetchall()

        seen_ids = set()
        conversations = []
        for row in list(tagged) + list(fts):
            if row["id"] not in seen_ids:
                seen_ids.add(row["id"])
                conversations.append(row)

        if not conversations:
            print(f"No history found for topic: {args.topic}")
            return

        print(f"=== Context for: {args.topic} ({len(conversations)} conversations) ===\n")

        for conv in conversations:
            title = conv["title"] or "(untitled)"
            print(f"--- Conversation {conv['id']} | {conv['started_at']} | {title} ---")
            if conv["summary"]:
                print(f"Summary: {conv['summary']}")

            messages = conn.execute("""
                SELECT ts, role, content FROM messages
                WHERE conversation_id = ?
                  AND id IN (
                      SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?
                  )
                ORDER BY ts ASC
                LIMIT 20
            """, (conv["id"], args.topic)).fetchall()

            for msg in messages:
                content = msg["content"] if args.full else msg["content"][:300]
                if not args.full and len(msg["content"]) > 300:
                    content += "…"
                print(f"  [{msg['ts']}] {msg['role']}: {content}")
            print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
