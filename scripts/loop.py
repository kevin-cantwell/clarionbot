#!/usr/bin/env python3
"""
Open loop (unresolved question/commitment) tracking for ClarionBot.

Usage:
    loop.py open <question> [--project <name>] [--thread <id>]
    loop.py resolve <id> <resolution>
    loop.py list [--project <name>] [--status open]
    loop.py stale [--days 14]     mark loops untouched for N days as stale
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
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


def cmd_open(conn, args):
    project_id = None
    if args.project:
        row = conn.execute(
            "SELECT id FROM projects WHERE lower(name)=lower(?)", (args.project,)
        ).fetchone()
        if not row:
            print(f"Project not found: {args.project}", file=sys.stderr)
            sys.exit(1)
        project_id = row["id"]

    cur = conn.execute(
        "INSERT INTO open_loops (project_id, thread_id, question) VALUES (?,?,?)",
        (project_id, args.thread, args.question)
    )
    loop_id = cur.lastrowid

    if project_id:
        conn.execute(
            "UPDATE projects SET last_touched_at=? WHERE id=?", (now_iso(), project_id)
        )

    conn.commit()
    print(loop_id)


def cmd_resolve(conn, args):
    row = conn.execute("SELECT id FROM open_loops WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"Loop not found: {args.id}", file=sys.stderr)
        sys.exit(1)

    conn.execute(
        "UPDATE open_loops SET status='resolved', resolution=?, last_touched_at=? WHERE id=?",
        (args.resolution, now_iso(), args.id)
    )
    conn.commit()
    print(f"Resolved loop [{args.id}]")


def cmd_list(conn, args):
    query = (
        "SELECT l.id, l.question, l.status, l.created_at, p.name AS project "
        "FROM open_loops l LEFT JOIN projects p ON l.project_id=p.id"
    )
    conditions = []
    params = []

    if args.project:
        row = conn.execute(
            "SELECT id FROM projects WHERE lower(name)=lower(?)", (args.project,)
        ).fetchone()
        if not row:
            print(f"Project not found: {args.project}", file=sys.stderr)
            sys.exit(1)
        conditions.append("l.project_id=?")
        params.append(row["id"])

    status = args.status or "open"
    conditions.append("l.status=?")
    params.append(status)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY l.created_at DESC"

    rows = conn.execute(query, params).fetchall()
    if not rows:
        print(f"No {status} loops found.")
        return
    for r in rows:
        proj = f" [{r['project']}]" if r["project"] else ""
        print(f"  [{r['id']}]{proj} {r['question']}  (opened: {r['created_at'][:10]})")


def cmd_stale(conn, args):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cur = conn.execute(
        "UPDATE open_loops SET status='stale', last_touched_at=? "
        "WHERE status='open' AND last_touched_at < ?",
        (now_iso(), cutoff)
    )
    conn.commit()
    print(f"Marked {cur.rowcount} loop(s) as stale (older than {args.days} days).")


def main():
    parser = argparse.ArgumentParser(description="Open loop tracking")
    sub = parser.add_subparsers(dest="cmd")

    p_open = sub.add_parser("open")
    p_open.add_argument("question")
    p_open.add_argument("--project")
    p_open.add_argument("--thread", type=int)

    p_resolve = sub.add_parser("resolve")
    p_resolve.add_argument("id", type=int)
    p_resolve.add_argument("resolution")

    p_list = sub.add_parser("list")
    p_list.add_argument("--project")
    p_list.add_argument("--status", default="open")

    p_stale = sub.add_parser("stale")
    p_stale.add_argument("--days", type=int, default=14)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    conn = get_conn()
    try:
        if args.cmd == "open":     cmd_open(conn, args)
        elif args.cmd == "resolve": cmd_resolve(conn, args)
        elif args.cmd == "list":   cmd_list(conn, args)
        elif args.cmd == "stale":  cmd_stale(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
