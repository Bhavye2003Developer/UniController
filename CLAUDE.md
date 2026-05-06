# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup & Run

```bash
pip install -r requirements.txt
python bot/tele_main.py
```

Requires `.env` in project root:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
ALLOWED_USER_ID=your_telegram_user_id
```

No test suite exists — test manually via the Telegram bot.

## Architecture

UniController is a Telegram bot that acts as a remote control daemon for a PC. The bot uses long-polling (`run_polling()`) and enforces single-user auth via `ALLOWED_USER_ID` on every handler.

**Data flow:** Telegram app → Telegram Bot API (HTTPS) → `bot/tele_main.py` (long-poll) → local OS (shell, screen, Python REPL)

**Key components:**

- `bot/tele_main.py` — entry point, command router, all Telegram handlers (`/start`, `/exec`, `/screenshot`, `/runp`), auth enforcement
- `utils/PythonTerminal.py` — interactive Python REPL: spawns a subprocess with embedded worker code, uses `codeop.compile_command()` for multi-line block detection, captures output via `threading.Queue`, edits a single Telegram message in-place to avoid spam
- `utils/CommandExecutor.py` — shell command runner with 30s timeout; partially superseded by inline logic in `tele_main.py`

**Authorization pattern:** Every handler calls `is_authorized(update)` which checks `update.effective_user.id == ALLOWED_USER_ID`. Unauthorized requests are silently dropped.

**Python REPL internals:** Worker code is written to a temp file on `terminal.start()` and deleted on stop. Sentinel strings (`__MORE__`, `__DONE__`) in the subprocess protocol signal multi-line vs completed state. Terminal history capped at 30 lines. Output HTML-escaped before sending to Telegram.

## Platform

Python 3.10+, targets Windows/Linux/macOS. `python-telegram-bot` v22.x uses async handlers — all handler functions must be `async def`.