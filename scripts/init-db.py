#!/usr/bin/env python3
"""Initialize the ClarionBot message database (v2 schema)."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"


def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            last_message_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            title           TEXT,
            summary         TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            ts              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            role            TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content         TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            content,
            content='messages',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
        END;

        CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
            INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
        END;

        CREATE TABLE IF NOT EXISTS artifacts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER REFERENCES conversations(id),
            message_id      INTEGER REFERENCES messages(id),
            path            TEXT NOT NULL,
            description     TEXT,
            created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        );

        CREATE TABLE IF NOT EXISTS conversation_topics (
            conversation_id INTEGER REFERENCES conversations(id),
            topic           TEXT NOT NULL,
            PRIMARY KEY (conversation_id, topic)
        );

        CREATE TABLE IF NOT EXISTS projects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
            goal            TEXT,
            status          TEXT DEFAULT 'active',
            risks           TEXT DEFAULT '[]',
            next_actions    TEXT DEFAULT '[]',
            last_touched_at TEXT
        );

        CREATE TABLE IF NOT EXISTS conversation_projects (
            conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            project_id      INTEGER NOT NULL REFERENCES projects(id),
            PRIMARY KEY (conversation_id, project_id)
        );

        CREATE TABLE IF NOT EXISTS threads (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      INTEGER REFERENCES projects(id),
            title           TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'active'
                            CHECK(status IN ('active','suspended','closed')),
            summary         TEXT,
            created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            last_touched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      INTEGER REFERENCES projects(id),
            thread_id       INTEGER REFERENCES threads(id),
            decision_text   TEXT NOT NULL,
            reason          TEXT,
            supersedes_id   INTEGER REFERENCES decisions(id),
            status          TEXT NOT NULL DEFAULT 'active'
                            CHECK(status IN ('active','superseded','revoked')),
            created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        );

        CREATE TABLE IF NOT EXISTS open_loops (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      INTEGER REFERENCES projects(id),
            thread_id       INTEGER REFERENCES threads(id),
            question        TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'open'
                            CHECK(status IN ('open','resolved','stale')),
            resolution      TEXT,
            created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            last_touched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        );

        CREATE TABLE IF NOT EXISTS memory_links (
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
        );

        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        );

        INSERT OR IGNORE INTO schema_version (version) VALUES (2);
    """)
    conn.commit()
    conn.close()
    print(f"DB initialized at {DB_PATH}")


if __name__ == "__main__":
    init()
