# Daily Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 15 daily-use commands across system monitoring, file operations, clipboard sync, media control, app launcher, volume, and focus mode.

**Architecture:** Six new handler modules in `bot/handlers/`. Windows-specific helpers (volume, media keys, app search) added to `utils/windows_utils.py`. Shutdown/restart confirm routing extended in `bot/handlers/core.py` handle_message. All handlers registered in `bot/tele_main.py`.

**Tech Stack:** psutil (already installed), pycaw, pynput, rapidfuzz, python-telegram-bot 22.7

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `requirements.txt` | Add pycaw, pynput, rapidfuzz |
| Modify | `utils/windows_utils.py` | Add get_volume, set_volume, press_media_key, list_apps |
| Create | `bot/handlers/system.py` | /sysinfo, /ps, /kill, /lock, /shutdown, /restart |
| Create | `bot/handlers/files.py` | /files, /download, /upload |
| Create | `bot/handlers/clipboard.py` | /clip get, /clip set |
| Create | `bot/handlers/media.py` | /media inline panel |
| Create | `bot/handlers/misc.py` | /volume, /launch, /focus |
| Modify | `bot/handlers/core.py` | Extend handle_message for shutdown/restart confirm routing |
| Modify | `bot/tele_main.py` | Register all new handlers |
| Create | `tests/test_system_handlers.py` | System handler tests |
| Create | `tests/test_files_handlers.py` | File handler tests |
| Create | `tests/test_clipboard_handlers.py` | Clipboard handler tests |
| Create | `tests/test_misc_handlers.py` | Misc handler tests |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add new packages to requirements.txt**

Append to the existing requirements.txt (keep all existing lines, add these):
```
pycaw
pynput
rapidfuzz
```

- [ ] **Step 2: Install**

```bash
pip install pycaw pynput rapidfuzz
```

Expected: all install without error.

- [ ] **Step 3: Verify**

```bash
python -c "from pycaw.pycaw import AudioUtilities; from pynput.keyboard import Key, Controller; from rapidfuzz import fuzz; print('all ok')"
```

---

## Task 2: Extend `utils/windows_utils.py`

Add volume control, media key simulation, and app list functions. All Windows-specific API calls stay isolated here.

**Files:**
- Modify: `utils/windows_utils.py`
- Modify: `tests/test_windows_utils.py`

- [ ] **Step 1: Add tests for new functions**

Append to `tests/test_windows_utils.py`:

```python
def test_get_volume_returns_float(mocker):
    import utils.windows_utils as wu
    mock_sessions = mocker.MagicMock()
    mock_vol = mocker.MagicMock()
    mock_vol.GetMasterVolumeLevelScalar.return_value = 0.5
    mock_sessions.QueryInterface.return_value = mock_vol
    mocker.patch("utils.windows_utils.AudioUtilities.GetSpeakers", return_value=mock_sessions)
    mocker.patch("utils.windows_utils.cast", return_value=mock_vol)
    mocker.patch("utils.windows_utils.IAudioEndpointVolume")
    result = wu.get_volume()
    assert isinstance(result, float)


def test_list_apps_returns_list():
    import utils.windows_utils as wu
    apps = wu.list_apps()
    assert isinstance(apps, list)
    # Each entry is a (name, path) tuple
    if apps:
        assert isinstance(apps[0], tuple)
        assert len(apps[0]) == 2
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -m pytest tests/test_windows_utils.py -v -k "volume or apps" 2>&1 | head -20
```

- [ ] **Step 3: Append to `utils/windows_utils.py`**

Add these imports at the top (after existing imports):
```python
import glob
import winreg
from pathlib import Path
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
```

Add these functions at the bottom of the file:

