#!/usr/bin/env python3
"""
Log a message to the ClarionBot database.

Usage:
    log.py <role> <content> [--new-session] [--title "..."] [--ts "2026-..."]

role: user | assistant
Prints the message_id on success.

Conversation detection:
- Reuses the current conversation if last message was < 2 hours ago.
- Forces a new conversation if --new-session is passed or content starts with
  "New session" (case-insensitive).
- Title for new conversation: use --title, or text after "New session: ".
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"
CONV_FILE = Path(__file__).parent.parent / "db" / ".current_conversation"
IDLE_SECONDS = 7200  # 2 hours


def get_conn():
    if not DB_PATH.exists():
        print("DB not found. Run scripts/init-db.py first.", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(ts_str):
    return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def get_or_create_conversation(conn, force_new, title, ts):
    if not force_new and CONV_FILE.exists():
        stored_id = CONV_FILE.read_text().strip()
        if stored_id.isdigit():
            row = conn.execute(
                "SELECT id, last_message_at FROM conversations WHERE id=?",
                (int(stored_id),)
            ).fetchone()
            if row:
                last = parse_iso(row["last_message_at"])
                now = datetime.now(timezone.utc)
                if (now - last).total_seconds() < IDLE_SECONDS:
                    return int(row["id"])

    # Create new conversation
    cur = conn.execute(
        "INSERT INTO conversations (started_at, last_message_at, title) VALUES (?,?,?)",
        (ts, ts, title or None)
    )
    conv_id = cur.lastrowid
    CONV_FILE.write_text(str(conv_id))
    return conv_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=["user", "assistant"])
    parser.add_argument("content")
    parser.add_argument("--new-session", action="store_true")
    parser.add_argument("--title", default="")
    parser.add_argument("--ts", default="")
    args = parser.parse_args()

    content = args.content
    force_new = args.new_session
    title = args.title
    ts = args.ts or now_iso()

    # Detect "New session" trigger in content
    lower = content.strip().lower()
    if lower.startswith("new session"):
        force_new = True
        after_colon = content.split(":", 1)
        if len(after_colon) > 1 and not title:
            title = after_colon[1].strip()

    conn = get_conn()
    try:
        conv_id = get_or_create_conversation(conn, force_new, title, ts)

        cur = conn.execute(
            "INSERT INTO messages (conversation_id, ts, role, content) VALUES (?,?,?,?)",
            (conv_id, ts, args.role, content)
        )
        msg_id = cur.lastrowid

        conn.execute(
            "UPDATE conversations SET last_message_at=? WHERE id=?",
            (ts, conv_id)
        )
        conn.commit()
        print(msg_id)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
