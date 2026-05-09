# UniController

Control your PC from Telegram. Single-user, self-hosted, no cloud middleman.

## What it does

Send commands to your PC from anywhere via a private Telegram bot.

**System**
- `/sysinfo` — CPU, RAM, disk, uptime
- `/ps` — top processes with inline kill buttons
- `/kill <pid>` — kill a process
- `/lock` `/shutdown` `/restart` — power controls

**Files**
- `/files` — inline file browser
- `/download <path>` — send file to chat
- `/upload` — receive file from chat

**Shell + Python**
- `/exec <cmd>` — run any shell command
- `/runp` — interactive Python REPL

**Media + Clipboard**
- `/media` — play/pause/next/prev/volume panel
- `/volume <0-100>` — set system volume
- `/clip get/set` — read/write clipboard

**Apps**
- `/launch <name>` — fuzzy app launcher
- `/focus <minutes>` — block distraction apps

**Guardian Mode**
- `/snap` — webcam snapshot on demand
- `/guard on/off/status` — motion detection, USB alerts, failed login alerts
- `/panic` — snap + lock screen + disable Wi-Fi

## Setup

```bash
pip install -r requirements.txt
```

Create `.env` in the project root:

```
TELEGRAM_BOT_TOKEN=your_token
ALLOWED_USER_ID=your_telegram_id
```

```bash
python bot/tele_main.py
```

## Security

Only one Telegram user ID can interact with the bot. All other requests are silently dropped.

## Stack

Python 3.10+, python-telegram-bot v22, pycaw, pynput, rapidfuzz, OpenCV
