# UniController V2 — Design Spec

**Date:** 2026-05-03
**Status:** Awaiting implementation

---

## Overview

UniController V2 adds two pillars on top of the existing Phase 1 foundation:

1. **Guardian Mode** — the viral headline. PC becomes a security sentinel that proactively messages you.
2. **Daily Driver** — the retention layer. 15+ commands that make the bot genuinely useful every day.

**Platform:** Windows only (first). Linux port deferred — isolated in `windows_utils.py` for future portability.
**No AI, no external APIs beyond Telegram.** Everything runs locally.

---

## Architecture

### Directory Structure

```
bot/
  tele_main.py              # entry point + handler registration only
  handlers/
    guardian.py             # /snap, /guard, /panic
    system.py               # /sysinfo, /ps, /kill, /lock, /shutdown, /restart
    files.py                # /files, /download, /upload
    media.py                # /media inline control panel
    clipboard.py            # /clip get, /clip set
    misc.py                 # /volume, /launch, /focus
utils/
  PythonTerminal.py         # unchanged
  CommandExecutor.py        # unchanged
  guardian_watcher.py       # background thread: motion, USB, login events
  notification_mirror.py    # background thread: Windows toast → Telegram
  windows_utils.py          # all win32/ctypes/WMI calls isolated here
```

### Key Decisions

- `tele_main.py` registers handlers only — zero feature logic lives in it
- Guardian Mode and notification mirror each run as **daemon threads** — fire `bot.send_message()` when events trigger, fully independent of the async Telegram loop
- All Windows-specific API calls isolated in `windows_utils.py` — future Linux port replaces only this file
- Every handler is `async def`, wraps body in `try/except`, replies with short error on failure, never crashes the bot

---

## Guardian Mode

### Commands

| Command | Behaviour |
|---|---|
| `/snap` | Takes webcam photo, sends to Telegram immediately |
| `/guard on` | Activates background watcher (motion + USB + login) |
| `/guard off` | Deactivates watcher |
| `/guard status` | Shows active watchers, last event time, motion sensitivity |
| `/panic` | Lock + snap + kill network → sends confirmation |

### `/guard` — Background Watcher Triggers

**Motion detection**
- Captures webcam frame every `GUARD_CHECK_INTERVAL` seconds (default 10s)
- Computes pixel diff vs baseline frame using OpenCV
- If diff exceeds `MOTION_THRESHOLD` (default 500 changed pixels) → sends snap + alert
- Baseline resets when guard is toggled on

**USB insertion**
- WMI event subscription on `Win32_DeviceChangeEvent`
- On new device → sends device name + alert immediately

**Failed login attempt**
- Polls Windows Security Event Log (Event ID 4625) every 30s
- On new event since last check → sends alert + snap

### `/panic` — Sequence

Executes in order, attempts every step regardless of individual failures:
1. Webcam snap → send to Telegram
2. Send confirmation: *"PC locked. Photo attached."*
3. Lock screen via `rundll32.exe user32.dll,LockWorkStation`
4. Disable WiFi adapter via `netsh interface set interface "Wi-Fi" disable` (recoverable — user re-enables from PC)

### Webcam Snapshots

Never written to disk. Captured as bytes via OpenCV, sent directly to Telegram as `InputFile(BytesIO(...))`, then discarded.

---

## Daily Driver Features

### System Commands

| Command | Behaviour |
|---|---|
| `/sysinfo` | CPU%, RAM%, disk%, network up/down, uptime — clean formatted message |
| `/ps` | Top 15 processes by CPU with inline "Kill" button per row |
| `/kill <name\|pid>` | Sends confirmation prompt before killing |
| `/lock` | Locks screen |
| `/shutdown` | Confirmation required → shuts down PC |
| `/restart` | Confirmation required → restarts PC |

`/shutdown` and `/restart` require confirmation: bot replies *"Type `confirm` to proceed"* — prevents accidental triggers.

### File Operations

| Command | Behaviour |
|---|---|
| `/files [path]` | Inline keyboard file browser — navigate folders with buttons, tap file to download |
| `/download <path>` | Sends specified file from PC to Telegram chat |
| `/upload <path>` | Reply to any Telegram file with this command → saves to specified path on PC |

Default upload destination: `UPLOAD_DEFAULT_PATH` in `.env`.

### Clipboard Sync

| Command | Behaviour |
|---|---|
| `/clip get` | Sends current PC clipboard content to Telegram |
| `/clip set` | Reply to any message with this → copies that text to PC clipboard |

Bidirectional. Phone → PC and PC → phone. No cloud, no sync service.

### Media Control

`/media` sends an inline keyboard panel:

```
[track name — artist]
[album art thumbnail]
[⏮ Prev]  [⏯ Play/Pause]  [⏭ Next]
[🔉 Vol-]  [🔇 Mute]       [🔊 Vol+]
```

- Uses Windows media key simulation via `pynput`
- Works with any media player (Spotify, VLC, browser, Windows Media Player)
- No app-specific integration — simulates keyboard media keys OS-level
- Track info pulled from Windows SMTC (System Media Transport Controls) via `winrt` package (`winrt-Windows.Media.Control`)

### Notification Mirror

`/notify on|off` — toggles forwarding of Windows toast notifications to Telegram in real time.

- Background thread hooks into Windows notification COM interface
- Filters out notifications containing words in `NOTIFY_BLACKLIST` (configurable in `.env`, default includes: `password`, `otp`, `code`, `pin`)
- Off by default (`NOTIFY_MIRROR=false` in `.env`)

### App Launcher

`/launch <query>` — fuzzy searches installed apps and launches best match.

- Reads Start Menu shortcuts (`%APPDATA%\Microsoft\Windows\Start Menu`) + registry uninstall keys
- Uses `rapidfuzz` for matching
- Example: `/launch spot` → launches Spotify

### Volume Control

`/volume <0-100|up|down|mute>` — direct volume control via `pycaw` (Windows Core Audio API).

### Focus Mode

`/focus <minutes>` — starts a focus session:
1. Kills all apps in `FOCUS_BLOCKLIST` (configurable in `.env`)
2. Sends "Focus session started — X minutes"
3. After X minutes, sends "Focus complete"

---

## Configuration (`.env` additions)

```
# Guardian Mode
MOTION_THRESHOLD=500
GUARD_CHECK_INTERVAL=10

# Notification Mirror
NOTIFY_MIRROR=false
NOTIFY_BLACKLIST=password,otp,code,pin,secret

# File Operations
UPLOAD_DEFAULT_PATH=C:\Users\%USERNAME%\Downloads

# Focus Mode
FOCUS_BLOCKLIST=chrome,discord,steam,spotify
```

---

## Dependencies (new)

| Package | Purpose |
|---|---|
| `opencv-python` | Webcam capture + motion detection (pixel diff) |
| `wmi` | USB event subscription, Windows Event Log polling |
| `pywin32` | Screen lock, Windows API calls |
| `pycaw` | Volume control via Windows Core Audio API |
| `pynput` | Media key simulation |
| `winrt` | SMTC track info (now playing, artist, album art) |
| `rapidfuzz` | Fuzzy app name matching for `/launch` |
| `comtypes` | COM interface for notification mirror |

---

## Security

- `ALLOWED_USER_ID` check on every handler — unchanged from V1
- `/panic`, `/shutdown`, `/restart` require explicit `confirm` reply before executing
- Webcam snapshots never saved to disk — bytes only, sent directly to Telegram
- Notification mirror respects `NOTIFY_BLACKLIST` to avoid forwarding sensitive alerts
- Guardian daemon errors log to `unicontroller.log` but never crash the bot process

