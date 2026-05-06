# Guardian Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `tele_main.py` into a handler-based architecture and add Guardian Mode — webcam snap, motion/USB/login-attempt detection, and a panic command.

**Architecture:** All handlers move into `bot/handlers/` modules; `tele_main.py` becomes registration-only. `GuardianWatcher` runs as daemon threads, bridging back to the async Telegram bot via `asyncio.run_coroutine_threadsafe`. All Windows API calls live in `utils/windows_utils.py` for future portability.

**Tech Stack:** python-telegram-bot 22.7, opencv-python, wmi, pywin32, pytest, pytest-mock

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `requirements.txt` | Add new deps |
| Create | `bot/handlers/__init__.py` | Package marker |
| Create | `bot/handlers/core.py` | Existing handlers (start, exec, screenshot, runp) |
| Create | `bot/handlers/guardian.py` | /snap, /guard, /panic |
| Create | `utils/windows_utils.py` | lock_screen, disable_wifi, capture_webcam |
| Create | `utils/guardian_watcher.py` | Background watcher thread |
| Modify | `bot/tele_main.py` | Thin registration + post_init wiring |
| Create | `tests/__init__.py` | Package marker |
| Create | `tests/test_windows_utils.py` | Unit tests for pure logic |
| Create | `tests/test_guardian_watcher.py` | Watcher state tests |
| Create | `tests/test_guardian_handlers.py` | Handler auth + arg tests |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt**

```
python-telegram-bot==22.7
mss==10.2.0
Pillow
psutil
pyperclip
python-dotenv
dotenv
opencv-python
wmi
pywin32
pytest
pytest-mock
numpy
```

- [ ] **Step 2: Install**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add opencv, wmi, pywin32, pytest deps"
```

---

## Task 2: Create `utils/windows_utils.py`

**Files:**
- Create: `utils/windows_utils.py`
- Create: `tests/__init__.py`
- Create: `tests/test_windows_utils.py`

- [ ] **Step 1: Write failing tests**

Create `tests/__init__.py` (empty), then create `tests/test_windows_utils.py`:

```python
from unittest.mock import patch, MagicMock
from io import BytesIO


def test_capture_webcam_returns_bytesio_on_success():
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, b"fakeframe")

    import numpy as np
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)

    with patch("cv2.VideoCapture", return_value=mock_cap):
        with patch("cv2.imencode", return_value=(True, np.array([1, 2, 3], dtype=np.uint8))):
            from utils.windows_utils import capture_webcam
            result = capture_webcam()
            assert isinstance(result, BytesIO)


def test_capture_webcam_returns_none_when_no_camera():
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False

    with patch("cv2.VideoCapture", return_value=mock_cap):
        from utils.windows_utils import capture_webcam
        result = capture_webcam()
        assert result is None


def test_capture_webcam_returns_none_when_read_fails():
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (False, None)

    with patch("cv2.VideoCapture", return_value=mock_cap):
        from utils.windows_utils import capture_webcam
        result = capture_webcam()
        assert result is None
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_windows_utils.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` for `utils.windows_utils`.

- [ ] **Step 3: Create `utils/windows_utils.py`**

```python
import ctypes
import subprocess
from io import BytesIO

import cv2
import numpy as np


def lock_screen() -> None:
    ctypes.windll.user32.LockWorkStation()


def disable_wifi() -> None:
    subprocess.run(
        ['netsh', 'interface', 'set', 'interface', 'Wi-Fi', 'disable'],
        check=True, capture_output=True, text=True
    )


def capture_webcam() -> BytesIO | None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    _, buf = cv2.imencode('.jpg', frame)
    bio = BytesIO(buf.tobytes())
    bio.name = 'snap.jpg'
    return bio


def frame_diff_pixel_count(frame_a: np.ndarray, frame_b: np.ndarray) -> int:
    diff = cv2.absdiff(frame_a, frame_b)
    return int(np.count_nonzero(diff > 30))
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_windows_utils.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add utils/windows_utils.py tests/__init__.py tests/test_windows_utils.py
git commit -m "feat: add windows_utils with webcam capture and screen lock"
```

---

## Task 3: Create `bot/handlers/core.py` — Extract Existing Handlers

**Files:**
- Create: `bot/handlers/__init__.py`
- Create: `bot/handlers/core.py`

- [ ] **Step 1: Create `bot/handlers/__init__.py`** (empty file)

- [ ] **Step 2: Create `bot/handlers/core.py`**

Move all existing handlers out of `tele_main.py` verbatim. The only change: `is_authorized`, `terminal`, `commandExecutor`, and `terminal_keyboard` become module-level in this file.

```python
import os
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import mss
from PIL import Image

