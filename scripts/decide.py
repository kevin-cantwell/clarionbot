#!/usr/bin/env python3
"""
Record a decision in ClarionBot's memory.

Usage:
    decide.py <text> [--reason "..."] [--project <name>] [--thread <id>] [--supersedes <id>]

When --supersedes is given, the old decision is marked 'superseded'.
Prints the new decision ID on success.
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"


def get_conn():
    if not DB_PATH.exists():
        print("DB not found.", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    parser = argparse.ArgumentParser(description="Record a decision")
    parser.add_argument("text", help="Decision text")
    parser.add_argument("--reason", default="")
    parser.add_argument("--project", help="Project name")
    parser.add_argument("--thread", type=int, help="Thread ID")
    parser.add_argument("--supersedes", type=int, help="Decision ID this supersedes")
    args = parser.parse_args()

    conn = get_conn()
    try:
        project_id = None
        if args.project:
            row = conn.execute(
                "SELECT id FROM projects WHERE lower(name)=lower(?)", (args.project,)
            ).fetchone()
            if not row:
                print(f"Project not found: {args.project}", file=sys.stderr)
                sys.exit(1)
            project_id = row["id"]

        if args.supersedes:
            row = conn.execute("SELECT id FROM decisions WHERE id=?", (args.supersedes,)).fetchone()
            if not row:
                print(f"Decision not found: {args.supersedes}", file=sys.stderr)
                sys.exit(1)
            conn.execute(
                "UPDATE decisions SET status='superseded' WHERE id=?", (args.supersedes,)
            )

        cur = conn.execute(
            "INSERT INTO decisions (project_id, thread_id, decision_text, reason, supersedes_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, args.thread, args.text, args.reason or None, args.supersedes)
        )
        decision_id = cur.lastrowid

        # Update project last_touched_at
        if project_id:
            conn.execute(
                "UPDATE projects SET last_touched_at=? WHERE id=?", (now_iso(), project_id)
            )

        conn.commit()
        print(decision_id)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
