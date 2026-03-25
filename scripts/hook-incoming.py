#!/usr/bin/env python3
"""
UserPromptSubmit hook: auto-log incoming Telegram messages to ClarionBot DB,
and inject relevant conversation history as context when available.

Only logs/injects for messages containing a <channel source="plugin:telegram:telegram"> tag.
Terminal and other prompts are silently ignored.

Context injection:
  - Extracts meaningful keywords from the incoming message
  - Searches FTS + topic tags for relevant prior conversations
  - If hits found, prepends a brief summary block to the prompt
  - Silently skips if DB unavailable or no hits
"""

import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

LOG_SCRIPT = Path(__file__).parent / "log.py"
DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"

CHANNEL_RE = re.compile(
    r'<channel\s[^>]*source="plugin:telegram:telegram"[^>]*>',
    re.IGNORECASE,
)
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
CONTENT_RE = re.compile(
    r'<channel\b[^>]*>(.*?)</channel>',
    re.DOTALL | re.IGNORECASE,
)

# Words to exclude when extracting keywords
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
    """Return (content, ts) from the first telegram channel tag, or None."""
    tag_match = CHANNEL_RE.search(text)
    if not tag_match:
        return None

    attrs = dict(ATTR_RE.findall(tag_match.group(0)))
    ts = attrs.get("ts", "")

    content_match = CONTENT_RE.search(text, tag_match.start())
    if not content_match:
        return None

    content = content_match.group(1).strip()
    return content, ts


def search_strings(obj, depth=0):
    """Recursively search all string values in a JSON object."""
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
    """Extract meaningful words from text, skipping stopwords and short tokens."""
    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    seen = set()
    keywords = []
    for w in words:
        if w not in STOPWORDS and w not in seen:
            seen.add(w)
            keywords.append(w)
    return keywords[:8]  # limit to top 8


def build_context_block(message: str) -> str | None:
    """
    Search history for relevant prior conversations based on message keywords.
    Returns a formatted context block string, or None if nothing relevant found.
    """
    if not DB_PATH.exists():
        return None

    keywords = extract_keywords(message)
    if not keywords:
        return None

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

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

        # Also check project/topic tags
        for kw in keywords:
            tagged = conn.execute("""
                SELECT DISTINCT c.id, c.started_at, c.title, c.summary
                FROM conversation_topics ct
                JOIN conversations c ON ct.conversation_id = c.id
                WHERE lower(ct.topic) = lower(?)
                UNION
                SELECT DISTINCT c.id, c.started_at, c.title, c.summary
                FROM projects p
                JOIN conversation_projects cp ON cp.project_id = p.id
                JOIN conversations c ON cp.conversation_id = c.id
                WHERE lower(p.name) = lower(?)
                ORDER BY started_at DESC
                LIMIT 2
            """, (kw, kw)).fetchall()
            for row in tagged:
                if row["id"] not in seen_conv_ids:
                    seen_conv_ids.add(row["id"])
                    # Fetch the most recent message snippet for context
                    last = conn.execute("""
                        SELECT role, content, ts FROM messages
                        WHERE conversation_id = ?
                        ORDER BY ts DESC LIMIT 1
                    """, (row["id"],)).fetchone()
                    if last:
                        hits.append({
                            "id": row["id"],
                            "started_at": row["started_at"],
                            "title": row["title"],
                            "summary": row["summary"],
                            "role": last["role"],
                            "content": last["content"],
                            "msg_ts": last["ts"],
                        })

        conn.close()

        if not hits:
            return None

        # Limit to 3 most relevant hits
        hits = hits[:3]

        lines = ["<clarion-context>",
                 "Relevant prior history (auto-injected based on message keywords):"]
        for h in hits:
            title = h["title"] or "(untitled)"
            lines.append(f"\n[Conversation {h['id']} | {h['started_at']} | {title}]")
            if h["summary"]:
                lines.append(f"Summary: {h['summary']}")
            snippet = h["content"][:200].replace("\n", " ")
            if len(h["content"]) > 200:
                snippet += "…"
            lines.append(f"  [{h['msg_ts']}] {h['role']}: {snippet}")
        lines.append("</clarion-context>")

        return "\n".join(lines)

    except Exception:
        return None


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)

    # Try JSON parse first; fall back to treating raw as plain text
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

    # Build and inject context block if relevant history found
    context_block = build_context_block(content)
    if context_block:
        # Write to stdout — Claude Code hook infrastructure prepends this to the prompt
        print(context_block)


if __name__ == "__main__":
    main()
