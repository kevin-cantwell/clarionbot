#!/usr/bin/env python3
"""
One-time migration to v2 schema.

Safe to run multiple times (idempotent). Upgrades the live DB in-place:
  - Adds columns to the existing `projects` table
  - Creates new tables: threads, decisions, open_loops, memory_links, schema_version
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"


def column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def main():
    if not DB_PATH.exists():
        print("DB not found. Run scripts/init-db.py first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    changes = []

    try:
        # --- projects table column upgrades ---
        projects_cols = [
            ("goal",           "TEXT"),
            ("status",         "TEXT DEFAULT 'active'"),
            ("risks",          "TEXT DEFAULT '[]'"),
            ("next_actions",   "TEXT DEFAULT '[]'"),
            ("last_touched_at","TEXT"),
        ]
        for col, typedef in projects_cols:
            if not column_exists(conn, "projects", col):
                conn.execute(f"ALTER TABLE projects ADD COLUMN {col} {typedef}")
                changes.append(f"projects.{col}")

        # --- threads ---
        if not table_exists(conn, "threads"):
            conn.execute("""
                CREATE TABLE threads (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id      INTEGER REFERENCES projects(id),
                    title           TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'active'
                                    CHECK(status IN ('active','suspended','closed')),
                    summary         TEXT,
                    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                    last_touched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                )
            """)
            changes.append("table:threads")

        # --- decisions ---
        if not table_exists(conn, "decisions"):
            conn.execute("""
                CREATE TABLE decisions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id      INTEGER REFERENCES projects(id),
                    thread_id       INTEGER REFERENCES threads(id),
                    decision_text   TEXT NOT NULL,
                    reason          TEXT,
                    supersedes_id   INTEGER REFERENCES decisions(id),
                    status          TEXT NOT NULL DEFAULT 'active'
                                    CHECK(status IN ('active','superseded','revoked')),
                    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                )
            """)
            changes.append("table:decisions")

        # --- open_loops ---
        if not table_exists(conn, "open_loops"):
            conn.execute("""
                CREATE TABLE open_loops (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id      INTEGER REFERENCES projects(id),
                    thread_id       INTEGER REFERENCES threads(id),
                    question        TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'open'
                                    CHECK(status IN ('open','resolved','stale')),
                    resolution      TEXT,
                    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                    last_touched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                )
            """)
            changes.append("table:open_loops")

        # --- memory_links ---
        if not table_exists(conn, "memory_links"):
            conn.execute("""
                CREATE TABLE memory_links (
                    source_type TEXT NOT NULL,
                    source_id   INTEGER NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id   INTEGER NOT NULL,
                    link_type   TEXT NOT NULL
                                CHECK(link_type IN (
                                    'belongs_to','continues','supersedes',
                                    'depends_on','mentions','related_to'
                                )),
                    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                    PRIMARY KEY (source_type, source_id, target_type, target_id, link_type)
                )
            """)
            changes.append("table:memory_links")

        # --- schema_version ---
        if not table_exists(conn, "schema_version"):
            conn.execute("""
                CREATE TABLE schema_version (
                    version     INTEGER PRIMARY KEY,
                    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                )
            """)
            changes.append("table:schema_version")

        # Record this migration
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (2)"
        )

        conn.commit()

        if changes:
            print(f"Migration v2 applied: {', '.join(changes)}")
        else:
            print("Migration v2: already up to date.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