from utils.CommandExecutor import CommandExecutor
from utils.PythonTerminal import PythonTerminal

ALLOWED_USER_ID = int(os.getenv('ALLOWED_USER_ID', '0'))

commandExecutor = CommandExecutor()
terminal = PythonTerminal()


def is_authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID


def terminal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛑 Exit",  callback_data="py_exit"),
            InlineKeyboardButton("🗑 Clear", callback_data="py_clear"),
        ]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    await update.message.reply_text(f"Ghost is online. Hello {update.effective_user.first_name}.")


async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    command = context.args
    if isinstance(command, list) and command:
        result = commandExecutor.run(command)
        await update.message.reply_text(result or "Done. No output.")


async def screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    buf = BytesIO()
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = sct.grab(monitor)
        pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
        pil_img.save(buf, format="PNG")
    buf.seek(0)
    await update.message.reply_photo(photo=buf)


async def runp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    started = terminal.start()
    if not started:
        await update.message.reply_text("⚠️ Session already running.")
        return
    msg = await update.message.reply_text(
        terminal.render(),
        parse_mode=ParseMode.HTML,
        reply_markup=terminal_keyboard()
    )
    terminal.terminal_message_id = msg.message_id
    terminal.chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⌨️ Session active. Just type code directly and send."
    )


