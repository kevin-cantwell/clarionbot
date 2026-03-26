#!/usr/bin/env python3
"""
UserPromptSubmit hook: auto-log incoming Telegram messages to ClarionBot DB,
and inject relevant context when available.

Context injection priority:
  1. If the message references a known project → inject project brief
     (goal, status, threads, decisions, open loops) + recent conversation summaries
  2. Otherwise → fall back to FTS-based message snippets

Also writes db/.current_project when a project is detected, so hook-stop.py
can link extracted decisions/loops to the right project.
"""

import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

LOG_SCRIPT = Path(__file__).parent / "log.py"
DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"
CURRENT_PROJECT_FILE = Path(__file__).parent.parent / "db" / ".current_project"

CHANNEL_RE = re.compile(
    r'<channel\s[^>]*source="plugin:telegram:telegram"[^>]*>',
    re.IGNORECASE,
)
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
CONTENT_RE = re.compile(
    r'<channel\b[^>]*>(.*?)</channel>',
    re.DOTALL | re.IGNORECASE,
)

STOPWORDS = {
    "the", "a", "an", "is", "it", "in", "on", "at", "to", "of", "and", "or",
    "for", "with", "that", "this", "are", "was", "be", "do", "did", "can",
    "i", "you", "me", "my", "your", "we", "they", "he", "she", "it", "what",
    "how", "why", "when", "where", "which", "just", "so", "up", "out", "if",
    "but", "not", "no", "yes", "ok", "hey", "hi", "yeah", "from", "about",
    "have", "has", "had", "will", "would", "could", "should", "get", "got",
    "going", "go", "make", "let", "like", "know", "think", "see", "look",
    "first", "also", "more", "than", "then", "some", "any", "all", "there",
    "their", "its", "too", "very", "much", "well", "still", "now", "new",
    "use", "used", "using", "want", "need", "add", "one", "two", "three",
    "way", "things", "thing", "next",
}


def extract_channel(text: str):
    tag_match = CHANNEL_RE.search(text)
    if not tag_match:
        return None
    attrs = dict(ATTR_RE.findall(tag_match.group(0)))
    ts = attrs.get("ts", "")
    content_match = CONTENT_RE.search(text, tag_match.start())
    if not content_match:
        return None
    return content_match.group(1).strip(), ts


def search_strings(obj, depth=0):
    if depth > 5:
        return None
    if isinstance(obj, str):
        result = extract_channel(obj)
        if result:
            return result
    elif isinstance(obj, dict):
        for v in obj.values():
            result = search_strings(v, depth + 1)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = search_strings(item, depth + 1)
            if result:
                return result
    return None


def extract_keywords(text: str) -> list[str]:
    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    seen = set()
    keywords = []
    for w in words:
        if w not in STOPWORDS and w not in seen:
            seen.add(w)
            keywords.append(w)
    return keywords[:8]


def find_project_match(conn, keywords: list[str]):
    """Return the first project that matches any keyword, or None."""
    rows = conn.execute("SELECT id, name FROM projects WHERE status='active'").fetchall()
    for kw in keywords:
        for row in rows:
            if kw == row["name"].lower() or kw in row["name"].lower():
                return row
    return None


