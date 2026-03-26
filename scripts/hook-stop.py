#!/usr/bin/env python3
"""
Stop hook: summarize the current conversation and extract decisions/open loops.

Fires when Claude stops responding:
1. Regenerates conversation summary via summarize.py (Ollama)
2. Extracts decisions and open questions from the conversation via Ollama
3. Stores extracted items in decisions/open_loops tables
4. Updates project last_touched_at if a current project is known
"""

import json
import os
import sqlite3
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

CONV_FILE = Path(__file__).parent.parent / "db" / ".current_conversation"
PROJECT_FILE = Path(__file__).parent.parent / "db" / ".current_project"
DB_PATH = Path(__file__).parent.parent / "db" / "messages.db"
SUMMARIZE = Path(__file__).parent / "summarize.py"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def call_ollama_json(prompt: str) -> dict | None:
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2, "num_predict": 300},
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            raw = data.get("response", "").strip()
            return json.loads(raw)
    except Exception:
        return None


def extract_decisions_and_loops(messages: list[dict]) -> dict:
    """Ask Ollama to extract decisions and open questions from the conversation."""
    if len(messages) < 3:
        return {}

    lines = []
    for m in messages[-20:]:  # last 20 messages
        role = "User" if m["role"] == "user" else "Assistant"
        content = m["content"][:300]
        lines.append(f"{role}: {content}")

    chat = "\n".join(lines)
    prompt = (
        "Extract decisions and open questions from this conversation. "
        "Return ONLY a JSON object with two arrays:\n"
        "- decisions: list of {text, reason} objects for clear decisions that were made\n"
        "- open_loops: list of {question} objects for unresolved questions or follow-ups\n"
        "Only include items that are genuinely important. Return {} if nothing significant.\n\n"
        f"Conversation:\n{chat}\n\nJSON:"
    )

    result = call_ollama_json(prompt)
    if not isinstance(result, dict):
        return {}
    return result


def store_extracted(conv_id: int, project_name: str | None, extracted: dict):
    if not DB_PATH.exists():
        return
    if not extracted:
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        project_id = None
        if project_name:
            row = conn.execute(
                "SELECT id FROM projects WHERE lower(name)=lower(?)", (project_name,)
            ).fetchone()
            if row:
                project_id = row["id"]

        ts = now_iso()

        decisions = extracted.get("decisions") or []
        for d in decisions:
            if not isinstance(d, dict):
                continue
            text = str(d.get("text", "")).strip()
            reason = str(d.get("reason", "")).strip() or None
            if text:
                conn.execute(
                    "INSERT INTO decisions (project_id, decision_text, reason) VALUES (?,?,?)",
                    (project_id, text, reason)
                )

        loops = extracted.get("open_loops") or []
        for l in loops:
            if not isinstance(l, dict):
                continue
            question = str(l.get("question", "")).strip()
            if question:
                conn.execute(
                    "INSERT INTO open_loops (project_id, question) VALUES (?,?)",
                    (project_id, question)
                )

        if project_id:
            conn.execute(
                "UPDATE projects SET last_touched_at=? WHERE id=?", (ts, project_id)
            )

        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_messages(conv_id: int) -> list[dict]:
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY ts ASC",
            (conv_id,)
        ).fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1]} for r in rows]
    except Exception:
        return []


def main():
    if not CONV_FILE.exists():
        sys.exit(0)

    val = CONV_FILE.read_text().strip()
    if not val.isdigit():
        sys.exit(0)

    conv_id = int(val)

    # Step 1: Summarize
    subprocess.run(
        ["python3", str(SUMMARIZE), "--conv", str(conv_id)],
        capture_output=True,
        timeout=45,
    )

    # Step 2: Extract decisions and open loops
    project_name = None
    if PROJECT_FILE.exists():
        project_name = PROJECT_FILE.read_text().strip() or None

    messages = get_messages(conv_id)
    if len(messages) >= 3:
        extracted = extract_decisions_and_loops(messages)
        if extracted:
            store_extracted(conv_id, project_name, extracted)


if __name__ == "__main__":
    main()
