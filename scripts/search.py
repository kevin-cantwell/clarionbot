#!/usr/bin/env python3
"""
Full-text search across all ClarionBot message history.

Usage:
    search.py <query> [--limit N] [--conversation-id ID]

Prints matching messages with context (conversation id, timestamp, role).
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
    parser.add_argument("query", help="Search query (FTS5 syntax supported)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--conversation-id", type=int, default=None)
    args = parser.parse_args()

    conn = get_conn()
    try:
        if args.conversation_id:
            rows = conn.execute("""
                SELECT m.id, m.conversation_id, m.ts, m.role, m.content,
                       c.title
                FROM messages_fts f
                JOIN messages m ON f.rowid = m.id
                JOIN conversations c ON m.conversation_id = c.id
                WHERE messages_fts MATCH ? AND m.conversation_id = ?
                ORDER BY m.ts DESC
                LIMIT ?
            """, (args.query, args.conversation_id, args.limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT m.id, m.conversation_id, m.ts, m.role, m.content,
                       c.title
                FROM messages_fts f
                JOIN messages m ON f.rowid = m.id
                JOIN conversations c ON m.conversation_id = c.id
                WHERE messages_fts MATCH ?
                ORDER BY m.ts DESC
                LIMIT ?
            """, (args.query, args.limit)).fetchall()

        if not rows:
            print("No results.")
            return

        for row in rows:
            title = f" ({row['title']})" if row['title'] else ""
            print(f"[conv:{row['conversation_id']}{title}] [{row['ts']}] [{row['role']}]")
            print(row['content'][:400])
            print("---")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
