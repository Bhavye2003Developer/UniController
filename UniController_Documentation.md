# UniController
### Control Your Entire PC from Telegram

> **"No app. No VPN. No remote desktop. Just Telegram."**
>
> One Python script on your PC. One Telegram bot. Complete control.  
> Shell commands, Python REPL, screenshots, file transfer — all from your phone.

**Open Source · Privacy-First · Works on Any PC**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Problem](#2-the-problem)
3. [The Solution](#3-the-solution)
4. [Features](#4-features)
5. [Technical Stack](#5-technical-stack)
6. [Competitive Analysis](#6-competitive-analysis)
7. [Roadmap](#7-roadmap)
8. [Launch Strategy](#8-launch-strategy)
9. [Risks & Mitigations](#9-risks--mitigations)
10. [Quick Start Guide](#10-quick-start-guide)

---

## 1. Executive Summary

UniController is an open-source tool that turns your Telegram account into a full remote control interface for your PC. No third-party apps, no port forwarding, no VPN setup. A single lightweight Python daemon runs on your machine and listens for commands through the Telegram Bot API.

The core insight is simple: Telegram is already installed on every smartphone. It has a robust bot API, handles message delivery over the internet reliably, and requires zero network configuration on the user's side. UniController uses Telegram as the transport layer — your phone becomes a universal remote for your PC.

| Metric | Value |
|---|---|
| Dependencies | 5 Python packages — no GPU, no ML |
| Minimum RAM | 4GB — runs on any laptop |
| Install | `pip install unicontroller` |
| Platform | Windows, Linux, macOS |
| Data privacy | Zero data leaves your machine except Telegram messages you send |

---

## 2. The Problem

Existing remote PC control solutions all have significant friction:

| Tool | Problem | Limitation |
|---|---|---|
| TeamViewer / AnyDesk | Requires installing a separate app on phone | Slow, proprietary, paywalled for commercial use |
| Chrome Remote Desktop | Google account dependency, screen mirroring only | Dumb mirror — no programmable interface |
| SSH | Requires port forwarding or VPN | Not phone-friendly, complex setup |
| GitHub TRPCC / similar | Windows-only, messy multi-step setup | No Python REPL, no AI layer, ugly UX |
| Wake-on-LAN tools | Hardware-specific, network-dependent | Limited to one action |

The deeper problem: none of these give you a **programmable interface**. They let you see and click. UniController lets you think and command.

---

## 3. The Solution

UniController is a lightweight Python daemon that connects your PC to a Telegram bot. Every command you send from your phone executes on your PC. Responses come back instantly in chat.

### 3.1 Architecture

The architecture is intentionally minimal:

```
Phone (Telegram app)
    ↓  HTTPS  (Telegram Bot API handles routing)
Telegram Servers
    ↓  Long polling
PC Daemon (Python, ~50MB RAM)
    ↓  executes locally
Your PC (shell, files, screen, processes)
```

The daemon uses long-polling — it asks Telegram for new messages every few seconds. **No open ports. No firewall rules. No VPN.** Telegram acts as the secure relay.

### 3.2 Security Model

Security is handled by a single `ALLOWED_USER_ID` check on every handler. Only your Telegram account ID can issue commands. The bot token is stored in a local `.env` file. Because Telegram delivers messages over HTTPS, the communication channel is already encrypted.

### 3.3 Privacy

No data is sent to any third party except Telegram. The daemon does not phone home, does not log commands to any server, and does not require account creation. Your files, screenshots, and command output go directly between your PC and your Telegram account.

---

## 4. Features

### 4.1 V1 — Core Commands

| Command | Description | Notes |
|---|---|---|
| `/start` | Start the bot, verify auth | Always available |
| `/screenshot` | Get current screen as image | Sends PNG to chat |
| `/exec <cmd>` | Run any shell command | Returns stdout/stderr |
| `/runp` | Start Python REPL session | Persistent, interactive |
| `/sysinfo` | CPU, RAM, disk, battery, OS | Live stats |
| `/ps` | List running processes | PID + name + CPU% |
| `/kill <name>` | Kill a process by name | Safe with confirmation |
| `/files <path>` | Browse directory | Lists files + sizes |
| `/download` | Send file from PC to Telegram | Any file type |
| `/upload` | Receive file from Telegram to PC | Saves to downloads/ |
| `/clip get` | Get clipboard content | Returns text |
| `/clip set` | Set clipboard content | From chat message |
| `/volume <n>` | Set system volume 0–100 | Windows/Linux/Mac |
| `/lock` | Lock the screen | OS-native lock |
| `/shutdown` | Shutdown the PC | With 10s warning |
| `/restart` | Restart the PC | With 10s warning |

### 4.2 Python REPL — The Killer Feature

UniController includes a full interactive Python terminal inside Telegram. **This is the feature no existing tool has.**

```
How it works:
  1. Send /runp — a terminal widget appears in chat
  2. Type Python code directly — no button taps needed
  3. Output appears in the terminal widget, edited in-place
  4. Variables, imports, and state persist for the session
  5. Multi-line blocks (for loops, functions) auto-detect completion
  6. 🛑 Exit or 🗑 Clear from inline buttons
```

What it looks like in Telegram:

```
🖥  Python Terminal
────────────────────────────
>>> x = [1, 2, 3]
>>> sum(x)
6
>>> for i in range(5):
...     print(i * 2)
0
2
4
6
8
>>> import os; os.getcwd()
'/home/user/projects'
────────────────────────────
>>> _

[🛑 Exit]  [🗑 Clear]
```

**Technical implementation:** a persistent Python subprocess using `codeop` for block-completion detection, a `threading.Queue` for non-blocking output, and Telegram message editing for in-place terminal updates. One message, edited after every command.

### 4.3 V2 — AI Layer (Planned)

In V2, an LLM brain connects to the existing infrastructure. Same commands, same architecture — but now you can say things like:

- *"Find the report I was editing yesterday and send it to me"*
- *"Close all Chrome tabs and open Spotify"*
- *"Check if my build finished and send me the output"*
- *"Take a screenshot every 5 minutes and send it to me"*

The AI layer uses a small local model for context extraction (privacy-preserving) and optionally a cloud model (Claude API, Gemini) for reasoning. User's choice. Data stays on device.

---

## 5. Technical Stack

### 5.1 Dependencies

| Package | Version | Purpose |
|---|---|---|
| `python-telegram-bot` | v22.7 (Mar 2026) | Telegram Bot API wrapper — actively maintained |
| `mss` | v10.2.0 (Apr 2026) | Ultra-fast cross-platform screenshots |
| `Pillow` | Latest stable | Image processing for screenshot compression |
| `psutil` | Latest stable | System stats — CPU, RAM, battery, processes |
| `pyperclip` | v1.5+ | Cross-platform clipboard read/write |
| `python-dotenv` | Latest stable | Environment variable management |

All six dependencies are actively maintained as of May 2026. `subprocess`, `pathlib`, `threading`, `queue`, `codeop`, and `os` are Python built-ins — zero additional installs.

### 5.2 Project Structure

```
unicontroller/
├── bot/
│   ├── tele_main.py          # Bot entry point, all handlers
│   └── utils/
│       ├── CommandExecutor.py  # Shell command runner
│       └── PythonTerminal.py   # REPL session manager
├── .env                      # TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID
├── requirements.txt
└── README.md
```

### 5.3 System Requirements

| Requirement | Specification |
|---|---|
| Python version | 3.10 or higher |
| RAM | 4GB minimum (daemon uses ~50MB) |
| OS | Windows 10+, Ubuntu 20.04+, macOS 12+ |
| Internet | Any connection — Telegram polling is lightweight |
| GPU | Not required |
| Disk | <10MB for the daemon |

---

## 6. Competitive Analysis

### 6.1 Existing Projects on GitHub

**TRPCC (xzripper)** is the most feature-complete competitor. It supports file management, process control, keyboard/mouse injection, and keylogging. However it is Windows-only, has no Python REPL, and requires compiling a binary. Setup is non-trivial.

**PCGuardControl (Farmerok)** adds camera and microphone access. The feature set is broad but positioning is surveillance-first, not developer-first. Setup still requires multiple manual steps.

**PC-Control-telegram-bot (Tostapunk)** has a multi-user database and scheduled commands. But it depends on python-tk for setup UI and lacks cross-platform support.

### 6.2 Differentiation Matrix

| Feature | UniController | Competitors |
|---|---|---|
| One-command install | ✅ `pip install unicontroller` | ❌ Multi-step for all |
| Python REPL in Telegram | ✅ Full interactive terminal | ❌ None have this |
| Cross-platform | ✅ Win + Linux + Mac | ⚠️ Windows-primary for most |
| AI layer (V2) | ✅ Planned, architecture ready | ❌ None planned |
| Privacy-first | ✅ No cloud, no account | ⚠️ Varies |
| Open source | ✅ MIT License | ⚠️ Mixed |
| Active maintenance | ✅ 2026 | ⚠️ Most last updated 2022–23 |

---

## 7. Roadmap

### Phase 1 — Core (Current)
- [x] Telegram bot daemon with auth
- [x] Shell command execution (`/exec`)
- [x] Screenshot capture (`/screenshot`)
- [x] Interactive Python REPL in Telegram (`/runp`)
- [x] Multi-line code block auto-detection
- [x] In-place terminal widget with inline buttons

### Phase 2 — Complete Control
- [ ] System info — CPU, RAM, battery, disk (`/sysinfo`)
- [ ] Process management — list and kill (`/ps`, `/kill`)
- [ ] File browser (`/files`)
- [ ] File download/upload (`/download`, `/upload`)
- [ ] Clipboard read/write (`/clip`)
- [ ] Volume control (`/volume`)
- [ ] Screen lock, shutdown, restart
- [ ] Startup daemon — auto-run on system boot

### Phase 3 — AI Layer
- [ ] Natural language command parsing
- [ ] Local context extraction (small model, privacy-preserving)
- [ ] Cloud LLM integration — Claude API / Gemini (optional, user-controlled)
- [ ] Multi-step task execution
- [ ] Scheduled tasks
- [ ] Smart notifications

### Phase 4 — Polish & Launch
- [ ] `pip install unicontroller` with CLI entry point
- [ ] Interactive first-run setup wizard
- [ ] Demo GIF for README
- [ ] Product Hunt launch
- [ ] Hacker News Show HN post
- [ ] GitHub Stars campaign

---

## 8. Launch Strategy

### 8.1 Positioning

The project does not launch as an "AI tool". It launches as the cleanest, simplest way to control your PC from Telegram. AI is V2. The hook is immediate utility.

**README hook (first 3 lines):**

```markdown
# UniController
Control your entire PC from Telegram. No app. No VPN. No bullshit.
pip install unicontroller && unicontroller init
```

### 8.2 Target Audience

- Developers who SSH into machines and want something simpler
- Power users who want to control their home PC while traveling
- Students who want to run code on their PC from a phone
- IT professionals managing personal machines

### 8.3 Distribution Channels

| Channel | Strategy |
|---|---|
| GitHub | Primary home. README with demo GIF is the product page. |
| Hacker News | *Show HN: "I built a Python REPL inside Telegram to control my PC"* |
| Product Hunt | Launch with screenshots of the terminal UI in action |
| Reddit | r/Python, r/selfhosted, r/commandline, r/telegram |
| Twitter / X | Demo video of for loop running in Telegram terminal |
| Dev.to | Technical writeup: architecture + how the REPL works |

### 8.4 The Demo That Goes Viral

A 30-second screen recording: Python terminal in Telegram executing a for loop, then a screenshot command, then a file download — all from a phone, with the PC visibly responding. No words needed.

---

## 9. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Bot token leaked | High | `.env` file, `.gitignore`, user education in README |
| Unauthorized access | High | `ALLOWED_USER_ID` check on every handler |
| Command hangs PC | Medium | 30s timeout on all subprocess calls |
| Telegram API rate limits | Medium | Polling handles this; no burst sending |
| PC sleeps/hibernates | Medium | V2: startup daemon + wake-on-LAN docs |
| Windows-only features | Low | OS detection, graceful fallbacks |
| Python process crash | Low | `BrokenPipeError` caught, session restart prompt |

---

## 10. Quick Start Guide

### Step 1 — Create a Telegram Bot
1. Open Telegram, search for **@BotFather**
2. Send `/newbot`, follow prompts, copy the token
3. Send `/start` to your new bot to get your chat ID

### Step 2 — Setup
```bash
git clone https://github.com/yourname/unicontroller
cd unicontroller
pip install -r requirements.txt
```

### Step 3 — Configure
Create a `.env` file in the project root:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
ALLOWED_USER_ID=your_telegram_user_id
```

### Step 4 — Run
```bash
python bot/tele_main.py
```

### Step 5 — Use
- Open Telegram on your phone
- Send `/start` — should reply instantly
- Send `/screenshot` — get your current screen
- Send `/runp` — open the Python terminal
- Type any Python code directly and hit send

> ⚠️ **Security reminder:** Never share your bot token. Never commit `.env` to git. Add `.env` to your `.gitignore` before your first commit.

---

*UniController — Open Source, MIT License — Built May 2026*