```python
def get_volume() -> float:
    speakers = AudioUtilities.GetSpeakers()
    interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    return round(volume.GetMasterVolumeLevelScalar() * 100, 1)


def set_volume(level: int) -> None:
    speakers = AudioUtilities.GetSpeakers()
    interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level / 100)), None)


def mute_toggle() -> None:
    from pynput.keyboard import Key, Controller
    kb = Controller()
    kb.press(Key.media_volume_mute)
    kb.release(Key.media_volume_mute)


def press_media_key(action: str) -> None:
    from pynput.keyboard import Key, Controller
    key_map = {
        'play_pause': Key.media_play_pause,
        'next': Key.media_next,
        'prev': Key.media_previous,
        'vol_up': Key.media_volume_up,
        'vol_down': Key.media_volume_down,
        'mute': Key.media_volume_mute,
    }
    key = key_map.get(action)
    if key is None:
        raise ValueError(f"Unknown media action: {action}")
    kb = Controller()
    kb.press(key)
    kb.release(key)


def list_apps() -> list[tuple[str, str]]:
    apps: list[tuple[str, str]] = []
    start_menu_dirs = [
        Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
        Path(os.environ.get('PROGRAMDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
    ]
    for smd in start_menu_dirs:
        if smd.exists():
            for lnk in smd.rglob('*.lnk'):
                apps.append((lnk.stem, str(lnk)))
    return apps


def launch_app(path: str) -> None:
    os.startfile(path)
```

- [ ] **Step 4: Run tests**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -m pytest tests/test_windows_utils.py -v 2>&1 | tail -10
```

Expected: all previous tests still pass + new ones pass (volume test requires mocking, list_apps reads real filesystem).

---

## Task 3: Create `bot/handlers/system.py`

**Files:**
- Create: `bot/handlers/system.py`
- Create: `tests/test_system_handlers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_system_handlers.py`:

```python
import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('ALLOWED_USER_ID', '12345')


@pytest.fixture
def auth_update():
    u = MagicMock()
    u.effective_user.id = 12345
    u.effective_chat.id = 12345
    u.message.reply_text = AsyncMock()
    u.message.reply_html = AsyncMock()
    return u


@pytest.fixture
def unauth_update():
    u = MagicMock()
    u.effective_user.id = 99999
    u.message.reply_text = AsyncMock()
    return u


@pytest.fixture
def ctx():
    c = MagicMock()
    c.args = []
    return c


@pytest.mark.asyncio
async def test_sysinfo_unauthorized_drops(unauth_update, ctx):
    from bot.handlers.system import sysinfo
    await sysinfo(unauth_update, ctx)
    unauth_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_sysinfo_sends_message(auth_update, ctx):
    with patch("psutil.cpu_percent", return_value=25.0), \
         patch("psutil.virtual_memory", return_value=MagicMock(percent=60, used=8*1024**3, total=16*1024**3)), \
         patch("psutil.disk_usage", return_value=MagicMock(percent=50, used=250*1024**3, total=500*1024**3)), \
         patch("psutil.net_io_counters", return_value=MagicMock(bytes_sent=1024, bytes_recv=2048)), \
         patch("psutil.boot_time", return_value=0):
        from bot.handlers.system import sysinfo
        await sysinfo(auth_update, ctx)
        auth_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_adds_to_pending(auth_update, ctx):
    from bot.handlers import system
    system._pending_shutdown.clear()
    await system.shutdown(auth_update, ctx)
    assert auth_update.effective_chat.id in system._pending_shutdown
    auth_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_restart_adds_to_pending(auth_update, ctx):
    from bot.handlers import system
    system._pending_restart.clear()
    await system.restart(auth_update, ctx)
    assert auth_update.effective_chat.id in system._pending_restart


@pytest.mark.asyncio
async def test_lock_calls_lock_screen(auth_update, ctx):
    with patch("bot.handlers.system.lock_screen") as mock_lock:
        from bot.handlers.system import lock
        await lock(auth_update, ctx)
        mock_lock.assert_called_once()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -m pytest tests/test_system_handlers.py -v 2>&1 | head -20
```

- [ ] **Step 3: Create `bot/handlers/system.py`**

```python
import datetime
import os
import subprocess
import time

import psutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from utils.windows_utils import lock_screen

_pending_shutdown: set[int] = set()
_pending_restart: set[int] = set()


