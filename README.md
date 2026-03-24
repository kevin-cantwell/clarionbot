# ClarionBot

A persistent Telegram assistant running on a local Mac mini, powered by Claude via Claude Code. Maintains a searchable conversation history across sessions using SQLite.

## How it works

Telegram messages arrive as channel events via the [Claude Code Telegram plugin](https://github.com/anthropics/claude-code). Claude Code responds using the `mcp__plugin_telegram_telegram__reply` tool. Two hooks handle logging automatically:

- **`UserPromptSubmit`** → `scripts/hook-incoming.py` — logs every incoming Telegram message to SQLite
- **`PostToolUse` (reply tool)** → `scripts/hook-reply.py` — logs every assistant reply to SQLite

The database gives Claude persistent memory across sessions. At the start of each session, Claude reads recent history to restore context.

## Directory structure

```
clarionbot/
├── CLAUDE.md              ← self-instructions for Claude
├── scripts/
│   ├── init-db.py         ← initialize the SQLite database
│   ├── log.py             ← log a message (user or assistant)
│   ├── recent.py          ← show recent conversations
│   ├── search.py          ← full-text search across all history
│   ├── context.py         ← retrieve history for a topic/project
│   ├── artifact.py        ← register a file as an artifact
│   ├── tag.py             ← tag current conversation with a topic
│   ├── hook-incoming.py   ← UserPromptSubmit hook
│   └── hook-reply.py      ← PostToolUse hook
├── db/
│   ├── messages.db        ← SQLite database (gitignored)
│   └── .current_conversation ← current conversation id (gitignored)
└── artifacts/             ← files created during conversations (gitignored)
```

## Setup

**1. Initialize the database**
```bash
python3 scripts/init-db.py
```

**2. Configure hooks in `~/.claude/settings.json`**
```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [{
          "type": "command",
          "command": "python3 /path/to/clarionbot/scripts/hook-incoming.py"
        }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "mcp__plugin_telegram_telegram__reply",
        "hooks": [{
          "type": "command",
          "command": "python3 /path/to/clarionbot/scripts/hook-reply.py"
        }]
      }
    ]
  }
}
```

**3. Set up the Telegram plugin**

Follow the [Claude Code Telegram plugin docs](https://github.com/anthropics/claude-code) to configure your bot token.

## Scripts

| Script | Usage |
|--------|-------|
| `recent.py` | `python3 scripts/recent.py --conversations 5` |
| `search.py` | `python3 scripts/search.py "query"` |
| `context.py` | `python3 scripts/context.py <topic>` |
| `tag.py` | `python3 scripts/tag.py <topic> [topic2 ...]` |
| `artifact.py` | `python3 scripts/artifact.py /path/to/file --description "..."` |
| `log.py` | `python3 scripts/log.py user "message" [--ts "ISO8601"]` |
