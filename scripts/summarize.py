#!/usr/bin/env python3
"""
Generate and store 1-2 sentence summaries for conversations using a local Ollama model.

Usage:
    summarize.py                  # summarize all conversations without a summary
    summarize.py --conv <id>      # summarize a specific conversation
    summarize.py --all            # re-summarize all conversations (overwrite existing)
    summarize.py --model <name>   # override model (default: qwen2.5:3b)

Summaries are stored in the conversations.summary column and used by context.py
for faster, more meaningful retrieval.
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
import urllib.error
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")

SYSTEM_PROMPT = (
    "You are a conversation summarizer. Given a chat log, write exactly 1-2 sentences "
    "summarizing what was discussed and any key decisions or outcomes. "
    "Be specific and factual. No preamble, no 'This conversation...', just the summary."
)


def get_conn():
    if not DB_PATH.exists():
        print("DB not found. Run scripts/init-db.py first.", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def call_ollama(model: str, prompt: str) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 120},
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get("response", "").strip()
    except urllib.error.URLError as e:
        print(f"Ollama error: {e}", file=sys.stderr)
        sys.exit(1)


def build_prompt(messages: list) -> str:
    lines = [SYSTEM_PROMPT, "", "Chat log:"]
    # Use up to 30 messages to stay within context
    for msg in messages[-30:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"][:400]
        if len(msg["content"]) > 400:
            content += "…"
        lines.append(f"{role}: {content}")
    lines.append("\nSummary:")
    return "\n".join(lines)


def summarize_conversation(conn, conv_id: int, model: str, overwrite: bool = False) -> bool:
    conv = conn.execute(
        "SELECT id, started_at, title, summary FROM conversations WHERE id=?",
        (conv_id,)
    ).fetchone()

    if not conv:
        print(f"Conversation {conv_id} not found.", file=sys.stderr)
        return False

    if conv["summary"] and not overwrite:
        print(f"Conversation {conv_id}: already has summary, skipping (use --all to overwrite)")
        return False

    messages = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY ts ASC",
        (conv_id,)
    ).fetchall()

    if len(messages) < 2:
        print(f"Conversation {conv_id}: too short to summarize, skipping")
        return False

    print(f"Summarizing conversation {conv_id} ({len(messages)} messages)...", end=" ", flush=True)
    prompt = build_prompt(list(messages))
    summary = call_ollama(model, prompt)

    if not summary:
        print("empty response, skipping")
        return False

    conn.execute(
        "UPDATE conversations SET summary=? WHERE id=?",
        (summary, conv_id)
    )
    conn.commit()
    print(f"done.\n  → {summary}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conv", type=int, help="Summarize a specific conversation ID")
    parser.add_argument("--all", action="store_true", help="Re-summarize all (overwrite existing)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    conn = get_conn()
    try:
        if args.conv:
            summarize_conversation(conn, args.conv, args.model, overwrite=True)
        elif args.all:
            convs = conn.execute("SELECT id FROM conversations ORDER BY id ASC").fetchall()
            count = 0
            for row in convs:
                if summarize_conversation(conn, row["id"], args.model, overwrite=True):
                    count += 1
            print(f"\nSummarized {count} conversation(s).")
        else:
            # Default: summarize only conversations without a summary
            convs = conn.execute(
                "SELECT id FROM conversations WHERE summary IS NULL OR summary='' ORDER BY id ASC"
            ).fetchall()
            if not convs:
                print("All conversations already have summaries. Use --all to regenerate.")
                return
            count = 0
            for row in convs:
                if summarize_conversation(conn, row["id"], args.model, overwrite=False):
                    count += 1
            print(f"\nSummarized {count} new conversation(s).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