def build_project_context(conn, project) -> str:
    """Build a structured project brief for context injection."""
    import json as _json
    pid = project["id"]
    name = project["name"]

    lines = [f"<project name=\"{name}\">"]

    # Goal + status
    p = conn.execute(
        "SELECT goal, status, risks, next_actions, last_touched_at FROM projects WHERE id=?",
        (pid,)
    ).fetchone()
    if p["goal"]:
        lines.append(f"  <goal>{p['goal']}</goal>")
    lines.append(f"  <status>{p['status']}</status>")

    risks = _json.loads(p["risks"] or "[]")
    if risks:
        lines.append("  <risks>")
        for r in risks:
            lines.append(f"    <risk>{r}</risk>")
        lines.append("  </risks>")

    actions = _json.loads(p["next_actions"] or "[]")
    if actions:
        lines.append("  <next-actions>")
        for a in actions:
            lines.append(f"    <action>{a}</action>")
        lines.append("  </next-actions>")

    # Active threads
    threads = conn.execute(
        "SELECT id, title, status FROM threads WHERE project_id=? AND status='active'"
        " ORDER BY last_touched_at DESC LIMIT 5",
        (pid,)
    ).fetchall()
    if threads:
        lines.append("  <threads>")
        for t in threads:
            lines.append(f"    <thread id=\"{t['id']}\">{t['title']}</thread>")
        lines.append("  </threads>")

    # Recent active decisions
    decisions = conn.execute(
        "SELECT id, decision_text, reason FROM decisions"
        " WHERE project_id=? AND status='active' ORDER BY created_at DESC LIMIT 5",
        (pid,)
    ).fetchall()
    if decisions:
        lines.append("  <decisions>")
        for d in decisions:
            reason = f" ({d['reason']})" if d["reason"] else ""
            lines.append(f"    <decision id=\"{d['id']}\">{d['decision_text']}{reason}</decision>")
        lines.append("  </decisions>")

    # Open loops
    loops = conn.execute(
        "SELECT id, question FROM open_loops WHERE project_id=? AND status='open'"
        " ORDER BY created_at DESC LIMIT 5",
        (pid,)
    ).fetchall()
    if loops:
        lines.append("  <open-loops>")
        for l in loops:
            lines.append(f"    <loop id=\"{l['id']}\">{l['question']}</loop>")
        lines.append("  </open-loops>")

    # Recent conversation summaries for this project
    convs = conn.execute("""
        SELECT c.id, c.started_at, c.summary FROM conversations c
        JOIN conversation_projects cp ON cp.conversation_id = c.id
        WHERE cp.project_id = ?
        ORDER BY c.started_at DESC LIMIT 3
    """, (pid,)).fetchall()
    if convs:
        lines.append("  <recent-conversations>")
        for c in convs:
            summary = c["summary"] or "(no summary)"
            lines.append(f"    <conversation id=\"{c['id']}\" date=\"{c['started_at'][:10]}\">{summary}</conversation>")
        lines.append("  </recent-conversations>")

    lines.append("</project>")
    return "\n".join(lines)


def build_fts_context(conn, keywords: list[str]) -> str | None:
    """Fallback: FTS-based message snippet context."""
    hits = []
    seen_conv_ids = set()

    for kw in keywords:
        try:
            rows = conn.execute("""
                SELECT DISTINCT c.id, c.started_at, c.title, c.summary,
                       m.role, m.content, m.ts as msg_ts
                FROM messages_fts f
                JOIN messages m ON f.rowid = m.id
                JOIN conversations c ON m.conversation_id = c.id
                WHERE messages_fts MATCH ?
                ORDER BY c.started_at DESC
                LIMIT 3
            """, (kw,)).fetchall()
        except sqlite3.OperationalError:
            continue
        for row in rows:
            if row["id"] not in seen_conv_ids:
                seen_conv_ids.add(row["id"])
                hits.append(row)

    if not hits:
        return None

    hits = hits[:3]
    lines = ["<recent-history>",
             "Relevant prior history (based on message keywords):"]
    for h in hits:
        title = h["title"] or "(untitled)"
        lines.append(f"\n[Conversation {h['id']} | {h['started_at']} | {title}]")
        if h["summary"]:
            lines.append(f"Summary: {h['summary']}")
        snippet = h["content"][:200].replace("\n", " ")
        if len(h["content"]) > 200:
            snippet += "…"
        lines.append(f"  [{h['msg_ts']}] {h['role']}: {snippet}")
    lines.append("</recent-history>")
    return "\n".join(lines)


def build_context_block(message: str) -> str | None:
    if not DB_PATH.exists():
        return None

    keywords = extract_keywords(message)
    if not keywords:
        return None

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        project = find_project_match(conn, keywords)

        if project:
            # Write current project for hook-stop.py
            try:
                CURRENT_PROJECT_FILE.write_text(project["name"])
            except Exception:
                pass

            project_block = build_project_context(conn, project)
            fts_block = build_fts_context(conn, keywords)

            parts = ["<clarion-context>", project_block]
            if fts_block:
                parts.append(fts_block)
            parts.append("</clarion-context>")
            return "\n".join(parts)

        else:
            # Clear current project state
            try:
                if CURRENT_PROJECT_FILE.exists():
                    CURRENT_PROJECT_FILE.unlink()
            except Exception:
                pass

            fts_block = build_fts_context(conn, keywords)
            if not fts_block:
                return None
            return f"<clarion-context>\n{fts_block}\n</clarion-context>"

    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)

    try:
        payload = json.loads(raw)
        result = search_strings(payload)
    except json.JSONDecodeError:
        result = extract_channel(raw)

    if not result:
        sys.exit(0)

    content, ts = result
    if not content:
        sys.exit(0)

    # Log the incoming message
    cmd = ["python3", str(LOG_SCRIPT), "user", content]
    if ts:
        cmd += ["--ts", ts]
    subprocess.run(cmd, check=False, capture_output=True)

    # Build and inject context block
    context_block = build_context_block(content)
    if context_block:
        print(context_block)


if __name__ == "__main__":
    main()
