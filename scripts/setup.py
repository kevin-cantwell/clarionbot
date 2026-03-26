#!/usr/bin/env python3
"""
ClarionBot first-run setup script.

1. Checks for config.env (copies from config.env.example if missing)
2. Initializes the SQLite database
3. Prints the hook configuration block for ~/.claude/settings.json
4. Prints instructions for the Telegram plugin
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"
CONFIG_ENV = ROOT / "config.env"
CONFIG_EXAMPLE = ROOT / "config.env.example"
DB_INIT = SCRIPTS / "init-db.py"


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def main():
    print("\nWelcome to ClarionBot setup!")
    print("This script will get you ready in a few steps.\n")

    # Step 1: config.env
    section("Step 1: Configuration")
    if CONFIG_ENV.exists():
        print(f"  config.env already exists at {CONFIG_ENV}")
        print("  (Edit it any time to change Ollama URL, model, etc.)")
    else:
        if not CONFIG_EXAMPLE.exists():
            print(f"  ERROR: config.env.example not found at {CONFIG_EXAMPLE}")
            print("  Make sure you cloned the full repo.")
            sys.exit(1)
        shutil.copy(CONFIG_EXAMPLE, CONFIG_ENV)
        print(f"  Created {CONFIG_ENV} from config.env.example")
        print()
        print("  ACTION REQUIRED: Open config.env and fill in your values:")
        print(f"    {CONFIG_ENV}")
        print()
        print("  Key settings:")
        print("    CLARIONBOT_OWNER   - Your name")
        print("    CLARIONBOT_DOMAIN  - Your expose tunnel domain")
        print("    OLLAMA_MODEL       - Local model for summarization")
        print()
        print("  Press Enter when you've filled in config.env, or Ctrl+C to exit.")
        try:
            input("  > ")
        except KeyboardInterrupt:
            print("\n  Exiting. Run this script again when config.env is ready.")
            sys.exit(0)

    # Step 2: Initialize database
    section("Step 2: Database Initialization")
    if not DB_INIT.exists():
        print(f"  ERROR: {DB_INIT} not found.")
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, str(DB_INIT)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ERROR initializing database:")
        print(result.stderr)
        sys.exit(1)
    print(f"  Database initialized successfully.")
    if result.stdout.strip():
        print(f"  {result.stdout.strip()}")

    # Step 3: Hook configuration
    section("Step 3: Claude Code Hook Configuration")
    hook_incoming = SCRIPTS / "hook-incoming.py"
    hook_reply = SCRIPTS / "hook-reply.py"
    hook_stop = SCRIPTS / "hook-stop.py"

    print()
    print("  Add the following to ~/.claude/settings.json under the 'hooks' key.")
    print("  If settings.json already has hooks, merge this in.")
    print()
    print('  {')
    print('    "hooks": {')
    print('      "UserPromptSubmit": [')
    print('        {')
    print('          "hooks": [{')
    print('            "type": "command",')
    print(f'            "command": "python3 {hook_incoming}"')
    print('          }]')
    print('        }')
    print('      ],')
    print('      "PostToolUse": [')
    print('        {')
    print('          "matcher": "mcp__plugin_telegram_telegram__reply",')
    print('          "hooks": [{')
    print('            "type": "command",')
    print(f'            "command": "python3 {hook_reply}"')
    print('          }]')
    print('        }')
    print('      ],')
    print('      "Stop": [')
    print('        {')
    print('          "hooks": [{')
    print('            "type": "command",')
    print(f'            "command": "python3 {hook_stop}"')
    print('          }]')
    print('        }')
    print('      ]')
    print('    }')
    print('  }')
    print()

    # Step 4: Telegram plugin
    section("Step 4: Telegram Plugin")
    print()
    print("  Install and configure the Claude Code Telegram plugin:")
    print()
    print("    https://github.com/anthropics/claude-code-telegram")
    print()
    print("  You'll need a Telegram bot token from @BotFather.")
    print("  Follow the plugin's README to connect your token to Claude Code.")
    print()

    # Done
    section("Setup Complete")
    print()
    print("  Next steps:")
    print("  1. Complete the hook config in ~/.claude/settings.json (printed above)")
    print("  2. Set up the Telegram plugin with your bot token")
    print("  3. Open a Claude Code session in this directory:")
    print(f"     cd {ROOT} && claude")
    print()
    print("  Optional: Run /setup inside Claude Code for an interactive")
    print("  onboarding walkthrough that personalizes CLAUDE.md for you.")
    print()


if __name__ == "__main__":
    main()
