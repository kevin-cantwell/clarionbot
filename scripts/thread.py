#!/usr/bin/env python3
"""
Thread CRUD for ClarionBot.

Threads are sub-project discussion topics. Each belongs to a project (optional).

Usage:
    thread.py create <title> [--project <name>] [--summary "..."]
    thread.py update <id> [--status active|suspended|closed] [--summary "..."] [--title "..."]
    thread.py list [--project <name>] [--status active]
    thread.py show <id>
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
        print("DB not found.", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_project_id(conn, name: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM projects WHERE lower(name)=lower(?)", (name,)
    ).fetchone()
    return row["id"] if row else None


def cmd_create(conn, args):
    project_id = None
    if args.project:
        project_id = get_project_id(conn, args.project)
        if project_id is None:
            print(f"Project not found: {args.project}", file=sys.stderr)
            sys.exit(1)

    cur = conn.execute(
        "INSERT INTO threads (project_id, title, status, summary) VALUES (?,?,?,?)",
        (project_id, args.title, "active", args.summary or None)
    )
    thread_id = cur.lastrowid

    # Link to current conversation if available
    if CONV_FILE.exists():
        val = CONV_FILE.read_text().strip()
        if val.isdigit():
            conn.execute(
                "INSERT OR IGNORE INTO memory_links "
                "(source_type, source_id, target_type, target_id, link_type) "
                "VALUES ('conversation', ?, 'thread', ?, 'belongs_to')",
                (int(val), thread_id)
            )

    conn.commit()
    print(f"Created thread [{thread_id}]: {args.title}")


def cmd_update(conn, args):
    row = conn.execute(
        "SELECT id FROM threads WHERE id=?", (args.id,)
    ).fetchone()
    if not row:
        print(f"Thread not found: {args.id}", file=sys.stderr)
        sys.exit(1)

    updates = {"last_touched_at": now_iso()}
    if args.status:
        updates["status"] = args.status
    if args.summary:
        updates["summary"] = args.summary
    if args.title:
        updates["title"] = args.title

    clauses = ", ".join(f"{k}=?" for k in updates)
    conn.execute(
        f"UPDATE threads SET {clauses} WHERE id=?",
        list(updates.values()) + [args.id]
    )
    conn.commit()
    print(f"Updated thread [{args.id}]")


def cmd_list(conn, args):
    query = "SELECT t.id, t.title, t.status, t.last_touched_at, p.name AS project FROM threads t LEFT JOIN projects p ON t.project_id=p.id"
    params = []
    conditions = []

    if args.project:
        project_id = get_project_id(conn, args.project)
        if project_id is None:
            print(f"Project not found: {args.project}", file=sys.stderr)
            sys.exit(1)
        conditions.append("t.project_id=?")
        params.append(project_id)

    if args.status:
        conditions.append("lower(t.status)=lower(?)")
        params.append(args.status)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY t.last_touched_at DESC"

    rows = conn.execute(query, params).fetchall()
    if not rows:
        print("No threads found.")
        return
    for r in rows:
        proj = f" [{r['project']}]" if r["project"] else ""
        last = r["last_touched_at"] or "never"
        print(f"  [{r['id']}] {r['title']} ({r['status']}){proj}  last: {last}")


def cmd_show(conn, args):
    row = conn.execute(
        "SELECT t.*, p.name AS project FROM threads t LEFT JOIN projects p ON t.project_id=p.id WHERE t.id=?",
        (args.id,)
    ).fetchone()
    if not row:
        print(f"Thread not found: {args.id}", file=sys.stderr)
        sys.exit(1)

    print(f"=== Thread [{row['id']}]: {row['title']} ===")
    print(f"Status:  {row['status']}")
    if row["project"]:
        print(f"Project: {row['project']}")
    if row["summary"]:
        print(f"Summary: {row['summary']}")

    decisions = conn.execute(
        "SELECT id, decision_text, reason, created_at FROM decisions"
        " WHERE thread_id=? AND status='active' ORDER BY created_at DESC",
        (args.id,)
    ).fetchall()
    if decisions:
        print("\nDecisions:")
        for d in decisions:
            reason = f" — {d['reason']}" if d["reason"] else ""
            print(f"  [{d['id']}] {d['decision_text']}{reason}")

    loops = conn.execute(
        "SELECT id, question, status FROM open_loops"
        " WHERE thread_id=? AND status='open' ORDER BY created_at DESC",
        (args.id,)
    ).fetchall()
    if loops:
        print("\nOpen Loops:")
        for l in loops:
            print(f"  [{l['id']}] {l['question']}")


def main():
    parser = argparse.ArgumentParser(description="Thread CRUD")
    sub = parser.add_subparsers(dest="cmd")

    p_create = sub.add_parser("create")
    p_create.add_argument("title")
    p_create.add_argument("--project")
    p_create.add_argument("--summary")

    p_update = sub.add_parser("update")
    p_update.add_argument("id", type=int)
    p_update.add_argument("--status")
    p_update.add_argument("--summary")
    p_update.add_argument("--title")

    p_list = sub.add_parser("list")
    p_list.add_argument("--project")
    p_list.add_argument("--status", default="")

    p_show = sub.add_parser("show")
    p_show.add_argument("id", type=int)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    conn = get_conn()
    try:
        if args.cmd == "create":   cmd_create(conn, args)
        elif args.cmd == "update": cmd_update(conn, args)
        elif args.cmd == "list":   cmd_list(conn, args)
        elif args.cmd == "show":   cmd_show(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