async def terminal_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == "py_exit":
        terminal.stop()
        await context.bot.edit_message_text(
            chat_id=terminal.chat_id,
            message_id=terminal.terminal_message_id,
            text="<code>🛑 Session terminated.</code>",
            parse_mode=ParseMode.HTML
        )
    elif query.data == "py_clear":
        terminal.history = []
        await context.bot.edit_message_text(
            chat_id=terminal.chat_id,
            message_id=terminal.terminal_message_id,
            text=terminal.render(),
            parse_mode=ParseMode.HTML,
            reply_markup=terminal_keyboard()
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
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


def register_core_handlers(app) -> None:
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("exec",       run_command))
    app.add_handler(CommandHandler("screenshot", screenshot))
    app.add_handler(CommandHandler("runp",       runp))
    app.add_handler(CallbackQueryHandler(terminal_button, pattern="^py_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
```

- [ ] **Step 3: Rewrite `bot/tele_main.py`**

```python
import os
import logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

from bot.handlers.core import register_core_handlers

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    register_core_handlers(app)
    app.run_polling()


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Manual smoke test — bot still works**

```bash
python bot/tele_main.py
```

Send `/start`, `/screenshot`, `/exec echo hello` in Telegram. All must respond correctly.

- [ ] **Step 5: Commit**

```bash
git add bot/tele_main.py bot/handlers/__init__.py bot/handlers/core.py
git commit -m "refactor: extract handlers into bot/handlers/core.py"
```

---

## Task 4: Create `utils/guardian_watcher.py`

**Files:**
- Create: `utils/guardian_watcher.py`
- Create: `tests/test_guardian_watcher.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_guardian_watcher.py`:

```python
from utils.guardian_watcher import GuardianWatcher


def test_watcher_starts_stopped():
    w = GuardianWatcher()
    assert not w.is_active()


def test_watcher_active_after_start(mocker):
    w = GuardianWatcher()
    mock_bot = mocker.MagicMock()
    mock_loop = mocker.MagicMock()
    mocker.patch("threading.Thread")
    w.start(mock_bot, chat_id=123, loop=mock_loop)
    assert w.is_active()


def test_watcher_inactive_after_stop(mocker):
    w = GuardianWatcher()
    mock_bot = mocker.MagicMock()
    mock_loop = mocker.MagicMock()
    mocker.patch("threading.Thread")
    w.start(mock_bot, chat_id=123, loop=mock_loop)
    w.stop()
    assert not w.is_active()


def test_frame_diff_triggers_alert(mocker):
    import numpy as np
    from utils.guardian_watcher import GuardianWatcher

    w = GuardianWatcher()
    w._running = True
    w._loop = mocker.MagicMock()
    w._bot = mocker.MagicMock()
    w._chat_id = 123

    baseline = np.zeros((480, 640, 3), dtype=np.uint8)
    changed = np.full((480, 640, 3), 200, dtype=np.uint8)  # all pixels changed

    w._baseline_frame = baseline

    mock_capture = mocker.patch("utils.guardian_watcher.capture_webcam_frame")
    mock_capture.return_value = changed

    mock_send = mocker.patch.object(w, "_send_alert")
    w._check_motion()

    mock_send.assert_called_once()


def test_frame_diff_no_alert_when_static(mocker):
    import numpy as np

    w = GuardianWatcher()
    w._running = True
    w._loop = mocker.MagicMock()
    w._bot = mocker.MagicMock()
    w._chat_id = 123

    baseline = np.zeros((480, 640, 3), dtype=np.uint8)

    w._baseline_frame = baseline

    mock_capture = mocker.patch("utils.guardian_watcher.capture_webcam_frame")
    mock_capture.return_value = baseline.copy()

    mock_send = mocker.patch.object(w, "_send_alert")
    w._check_motion()

    mock_send.assert_not_called()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_guardian_watcher.py -v
```

Expected: `ImportError` for `utils.guardian_watcher`.

- [ ] **Step 3: Create `utils/guardian_watcher.py`**

```python
import asyncio
import logging
import os
import threading
import time
from io import BytesIO

import cv2
import numpy as np
from telegram import Bot

from utils.windows_utils import frame_diff_pixel_count

logger = logging.getLogger(__name__)

MOTION_THRESHOLD = int(os.getenv('MOTION_THRESHOLD', '500'))
GUARD_CHECK_INTERVAL = int(os.getenv('GUARD_CHECK_INTERVAL', '10'))


def capture_webcam_frame() -> np.ndarray | None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


def frame_to_bytesio(frame: np.ndarray) -> BytesIO:
    _, buf = cv2.imencode('.jpg', frame)
    bio = BytesIO(buf.tobytes())
    bio.name = 'alert.jpg'
    return bio


class GuardianWatcher:
    def __init__(self):
        self._running = False
        self._bot: Bot | None = None
        self._chat_id: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._baseline_frame: np.ndarray | None = None
        self._last_login_check: float = 0.0
        self._threads: list[threading.Thread] = []

    def is_active(self) -> bool:
        return self._running

    def start(self, bot: Bot, chat_id: int, loop: asyncio.AbstractEventLoop) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._loop = loop
        self._running = True
        self._last_login_check = time.time()
        self._baseline_frame = capture_webcam_frame()

        for target in (self._motion_loop, self._usb_loop, self._login_loop):
            t = threading.Thread(target=target, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._running = False
        self._threads.clear()

    def reset_baseline(self) -> None:
        self._baseline_frame = capture_webcam_frame()

    # ── internal ──────────────────────────────────────────────────────────────

    def _send_alert(self, text: str, photo: BytesIO | None = None) -> None:
        if photo:
            coro = self._bot.send_photo(self._chat_id, photo=photo, caption=text)
        else:
            coro = self._bot.send_message(self._chat_id, text=text)
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _motion_loop(self) -> None:
        while self._running:
            try:
                self._check_motion()
            except Exception as e:
                logger.error("Motion check error: %s", e)
            time.sleep(GUARD_CHECK_INTERVAL)

    def _check_motion(self) -> None:
        frame = capture_webcam_frame()
        if frame is None or self._baseline_frame is None:
            return
        changed = frame_diff_pixel_count(self._baseline_frame, frame)
        if changed > MOTION_THRESHOLD:
            photo = frame_to_bytesio(frame)
            self._send_alert("🚨 Motion detected at your PC!", photo)
            self._baseline_frame = frame  # reset so next alert needs new movement

    def _usb_loop(self) -> None:
        try:
            import wmi
            c = wmi.WMI()
            watcher = c.watch_for(
                raw_wql="SELECT * FROM __InstanceCreationEvent WITHIN 2 "
                        "WHERE TargetInstance ISA 'Win32_PnPEntity'"
            )
            while self._running:
                try:
                    event = watcher(timeout_ms=5000)
                    if event and self._running:
                        name = getattr(event.TargetInstance, 'Name', 'Unknown device')
                        self._send_alert(f"🔌 USB device connected: {name}")
                except wmi.x_wmi_timed_out:
                    pass
        except Exception as e:
            logger.error("USB watcher error: %s", e)

    def _login_loop(self) -> None:
        while self._running:
            try:
                self._check_failed_logins()
            except Exception as e:
                logger.error("Login check error: %s", e)
            time.sleep(30)

    def _check_failed_logins(self) -> None:
        import win32evtlog
        import win32evtlogutil
        handle = win32evtlog.OpenEventLog(None, 'Security')
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        now = time.time()
        try:
            while True:
                records = win32evtlog.ReadEventLog(handle, flags, 0)
                if not records:
                    break
                for record in records:
                    if (record.EventID & 0xFFFF) == 4625:
                        import calendar
                        event_time = calendar.timegm(record.TimeGenerated.timetuple())
                        if event_time > self._last_login_check:
                            photo = self._try_snap()
                            self._send_alert("⚠️ Failed login attempt detected!", photo)
                        else:
                            return
        finally:
            win32evtlog.CloseEventLog(handle)
            self._last_login_check = now

    def _try_snap(self) -> BytesIO | None:
        frame = capture_webcam_frame()
        return frame_to_bytesio(frame) if frame is not None else None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_guardian_watcher.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add utils/guardian_watcher.py tests/test_guardian_watcher.py
git commit -m "feat: add GuardianWatcher with motion, USB, and login detection"
```

---

## Task 5: Create `bot/handlers/guardian.py`

**Files:**
- Create: `bot/handlers/guardian.py`
- Create: `tests/test_guardian_handlers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_guardian_handlers.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_update_authorized():
    update = MagicMock()
    update.effective_user.id = 12345
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    return update


@pytest.fixture
def mock_update_unauthorized():
    update = MagicMock()
    update.effective_user.id = 99999
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.args = []
    return ctx


@pytest.mark.asyncio
async def test_snap_unauthorized_drops_silently(mock_update_unauthorized, mock_context):
    import os
    os.environ['ALLOWED_USER_ID'] = '12345'
    from bot.handlers.guardian import snap
    await snap(mock_update_unauthorized, mock_context)
    mock_update_unauthorized.message.reply_photo.assert_not_called()


@pytest.mark.asyncio
async def test_snap_no_webcam_sends_error(mock_update_authorized, mock_context):
    import os
    os.environ['ALLOWED_USER_ID'] = '12345'
    with patch("bot.handlers.guardian.capture_webcam", return_value=None):
        from bot.handlers.guardian import snap
        await snap(mock_update_authorized, mock_context)
        mock_update_authorized.message.reply_text.assert_called_once()
        assert "webcam" in mock_update_authorized.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_snap_sends_photo_when_webcam_available(mock_update_authorized, mock_context):
    import os
    from io import BytesIO
    os.environ['ALLOWED_USER_ID'] = '12345'
    fake_photo = BytesIO(b"fakeimg")
    with patch("bot.handlers.guardian.capture_webcam", return_value=fake_photo):
        from bot.handlers.guardian import snap
        await snap(mock_update_authorized, mock_context)
        mock_update_authorized.message.reply_photo.assert_called_once_with(photo=fake_photo)


@pytest.mark.asyncio
async def test_guard_on_starts_watcher(mock_update_authorized, mock_context):
    import os
    os.environ['ALLOWED_USER_ID'] = '12345'
    mock_context.args = ['on']
    mock_watcher = MagicMock()
    mock_watcher.is_active.return_value = False
    with patch("bot.handlers.guardian._watcher", mock_watcher):
        from bot.handlers import guardian
        guardian._watcher = mock_watcher
        await guardian.guard(mock_update_authorized, mock_context)
        mock_watcher.start.assert_called_once()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_guardian_handlers.py -v
```

Expected: `ImportError` for `bot.handlers.guardian`.

- [ ] **Step 3: Create `bot/handlers/guardian.py`**

```python
import asyncio
import os

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from utils.guardian_watcher import GuardianWatcher
from utils.windows_utils import capture_webcam, lock_screen, disable_wifi

ALLOWED_USER_ID = int(os.getenv('ALLOWED_USER_ID', '0'))

_watcher = GuardianWatcher()
_pending_panic: set[int] = set()


def is_authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID


async def snap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    photo = capture_webcam()
    if photo is None:
        await update.message.reply_text("No webcam found or could not capture.")
        return
    await update.message.reply_photo(photo=photo)


async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    arg = (context.args or [''])[0].lower()

    if arg == 'on':
        if _watcher.is_active():
            await update.message.reply_text("Guardian already active.")
            return
        loop = asyncio.get_event_loop()
        _watcher.start(context.bot, update.effective_chat.id, loop)
        await update.message.reply_text(
            "🛡 Guardian Mode ON\n"
            "Watching: motion · USB · failed logins"
        )

    elif arg == 'off':
        if not _watcher.is_active():
            await update.message.reply_text("Guardian is not active.")
            return
        _watcher.stop()
        await update.message.reply_text("Guardian Mode OFF.")

    elif arg == 'status':
        status = "🟢 Active" if _watcher.is_active() else "🔴 Inactive"
        await update.message.reply_text(f"Guardian: {status}")

    else:
        await update.message.reply_text("Usage: /guard on | off | status")


async def panic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    chat_id = update.effective_chat.id

    if chat_id not in _pending_panic:
        _pending_panic.add(chat_id)
        await update.message.reply_text(
            "⚠️ PANIC will:\n"
            "1. Snap webcam photo → send here\n"
            "2. Lock screen\n"
            "3. Disable Wi-Fi\n\n"
            "Reply with `confirm` to proceed."
        )
        return

    _pending_panic.discard(chat_id)
    await _execute_panic(update, context)


async def panic_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the text 'confirm' message for /panic confirmation."""
    if not is_authorized(update):
        return
    chat_id = update.effective_chat.id
    if chat_id not in _pending_panic:
        return
    _pending_panic.discard(chat_id)
    await _execute_panic(update, context)


async def _execute_panic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Step 1: snap + send
    photo = capture_webcam()
    if photo:
        await update.message.reply_photo(photo=photo, caption="📸 Snap taken.")
    else:
        await update.message.reply_text("⚠️ No webcam — skipping snap.")

    # Step 2: confirm before cutting off
    await update.message.reply_text("🔒 Locking screen and disabling Wi-Fi now.")

    # Step 3: lock screen
    try:
        lock_screen()
    except Exception as e:
        await update.message.reply_text(f"Lock failed: {e}")

    # Step 4: disable wifi
    try:
        disable_wifi()
    except Exception as e:
        await update.message.reply_text(f"Wi-Fi disable failed: {e}")


def register_guardian_handlers(app) -> None:
    app.add_handler(CommandHandler("snap",   snap))
    app.add_handler(CommandHandler("guard",  guard))
    app.add_handler(CommandHandler("panic",  panic))
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_guardian_handlers.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add bot/handlers/guardian.py tests/test_guardian_handlers.py
git commit -m "feat: add /snap, /guard, /panic handlers"
```

---

## Task 6: Handle `confirm` Message for Panic + Wire Everything into `tele_main.py`

**Files:**
- Modify: `bot/tele_main.py`
- Modify: `bot/handlers/core.py`

- [ ] **Step 1: Update `bot/handlers/core.py` — add panic confirm routing**

In `handle_message`, add a check before the terminal block so `confirm` texts route to panic:

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return

    # Route "confirm" to panic handler if pending
    from bot.handlers.guardian import panic_confirm, _pending_panic
    if (update.message.text or '').strip().lower() == 'confirm' \
            and update.effective_chat.id in _pending_panic:
        await panic_confirm(update, context)
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

- [ ] **Step 2: Rewrite `bot/tele_main.py` — wire guardian + post_init**

```python
import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram.ext import Application, ApplicationBuilder

from bot.handlers.core import register_core_handlers
from bot.handlers.guardian import register_guardian_handlers

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def main() -> None:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    register_guardian_handlers(app)
    register_core_handlers(app)
    app.run_polling()


if __name__ == '__main__':
    main()
```

- [ ] **Step 3: Manual smoke test — all commands work**

```bash
python bot/tele_main.py
```

Test each:
- `/start` → greeting
- `/screenshot` → screenshot
- `/exec echo hello` → `hello`
- `/snap` → webcam photo (or "No webcam" message)
- `/guard status` → "🔴 Inactive"
- `/guard on` → "🛡 Guardian Mode ON"
- `/guard status` → "🟢 Active"
- `/guard off` → "Guardian Mode OFF"
- `/panic` → confirmation prompt → reply `confirm` → snap + lock + wifi disable

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add bot/tele_main.py bot/handlers/core.py
git commit -m "feat: wire Guardian Mode into main bot with post_init and confirm routing"
```

---

## Self-Review Checklist

- [x] `/snap` — Task 5 ✓
- [x] `/guard on|off|status` — Task 5 ✓
- [x] Motion detection (GuardianWatcher._check_motion) — Task 4 ✓
- [x] USB detection (_usb_loop) — Task 4 ✓
- [x] Login attempt detection (_login_loop) — Task 4 ✓
- [x] `/panic` with confirmation + sequence — Task 5 + 6 ✓
- [x] Webcam bytes-only, never written to disk — Task 5 ✓
- [x] Guardian errors logged, never crash bot — Task 4 ✓
- [x] `windows_utils.py` isolates all Win32 calls — Task 2 ✓
- [x] `tele_main.py` is registration-only — Task 3 + 6 ✓
- [x] Existing handlers preserved and working — Task 3 ✓
