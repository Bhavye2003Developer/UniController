# UniController

Control your entire PC from Telegram. Single-user, self-hosted, no cloud middleman, no AI required.

## Setup

**1. Clone and install**
```bash
git clone https://github.com/Bhavye2003Developer/UniController
cd UniController
python -m venv venv
venv\Scripts\activate       # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
```

**2. Create `.env` in the project root**
```
TELEGRAM_BOT_TOKEN=your_bot_token
ALLOWED_USER_ID=your_telegram_user_id
```

Get your bot token from [@BotFather](https://t.me/BotFather) and your user ID from [@userinfobot](https://t.me/userinfobot).

**3. Run**
```bash
python bot/tele_main.py
```

**Auto-start on login (Windows)**
```
/daemon install
```

---

## Features

### Core
| Command | Description |
|---|---|
| `/exec <cmd>` | Run any shell command, get output |
| `/screenshot [n\|all]` | Capture screen, specific monitor, or all monitors |
| `/runp` | Interactive Python REPL with persistent state |

### System
| Command | Description |
|---|---|
| `/sysinfo` | CPU, RAM, disk, network, uptime with bar graphs |
| `/ps` | Top 15 processes by CPU with inline kill buttons |
| `/kill <pid\|name>` | Kill a process by PID or name |
| `/temp` | CPU temperatures per zone |
| `/lock` | Lock screen |
| `/shutdown` `/restart` | Power control with confirm step |
| `/activewindow` | Focused window title, process, memory, uptime |
| `/powerplan [name]` | Show or switch Windows power plan |
| `/windows` | List open windows with focus/minimize/close buttons |

### Files
| Command | Description |
|---|---|
| `/files` | Inline file browser starting at drive root |
| `/download [path]` | Browse or send any file to Telegram |
| `/upload` | Save a file from Telegram to PC |
| `/print` | Print a document (reply to file) |
| `/cleanup` | Scan Temp and old Downloads, clean with one tap |
| `/search <pattern> [path]` | Search file contents across text files |
| `/stage <path>` | Upload file to Telegram for offline access |

Send a photo to the bot: choose wallpaper, save to Desktop, or save to inbox folder.

### Clipboard
| Command | Description |
|---|---|
| `/clip get` | Read current clipboard |
| `/clip set` | Write to clipboard (reply to a message) |
| `/clip history` | Last 10 clipboard items with timestamps |

### Media
| Command | Description |
|---|---|
| `/media` | Play/pause/next/prev/volume panel |
| `/volume [0-100\|up\|down\|mute]` | Get or set system volume |
| `/nowplaying` | Current track from any app via Windows SMTC |

### Apps
| Command | Description |
|---|---|
| `/launch <name>` | Fuzzy-matched app launcher |
| `/focus [minutes]` | Kill distraction apps, notify on completion |
| `/type <text>` | Type text into whatever window is active |
| `/speedtest` | Internet speed test |

### Scheduler
| Command | Description |
|---|---|
| `/schedule <time> <cmd>` | Schedule exec/shutdown/restart at a time or delay |
| `/babysit <cmd>` | Run a command, notify when it exits with output |
| `/wake <mac>` | Send Wake-on-LAN magic packet |

Examples: `/schedule in 2h shutdown`, `/schedule 11:30pm exec git pull`

### Network
| Command | Description |
|---|---|
| `/netstat` | Active connections grouped by process, tree-style |
| `/lan` | Ping-sweep LAN, list devices with hostnames and MACs |

### Remote / Presentation
| Command | Description |
|---|---|
| `/next` `/prev` | Arrow keys (slide navigation) |
| `/fullscreen` `/escape` | F5 / Escape |
| `/openurl <url>` | Open URL in default browser |
| `/closetab` | Ctrl+W |

### Notepad
| Command | Description |
|---|---|
| `/note <text>` | Add a timestamped note |
| `/notes` | List all notes |
| `/note clear <n>` | Delete note by number |

### Watchers
| Command | Description |
|---|---|
| `/watch <rule>` | Add a background watch rule |
| `/watches` | List active rules |
| `/unwatch <id>` | Remove a rule |

Rule syntax: `cpu > 90`, `ram > 80`, `disk free < 5GB`, `process chrome exits`, `file C:\build.log changes`

### Reports
| Command | Description |
|---|---|
| `/report now` | Instant CPU/RAM/disk/battery snapshot |
| `/report on HH:MM` | Schedule a daily morning report |
| `/report off` | Cancel daily report |

Returns from 30+ min idle automatically trigger a session summary of what happened while you were away.

### Timelapse
| Command | Description |
|---|---|
| `/timelapse <duration> [interval=Xm]` | Record screen as animated GIF |
| `/stream [seconds]` | 5-60s screen burst as animated GIF |

### Guardian
| Command | Description |
|---|---|
| `/snap` | Webcam snapshot on demand |
| `/guard on\|off\|status` | Motion, USB, and failed login alerts |
| `/panic` | Snap webcam + lock screen + disable Wi-Fi |

### Daemon
| Command | Description |
|---|---|
| `/daemon install` | Add to Windows startup (Registry Run key) |
| `/daemon uninstall` | Remove from startup |
| `/daemon status` | Check startup registration |

---

## File Inbox / Outbox

Two magic folders created automatically at `~/UniController/`:

- **inbox/**: files saved here by the bot (uploads, photos)
- **outbox/**: drop any file here and it auto-sends to Telegram, then moves to `outbox/sent/`

---

## Security

- One `ALLOWED_USER_ID` checked on every handler. All other requests are silently dropped.
- Bot token stored locally in `.env`, never leaves your machine.
- No data sent to any third party except Telegram (over HTTPS).

---

## Stack

Python 3.10+, python-telegram-bot v22, psutil, mss, Pillow, pycaw, pynput, pywin32, rapidfuzz, speedtest-cli, wakeonlan
