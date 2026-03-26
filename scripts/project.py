#!/usr/bin/env python3
"""
Project CRUD for ClarionBot.

Usage:
    project.py create <name> --goal "..."
    project.py update <name> [--status active|paused|archived] [--goal "..."]
                             [--add-risk "..."] [--rm-risk "..."]
                             [--add-action "..."] [--rm-action "..."]
    project.py list [--status active]
    project.py show <name>      full brief: goal, status, threads, decisions, open loops
    project.py touch <name>     update last_touched_at to now
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"


def get_conn():
    if not DB_PATH.exists():
        print("DB not found. Run scripts/init-db.py first.", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_project(conn, name: str):
    return conn.execute(
        "SELECT * FROM projects WHERE lower(name)=lower(?)", (name,)
    ).fetchone()


def require_project(conn, name: str):
    p = get_project(conn, name)
    if not p:
        print(f"Project not found: {name}", file=sys.stderr)
        sys.exit(1)
    return p


def cmd_create(conn, args):
    existing = get_project(conn, args.name)
    if existing:
        print(f"Project already exists: {args.name}")
        return
    conn.execute(
        "INSERT INTO projects (name, goal, status, risks, next_actions, last_touched_at) "
        "VALUES (?, ?, 'active', '[]', '[]', ?)",
        (args.name.lower(), args.goal or "", now_iso())
    )
    conn.commit()
    print(f"Created project: {args.name}")


def cmd_update(conn, args):
    p = require_project(conn, args.name)
    pid = p["id"]

    updates = {}
    if args.status:
        updates["status"] = args.status
    if args.goal:
        updates["goal"] = args.goal
    updates["last_touched_at"] = now_iso()

    if updates:
        clauses = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE projects SET {clauses} WHERE id=?",
            list(updates.values()) + [pid]
        )

    # JSON list updates
    for field, add_val, rm_val in [
        ("risks",        args.add_risk,   args.rm_risk),
        ("next_actions", args.add_action, args.rm_action),
    ]:
        if add_val or rm_val:
            current = json.loads(p[field] or "[]")
            if add_val and add_val not in current:
                current.append(add_val)
            if rm_val and rm_val in current:
                current.remove(rm_val)
            conn.execute(
                f"UPDATE projects SET {field}=? WHERE id=?",
                (json.dumps(current), pid)
            )

    conn.commit()
    print(f"Updated project: {args.name}")


def cmd_list(conn, args):
    if args.status:
        rows = conn.execute(
            "SELECT name, status, goal, last_touched_at FROM projects WHERE lower(status)=lower(?)"
            " ORDER BY last_touched_at DESC",
            (args.status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT name, status, goal, last_touched_at FROM projects ORDER BY last_touched_at DESC"
        ).fetchall()

    if not rows:
        print("No projects found.")
        return
    for r in rows:
        last = r["last_touched_at"] or "never"
        goal_short = (r["goal"] or "")[:60]
        print(f"[{r['status']}] {r['name']}  —  {goal_short}  (last: {last})")


def cmd_show(conn, args):
    p = require_project(conn, args.name)
    pid = p["id"]

    print(f"=== Project: {p['name']} ===")
    print(f"Status:       {p['status']}")
    print(f"Goal:         {p['goal'] or '(none)'}")
    print(f"Last touched: {p['last_touched_at'] or 'never'}")

    risks = json.loads(p["risks"] or "[]")
    if risks:
        print("\nRisks:")
        for r in risks:
            print(f"  - {r}")

    actions = json.loads(p["next_actions"] or "[]")
    if actions:
        print("\nNext Actions:")
        for a in actions:
            print(f"  - {a}")

    threads = conn.execute(
        "SELECT id, title, status, last_touched_at FROM threads"
        " WHERE project_id=? ORDER BY status ASC, last_touched_at DESC",
        (pid,)
    ).fetchall()
    if threads:
        print("\nThreads:")
        for t in threads:
            print(f"  [{t['id']}] {t['title']} ({t['status']})")

    decisions = conn.execute(
        "SELECT id, decision_text, reason, created_at FROM decisions"
        " WHERE project_id=? AND status='active' ORDER BY created_at DESC LIMIT 10",
        (pid,)
    ).fetchall()
    if decisions:
        print("\nDecisions:")
        for d in decisions:
            reason = f" — {d['reason']}" if d["reason"] else ""
            print(f"  [{d['id']}] {d['decision_text']}{reason}  ({d['created_at'][:10]})")

    loops = conn.execute(
        "SELECT id, question, status, created_at FROM open_loops"
        " WHERE project_id=? AND status='open' ORDER BY created_at DESC",
        (pid,)
    ).fetchall()
    if loops:
        print("\nOpen Loops:")
        for l in loops:
            print(f"  [{l['id']}] {l['question']}")


def cmd_touch(conn, args):
    require_project(conn, args.name)
    conn.execute(
        "UPDATE projects SET last_touched_at=? WHERE lower(name)=lower(?)",
        (now_iso(), args.name)
    )
    conn.commit()
    print(f"Touched: {args.name}")


def main():
    parser = argparse.ArgumentParser(description="Project CRUD")
    sub = parser.add_subparsers(dest="cmd")

    p_create = sub.add_parser("create")
    p_create.add_argument("name")
    p_create.add_argument("--goal", default="")

    p_update = sub.add_parser("update")
    p_update.add_argument("name")
    p_update.add_argument("--status")
    p_update.add_argument("--goal")
    p_update.add_argument("--add-risk")
    p_update.add_argument("--rm-risk")
    p_update.add_argument("--add-action")
    p_update.add_argument("--rm-action")

    p_list = sub.add_parser("list")
    p_list.add_argument("--status", default="")

    p_show = sub.add_parser("show")
    p_show.add_argument("name")

    p_touch = sub.add_parser("touch")
    p_touch.add_argument("name")

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
        elif args.cmd == "touch":  cmd_touch(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
