# /setup — First-Time ClarionBot Onboarding

You are helping the user personalize their ClarionBot installation. Walk through the following steps in order. Be conversational but efficient.

## Step 1: Run setup.py

Run the Python setup script to initialize the database and print the hook config:

```bash
python3 ~/dev/clarionbot/scripts/setup.py
```

Show the user the output, particularly the hook JSON block they need to add to `~/.claude/settings.json`.

## Step 2: Collect Personalization Info

Ask the user for the following, one at a time (or all at once if they want to go fast):

1. **Your name** — Used throughout CLAUDE.md to refer to you (replaces "the owner")
2. **Your expose domain** — The domain you use with the `expose` CLI for tunneling (e.g. `example.com`). Used in the expose section of CLAUDE.md.
3. **Your dev directory** — Where your projects live (default: `~/dev`). Used in path references.
4. **Your GitHub username** — Used in CLAUDE.md context (optional).
5. **Ollama model preference** — Model to use for conversation summarization (default: `qwen2.5:3b`). Written to `config.env`.

You can skip any item the user doesn't want to set.

## Step 3: Apply Changes

After collecting answers, make the following edits:

### CLAUDE.md (`~/dev/clarionbot/CLAUDE.md`)

Read the file first, then:

- Replace every occurrence of `the owner` with the user's name (if provided)
- Replace `<YOUR_DOMAIN>` with the user's expose domain (if provided) — there are 2 occurrences in the expose section
- Replace `~/dev/clarionbot` path references with the actual path if their dev dir is not `~/dev`
- Replace `<YOUR_GITHUB_USERNAME>` with the user's GitHub username (if provided)
- In the "About the Owner" section at the bottom, add a line like: `The owner is <NAME>. Projects live at github.com/<USERNAME>.`

### `config.env` (`~/dev/clarionbot/config.env`)

Read the file first, then update:

- `CLARIONBOT_OWNER` → user's name
- `CLARIONBOT_DOMAIN` → user's expose domain
- `CLARIONBOT_DEV_DIR` → user's dev directory
- `OLLAMA_MODEL` → user's model preference

Only edit lines for values the user actually provided.

## Step 4: Confirm

After making the edits, show the user a summary of what was changed:

- Which CLAUDE.md lines were updated
- Which config.env values were set

Then remind them of the remaining manual steps:
1. Add the hook JSON to `~/.claude/settings.json`
2. Set up the Telegram plugin with their bot token

## Notes

- Be surgical with edits — use exact string replacement, don't rewrite whole sections
- If a value is already set (not the placeholder), ask the user if they want to update it
- Don't commit changes — let the user review first and commit manually
