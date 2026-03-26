# ClarionBot

ClarionBot is a persistent Telegram assistant powered by Claude Code. It runs on your local machine, receives Telegram messages as [Claude Code channel](https://code.claude.com/docs/en/channels#supported-channels) events, responds via the Telegram channel, and automatically logs every exchange to a local SQLite database — giving Claude persistent memory across sessions.

## Prerequisites

- [Claude Code](https://github.com/anthropics/claude-code) installed and authenticated
- [Ollama](https://ollama.ai) running locally with `qwen2.5:3b` pulled (`ollama pull qwen2.5:3b`)
- A Telegram bot token (create one via [@BotFather](https://t.me/botfather))
- Python 3.9+

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/clarionbot ~/dev/clarionbot
cd ~/dev/clarionbot
```

### 2. Configure

```bash
cp config.env.example config.env
```

Edit `config.env` and fill in your values:

```
CLARIONBOT_OWNER=YourName
CLARIONBOT_DOMAIN=yourdomain.com   # for expose tunneling
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=qwen2.5:3b
```

### 3. Run the setup script

```bash
python3 scripts/setup.py
```

This will:
- Initialize the SQLite database
- Print the exact hook configuration block you need to add to `~/.claude/settings.json`

### 4. Add hooks to `~/.claude/settings.json`

Copy the JSON block printed by `setup.py` and merge it into your `~/.claude/settings.json`. It registers three hooks:

| Hook | Script | Purpose |
|------|--------|---------|
| `UserPromptSubmit` | `hook-incoming.py` | Logs every incoming Telegram message |
| `PostToolUse` (reply) | `hook-reply.py` | Logs every assistant reply |
| `Stop` | `hook-stop.py` | Summarizes the conversation via Ollama |

### 5. Configure the Telegram plugin

Set up the Telegram channel in Claude Code and connect your bot token. See the [Claude Code channels docs](https://code.claude.com/docs/en/channels#supported-channels) for setup instructions, then run `/telegram:configure` inside a Claude Code session to connect your bot token.

### 6. Start a Claude Code session

```bash
cd ~/dev/clarionbot
claude
```

Claude will read `CLAUDE.md` at session start and know how to handle incoming messages.

### 7. (Optional) Run `/setup` for interactive onboarding

Inside a Claude Code session, run:

```
/setup
```

This slash command walks you through personalizing `CLAUDE.md` and `config.env` — replacing placeholder values with your name, domain, GitHub username, and Ollama model preference.

---

## How It Works

1. A Telegram message arrives as a Claude Code channel event via the [Telegram channel](https://code.claude.com/docs/en/channels#supported-channels)
2. `hook-incoming.py` fires and logs the message to SQLite
3. Claude reads recent history to restore context, then responds using the Telegram reply tool
4. `hook-reply.py` fires and logs the reply to SQLite
5. When Claude stops responding, `hook-stop.py` calls Ollama to summarize the conversation and extract any decisions or open questions into the database

The database gives Claude a persistent memory across sessions. Scripts like `context.py` and `recent.py` let Claude retrieve relevant history at the start of each new session.

---

## Directory Structure

```
clarionbot/
├── CLAUDE.md              ← self-instructions for Claude (customize this)
├── config.env.example     ← configuration template
├── scripts/
│   ├── setup.py           ← first-run setup
│   ├── init-db.py         ← initialize the SQLite database
│   ├── log.py             ← log a message (user or assistant)
│   ├── recent.py          ← show recent conversations
│   ├── search.py          ← full-text search across all history
│   ├── context.py         ← retrieve history for a topic/project
│   ├── artifact.py        ← register a file as an artifact
│   ├── tag.py             ← tag current conversation with a topic
│   ├── project.py         ← project CRUD
│   ├── thread.py          ← thread CRUD (sub-topics per project)
│   ├── decide.py          ← record decisions
│   ├── loop.py            ← open loop tracking
│   ├── summarize.py       ← generate summaries via Ollama
│   ├── hook-incoming.py   ← UserPromptSubmit hook
│   ├── hook-reply.py      ← PostToolUse hook
│   └── hook-stop.py       ← Stop hook
├── .claude/
│   ├── agents/
│   │   └── project-worker.md  ← sub-agent for project dispatch
│   └── commands/
│       └── setup.md           ← /setup slash command
├── db/
│   ├── messages.db        ← SQLite database (gitignored)
│   └── .current_conversation  ← session state (gitignored)
└── artifacts/             ← files created during conversations
```

---

## Customization

The core of ClarionBot is `CLAUDE.md` — Claude reads it at the start of every session. It controls:

- How Claude orients itself (reading recent history, checking project context)
- How sub-agents are dispatched for longer tasks
- How artifacts and decisions are recorded
- Personal context about the owner

After running `/setup`, edit `CLAUDE.md` freely to add your own preferences, projects, and instructions. The more context you give Claude, the more useful it becomes.

### Changing the Ollama model

Update `OLLAMA_MODEL` in `config.env`. Any model available in your local Ollama instance works. `qwen2.5:3b` is a good default — fast and small enough to summarize conversations without blocking.

---

## Scripts Reference

| Script | Usage |
|--------|-------|
| `recent.py` | `python3 scripts/recent.py --conversations 5` |
| `search.py` | `python3 scripts/search.py "query"` |
| `context.py` | `python3 scripts/context.py <topic>` |
| `tag.py` | `python3 scripts/tag.py <topic> [topic2 ...]` |
| `artifact.py` | `python3 scripts/artifact.py /path/to/file --description "..."` |
| `project.py` | `python3 scripts/project.py show <name>` |
| `decide.py` | `python3 scripts/decide.py "<decision>" --project <name>` |
| `loop.py` | `python3 scripts/loop.py open "<question>" --project <name>` |
| `log.py` | `python3 scripts/log.py user "message"` (manual backfill only) |