async def sysinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('C:\\')
    net = psutil.net_io_counters()
    uptime = str(datetime.timedelta(seconds=int(time.time() - psutil.boot_time())))

    msg = (
        f"💻 <b>System Info</b>\n"
        f"CPU: {cpu}%\n"
        f"RAM: {ram.percent}% "
        f"({ram.used // 1024**3:.1f}/{ram.total // 1024**3:.1f} GB)\n"
        f"Disk C: {disk.percent}% "
        f"({disk.used // 1024**3:.1f}/{disk.total // 1024**3:.1f} GB)\n"
        f"Net ↑{net.bytes_sent // 1024} KB ↓{net.bytes_recv // 1024} KB\n"
        f"Uptime: {uptime}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def ps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    procs.sort(key=lambda x: x.get('cpu_percent') or 0, reverse=True)
    top = procs[:15]

    lines = []
    keyboard = []
    for p in top:
        name = (p.get('name') or 'Unknown')[:20]
        cpu = p.get('cpu_percent') or 0
        pid = p.get('pid', 0)
        lines.append(f"{pid:6d} {cpu:5.1f}% {name}")
        keyboard.append([InlineKeyboardButton(f"🔴 {name}", callback_data=f"killpid_{pid}")])

    text = "<code>   PID   CPU% Name\n" + "\n".join(lines) + "</code>"
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def kill_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /kill <pid|name>")
        return
    target = context.args[0]
    try:
        pid = int(target)
        proc = psutil.Process(pid)
        proc.kill()
        await update.message.reply_text(f"Killed PID {pid}.")
    except ValueError:
        killed = []
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if (p.info.get('name') or '').lower() == target.lower():
                    p.kill()
                    killed.append(p.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed:
            await update.message.reply_text(f"Killed: {killed}")
        else:
            await update.message.reply_text(f"No process named '{target}'.")
    except psutil.NoSuchProcess:
        await update.message.reply_text(f"PID {target} not found.")
    except Exception as e:
        await update.message.reply_text(f"Kill failed: {e}")


async def kill_pid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split('_')[1])
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.kill()
        await query.edit_message_text(f"✅ Killed {name} (PID {pid})")
    except psutil.NoSuchProcess:
        await query.edit_message_text(f"Process {pid} no longer exists.")
    except Exception as e:
        await query.edit_message_text(f"Kill failed: {e}")


async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    lock_screen()
    await update.message.reply_text("🔒 Screen locked.")


async def shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    _pending_shutdown.add(update.effective_chat.id)
    await update.message.reply_text("⚠️ Type `confirm` to shut down the PC.")


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    _pending_restart.add(update.effective_chat.id)
    await update.message.reply_text("⚠️ Type `confirm` to restart the PC.")


async def shutdown_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _pending_shutdown.discard(update.effective_chat.id)
    await update.message.reply_text("Shutting down in 3 seconds...")
    subprocess.run(['shutdown', '/s', '/t', '3'])


async def restart_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _pending_restart.discard(update.effective_chat.id)
    await update.message.reply_text("Restarting in 3 seconds...")
    subprocess.run(['shutdown', '/r', '/t', '3'])


def register_system_handlers(app) -> None:
    app.add_handler(CommandHandler("sysinfo",  sysinfo))
    app.add_handler(CommandHandler("ps",       ps))
    app.add_handler(CommandHandler("kill",     kill_cmd))
    app.add_handler(CommandHandler("lock",     lock))
    app.add_handler(CommandHandler("shutdown", shutdown))
    app.add_handler(CommandHandler("restart",  restart))
    app.add_handler(CallbackQueryHandler(kill_pid_callback, pattern="^killpid_"))
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -m pytest tests/test_system_handlers.py -v 2>&1
```

Expected: 5 passed.

---

## Task 4: Create `bot/handlers/files.py`

**Files:**
- Create: `bot/handlers/files.py`
- Create: `tests/test_files_handlers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_files_handlers.py`:

```python
import pytest, os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

os.environ.setdefault('ALLOWED_USER_ID', '12345')


@pytest.fixture
def auth_update():
    u = MagicMock()
    u.effective_user.id = 12345
    u.effective_chat.id = 12345
    u.message.reply_text = AsyncMock()
    u.message.reply_document = AsyncMock()
    u.message.document = None
    return u


@pytest.fixture
def ctx():
    c = MagicMock()
    c.args = []
    c.user_data = {}
    return c


@pytest.mark.asyncio
async def test_files_invalid_path_replies_error(auth_update, ctx):
    ctx.args = ['/nonexistent/path/xyz']
    from bot.handlers.files import files
    await files(auth_update, ctx)
    auth_update.message.reply_text.assert_called_once()
    msg = auth_update.message.reply_text.call_args[0][0].lower()
    assert "not a directory" in msg or "does not exist" in msg or "error" in msg


@pytest.mark.asyncio
async def test_files_lists_home_dir(auth_update, ctx):
    ctx.args = []
    from bot.handlers.files import files
    await files(auth_update, ctx)
    auth_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_download_nonexistent_file_replies_error(auth_update, ctx):
    ctx.args = ['/nonexistent/file.txt']
    from bot.handlers.files import download
    await download(auth_update, ctx)
    auth_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_upload_no_file_replies_error(auth_update, ctx):
    auth_update.message.document = None
    auth_update.message.reply_to_message = None
    from bot.handlers.files import upload
    await upload(auth_update, ctx)
    auth_update.message.reply_text.assert_called_once()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -m pytest tests/test_files_handlers.py -v 2>&1 | head -20
```

- [ ] **Step 3: Create `bot/handlers/files.py`**

```python
import os
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.handlers.core import is_authorized

UPLOAD_DEFAULT_PATH = os.getenv('UPLOAD_DEFAULT_PATH', str(Path.home() / 'Downloads'))


async def files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    path_str = ' '.join(context.args) if context.args else str(Path.home())
    await _show_dir(update.message, context, Path(path_str))


async def _show_dir(message, context, path: Path) -> None:
    if not path.exists() or not path.is_dir():
        await message.reply_text(f"Not a directory: {path}")
        return

    try:
        items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))[:20]
    except PermissionError:
        await message.reply_text(f"Permission denied: {path}")
        return

    # Store mapping in user_data for callback lookups
    context.user_data['browse_dir'] = str(path)
    context.user_data['browse_items'] = {i: str(item) for i, item in enumerate(items)}

    keyboard = []
    if path.parent != path:
        keyboard.append([InlineKeyboardButton("⬆️ ..", callback_data="nav_up")])

    for i, item in enumerate(items):
        name = item.name[:40]
        if item.is_dir():
            keyboard.append([InlineKeyboardButton(f"📁 {name}", callback_data=f"nav_d_{i}")])
        else:
            size = item.stat().st_size
            size_str = f"{size // 1024}KB" if size >= 1024 else f"{size}B"
            keyboard.append([InlineKeyboardButton(f"📄 {name} ({size_str})", callback_data=f"nav_f_{i}")])

    await message.reply_text(
        f"📂 <code>{path}</code>\n{len(items)} items",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    query = update.callback_query
    await query.answer()
    data = query.data
    current = Path(context.user_data.get('browse_dir', str(Path.home())))
    items = context.user_data.get('browse_items', {})

    if data == 'nav_up':
        await _show_dir(query.message, context, current.parent)
    elif data.startswith('nav_d_'):
        idx = int(data.split('_')[2])
        new_path = Path(items.get(idx, str(current)))
        await _show_dir(query.message, context, new_path)
    elif data.startswith('nav_f_'):
        idx = int(data.split('_')[2])
        file_path = Path(items.get(idx, ''))
        if not file_path.exists():
            await query.edit_message_text("File no longer exists.")
            return
        await query.message.reply_document(
            document=open(file_path, 'rb'),
            filename=file_path.name
        )


async def download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /download <path>")
        return
    path = Path(' '.join(context.args))
    if not path.exists():
        await update.message.reply_text(f"File not found: {path}")
        return
    if path.is_dir():
        await update.message.reply_text("Path is a directory. Use /files to browse.")
        return
    await update.message.reply_document(document=open(path, 'rb'), filename=path.name)


async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    reply = update.message.reply_to_message
    doc = (reply.document or reply.photo[-1] if reply and (reply.document or reply.photo) else None)
    if doc is None:
        await update.message.reply_text(
            "Reply to a file with /upload [path] to save it.\n"
            f"Default save path: {UPLOAD_DEFAULT_PATH}"
        )
        return
    dest_dir = Path(' '.join(context.args)) if context.args else Path(UPLOAD_DEFAULT_PATH)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = getattr(doc, 'file_name', None) or f"upload_{doc.file_unique_id}"
    dest = dest_dir / filename
    file_obj = await context.bot.get_file(doc.file_id)
    await file_obj.download_to_drive(str(dest))
    await update.message.reply_text(f"✅ Saved to {dest}")


def register_files_handlers(app) -> None:
    app.add_handler(CommandHandler("files",    files))
    app.add_handler(CommandHandler("download", download))
    app.add_handler(CommandHandler("upload",   upload))
    app.add_handler(CallbackQueryHandler(nav_callback, pattern="^nav_"))
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -m pytest tests/test_files_handlers.py -v 2>&1
```

Expected: 4 passed.

---

## Task 5: Create `bot/handlers/clipboard.py`

**Files:**
- Create: `bot/handlers/clipboard.py`
- Create: `tests/test_clipboard_handlers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_clipboard_handlers.py`:

```python
import pytest, os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('ALLOWED_USER_ID', '12345')


@pytest.fixture
def auth_update():
    u = MagicMock()
    u.effective_user.id = 12345
    u.effective_chat.id = 12345
    u.message.reply_text = AsyncMock()
    u.message.text = '/clip get'
    u.message.reply_to_message = None
    return u


@pytest.fixture
def ctx():
    c = MagicMock()
    c.args = ['get']
    return c


@pytest.mark.asyncio
async def test_clip_get_sends_clipboard_content(auth_update, ctx):
    ctx.args = ['get']
    with patch("pyperclip.paste", return_value="hello world"):
        from bot.handlers.clipboard import clip
        await clip(auth_update, ctx)
        auth_update.message.reply_text.assert_called_once()
        assert "hello world" in auth_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_clip_get_empty_clipboard(auth_update, ctx):
    ctx.args = ['get']
    with patch("pyperclip.paste", return_value=""):
        from bot.handlers.clipboard import clip
        await clip(auth_update, ctx)
        auth_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_clip_set_requires_reply(auth_update, ctx):
    ctx.args = ['set']
    auth_update.message.reply_to_message = None
    from bot.handlers.clipboard import clip
    await clip(auth_update, ctx)
    auth_update.message.reply_text.assert_called_once()
    assert "reply" in auth_update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_clip_set_copies_text(auth_update, ctx):
    ctx.args = ['set']
    reply = MagicMock()
    reply.text = "copied text"
    auth_update.message.reply_to_message = reply
    with patch("pyperclip.copy") as mock_copy:
        from bot.handlers.clipboard import clip
        await clip(auth_update, ctx)
        mock_copy.assert_called_once_with("copied text")
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -m pytest tests/test_clipboard_handlers.py -v 2>&1 | head -20
```

- [ ] **Step 3: Create `bot/handlers/clipboard.py`**

```python
import pyperclip
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized


async def clip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    sub = (context.args or ['get'])[0].lower()

    if sub == 'get':
        content = pyperclip.paste()
        if not content:
            await update.message.reply_text("Clipboard is empty.")
        else:
            await update.message.reply_text(f"📋 Clipboard:\n{content}")

    elif sub == 'set':
        reply = update.message.reply_to_message
        if reply is None or not reply.text:
            await update.message.reply_text(
                "Reply to a text message with /clip set to copy it to PC clipboard."
            )
            return
        pyperclip.copy(reply.text)
        await update.message.reply_text("✅ Copied to PC clipboard.")

    else:
        await update.message.reply_text("Usage: /clip get  |  reply to message with /clip set")


def register_clipboard_handlers(app) -> None:
    app.add_handler(CommandHandler("clip", clip))
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -m pytest tests/test_clipboard_handlers.py -v 2>&1
```

Expected: 4 passed.

---

## Task 6: Create `bot/handlers/media.py`

**Files:**
- Create: `bot/handlers/media.py`

No unit tests — pynput media key simulation is hardware-level with no meaningful mock surface. Manual test instructions provided.

- [ ] **Step 1: Create `bot/handlers/media.py`**

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from utils.windows_utils import press_media_key, get_volume

_MEDIA_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("⏮", callback_data="media_prev"),
        InlineKeyboardButton("⏯", callback_data="media_play_pause"),
        InlineKeyboardButton("⏭", callback_data="media_next"),
    ],
    [
        InlineKeyboardButton("🔉", callback_data="media_vol_down"),
        InlineKeyboardButton("🔇", callback_data="media_mute"),
        InlineKeyboardButton("🔊", callback_data="media_vol_up"),
    ],
])

_ACTION_MAP = {
    'media_prev':       'prev',
    'media_play_pause': 'play_pause',
    'media_next':       'next',
    'media_vol_down':   'vol_down',
    'media_mute':       'mute',
    'media_vol_up':     'vol_up',
}


async def media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    try:
        vol = get_volume()
        caption = f"🎵 Media Control  |  🔊 {vol:.0f}%"
    except Exception:
        caption = "🎵 Media Control"
    await update.message.reply_text(caption, reply_markup=_MEDIA_KEYBOARD)


async def media_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    query = update.callback_query
    await query.answer()
    action = _ACTION_MAP.get(query.data)
    if action is None:
        return
    try:
        press_media_key(action)
        try:
            vol = get_volume()
            caption = f"🎵 Media Control  |  🔊 {vol:.0f}%"
        except Exception:
            caption = "🎵 Media Control"
        await query.edit_message_text(caption, reply_markup=_MEDIA_KEYBOARD)
    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)


def register_media_handlers(app) -> None:
    app.add_handler(CommandHandler("media", media))
    app.add_handler(CallbackQueryHandler(media_callback, pattern="^media_"))
```

- [ ] **Step 2: Verify import**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -c "from bot.handlers.media import register_media_handlers; print('ok')"
```

- [ ] **Manual test** — after full wiring in Task 8, send `/media` to the bot. Buttons should appear. Press ⏯ while music plays — it should pause/play.

---

## Task 7: Create `bot/handlers/misc.py`

**Files:**
- Create: `bot/handlers/misc.py`
- Create: `tests/test_misc_handlers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_misc_handlers.py`:

```python
import pytest, os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('ALLOWED_USER_ID', '12345')
os.environ.setdefault('FOCUS_BLOCKLIST', 'notepad,calc')


@pytest.fixture
def auth_update():
    u = MagicMock()
    u.effective_user.id = 12345
    u.effective_chat.id = 12345
    u.message.reply_text = AsyncMock()
    return u


@pytest.fixture
def ctx():
    c = MagicMock()
    c.args = []
    c.job_queue = MagicMock()
    c.job_queue.run_once = MagicMock()
    return c


@pytest.mark.asyncio
async def test_volume_no_args_shows_current(auth_update, ctx):
    ctx.args = []
    with patch("bot.handlers.misc.get_volume", return_value=50.0):
        from bot.handlers.misc import volume
        await volume(auth_update, ctx)
        auth_update.message.reply_text.assert_called_once()
        assert "50" in auth_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_volume_set_number(auth_update, ctx):
    ctx.args = ['75']
    with patch("bot.handlers.misc.set_volume") as mock_set, \
         patch("bot.handlers.misc.get_volume", return_value=75.0):
        from bot.handlers.misc import volume
        await volume(auth_update, ctx)
        mock_set.assert_called_once_with(75)


@pytest.mark.asyncio
async def test_launch_no_args_sends_usage(auth_update, ctx):
    ctx.args = []
    from bot.handlers.misc import launch
    await launch(auth_update, ctx)
    auth_update.message.reply_text.assert_called_once()
    assert "usage" in auth_update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_launch_finds_app(auth_update, ctx):
    ctx.args = ['calc']
    fake_apps = [('Calculator', 'C:\\calc.lnk'), ('Notepad', 'C:\\notepad.lnk')]
    with patch("bot.handlers.misc.list_apps", return_value=fake_apps), \
         patch("bot.handlers.misc.launch_app") as mock_launch:
        from bot.handlers.misc import launch
        await launch(auth_update, ctx)
        mock_launch.assert_called_once()


@pytest.mark.asyncio
async def test_focus_no_args_defaults_25(auth_update, ctx):
    ctx.args = []
    with patch("psutil.process_iter", return_value=[]):
        from bot.handlers.misc import focus
        await focus(auth_update, ctx)
        auth_update.message.reply_text.assert_called_once()
        assert "25" in auth_update.message.reply_text.call_args[0][0]
        ctx.job_queue.run_once.assert_called_once()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -m pytest tests/test_misc_handlers.py -v 2>&1 | head -20
```

- [ ] **Step 3: Create `bot/handlers/misc.py`**

```python
import os

import psutil
from rapidfuzz import fuzz, process
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from utils.windows_utils import get_volume, set_volume, mute_toggle, list_apps, launch_app

FOCUS_BLOCKLIST = [x.strip().lower() for x in os.getenv('FOCUS_BLOCKLIST', '').split(',') if x.strip()]


async def volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        vol = get_volume()
        await update.message.reply_text(f"🔊 Volume: {vol:.0f}%")
        return

    arg = context.args[0].lower()
    try:
        if arg == 'up':
            current = get_volume()
            set_volume(min(100, int(current) + 10))
        elif arg == 'down':
            current = get_volume()
            set_volume(max(0, int(current) - 10))
        elif arg == 'mute':
            mute_toggle()
            await update.message.reply_text("🔇 Toggled mute.")
            return
        else:
            level = int(arg)
            set_volume(level)
        vol = get_volume()
        await update.message.reply_text(f"🔊 Volume set to {vol:.0f}%")
    except ValueError:
        await update.message.reply_text("Usage: /volume <0-100|up|down|mute>")
    except Exception as e:
        await update.message.reply_text(f"Volume error: {e}")


async def launch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /launch <app name>")
        return

    query = ' '.join(context.args)
    apps = list_apps()
    if not apps:
        await update.message.reply_text("No installed apps found.")
        return

    names = [a[0] for a in apps]
    match = process.extractOne(query, names, scorer=fuzz.WRatio)
    if match is None or match[1] < 40:
        await update.message.reply_text(f"No app matching '{query}' found.")
        return

    matched_name, score, idx = match
    app_path = apps[idx][1]
    try:
        launch_app(app_path)
        await update.message.reply_text(f"🚀 Launched {matched_name}")
    except Exception as e:
        await update.message.reply_text(f"Launch failed: {e}")


async def focus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    try:
        minutes = int(context.args[0]) if context.args else 25
    except ValueError:
        await update.message.reply_text("Usage: /focus <minutes>")
        return

    killed = []
    for proc in psutil.process_iter(['name']):
        try:
            pname = (proc.info.get('name') or '').lower().replace('.exe', '')
            if pname in FOCUS_BLOCKLIST:
                proc.kill()
                killed.append(pname)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    chat_id = update.effective_chat.id
    killed_str = f" Closed: {', '.join(set(killed))}." if killed else ""

    async def _done(ctx):
        await ctx.bot.send_message(chat_id, "✅ Focus session complete!")

    context.job_queue.run_once(_done, when=minutes * 60)
    await update.message.reply_text(
        f"🎯 Focus session started — {minutes} minutes.{killed_str}"
    )


def register_misc_handlers(app) -> None:
    app.add_handler(CommandHandler("volume", volume))
    app.add_handler(CommandHandler("launch", launch))
    app.add_handler(CommandHandler("focus",  focus))
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -m pytest tests/test_misc_handlers.py -v 2>&1
```

Expected: 5 passed.

---

## Task 8: Wire All Handlers + Extend Confirm Routing

**Files:**
- Modify: `bot/handlers/core.py`
- Modify: `bot/tele_main.py`

- [ ] **Step 1: READ `bot/handlers/core.py` before editing**

- [ ] **Step 2: Extend `handle_message` in `bot/handlers/core.py`**

Replace the existing `handle_message` function with this version that adds shutdown/restart confirm routing alongside the existing panic routing:

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return

    text = (update.message.text or '').strip().lower()

    # Route "confirm" to whichever action is pending for this chat
    if text == 'confirm':
        from bot.handlers.guardian import panic_confirm, _pending_panic
        from bot.handlers.system import (
            shutdown_confirm, _pending_shutdown,
            restart_confirm, _pending_restart,
        )
        chat_id = update.effective_chat.id
        if chat_id in _pending_panic:
            await panic_confirm(update, context)
            return
        if chat_id in _pending_shutdown:
            await shutdown_confirm(update, context)
            return
        if chat_id in _pending_restart:
            await restart_confirm(update, context)
            return

    if not terminal.is_active():
        await update.message.reply_text("No active session. Use /runp to start Python.")
        return

    code = update.message.text.strip()
    is_continuation = terminal.waiting_for_more
    output, needs_more = terminal.execute(code)
    if not needs_more:
        terminal.add_to_history(code, output, continuation=is_continuation)
    else:
        terminal.add_to_history(code, "", continuation=is_continuation)
    try:
        await update.message.delete()
    except Exception:
        pass
    await context.bot.edit_message_text(
        chat_id=terminal.chat_id,
        message_id=terminal.terminal_message_id,
        text=terminal.render(),
        parse_mode=ParseMode.HTML,
        reply_markup=terminal_keyboard()
    )
```

- [ ] **Step 3: Overwrite `bot/tele_main.py`**

```python
import logging
import os

from dotenv import load_dotenv
from telegram.ext import Application, ApplicationBuilder

from bot.handlers.clipboard import register_clipboard_handlers
from bot.handlers.core import register_core_handlers
from bot.handlers.files import register_files_handlers
from bot.handlers.guardian import register_guardian_handlers
from bot.handlers.media import register_media_handlers
from bot.handlers.misc import register_misc_handlers
from bot.handlers.system import register_system_handlers

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def main() -> None:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Guardian first so /panic has priority over any conflicting command names
    register_guardian_handlers(app)
    register_system_handlers(app)
    register_files_handlers(app)
    register_clipboard_handlers(app)
    register_media_handlers(app)
    register_misc_handlers(app)
    # Core last — its MessageHandler catch-all must be registered after all CommandHandlers
    register_core_handlers(app)

    app.run_polling()


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Verify all imports are clean**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -c "from bot.tele_main import main; print('import ok')"
```

- [ ] **Step 5: Run full test suite**

```bash
cd C:\Users\Bhavye\Desktop\UniController && python -m pytest tests/ -v 2>&1
```

Expected: all tests pass (16 from Plan 1 + new ones from Plan 2).

---

## Self-Review Checklist

- [x] `/sysinfo` — Task 3 ✓
- [x] `/ps` with inline Kill buttons — Task 3 ✓
- [x] `/kill <pid|name>` — Task 3 ✓
- [x] `/lock` — Task 3 ✓
- [x] `/shutdown` + confirmation — Task 3 + Task 8 ✓
- [x] `/restart` + confirmation — Task 3 + Task 8 ✓
- [x] `/files` inline browser with navigation — Task 4 ✓
- [x] `/download <path>` — Task 4 ✓
- [x] `/upload` via file reply — Task 4 ✓
- [x] `/clip get` + `/clip set` — Task 5 ✓
- [x] `/media` inline panel with play/pause/next/prev/vol — Task 6 ✓
- [x] `/volume` with level/up/down/mute — Task 7 ✓
- [x] `/launch <query>` fuzzy search — Task 7 ✓
- [x] `/focus <minutes>` with blocklist + job_queue timer — Task 7 ✓
- [x] Confirm routing unified in handle_message — Task 8 ✓
- [x] All handlers registered in tele_main.py — Task 8 ✓
- [x] `is_authorized` imported from core (no duplication) — all handlers ✓
- [x] Windows API calls (volume, media keys, apps) in windows_utils.py — Task 2 ✓
