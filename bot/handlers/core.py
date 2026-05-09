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


HELP_TEXT = """<b>UNICONTROLLER</b>

<b>CORE</b>
/exec &lt;cmd&gt; - run shell command
/screenshot - capture screen(s)
/runp - interactive python REPL

<b>SYSTEM</b>
/sysinfo - cpu, ram, disk, uptime
/ps - processes by cpu
/kill &lt;pid|name&gt; - kill process
/lock - lock screen
/shutdown - power off
/restart - reboot
/activewindow - focused window info
/powerplan - power plan control
/windows - window manager

<b>FILES</b>
/files - browse filesystem
/download - file browser or send file
/upload - save file from chat
/print - print doc (reply to file)
/cleanup - scan and delete junk
/search &lt;pattern&gt; - search file contents

<b>CLIPBOARD</b>
/clip - get, set, or history

<b>MEDIA</b>
/media - media control panel
/volume - get or set volume
/nowplaying - current track

<b>APPS</b>
/launch &lt;name&gt; - open app by name
/focus - block distractions
/type &lt;text&gt; - type into active window
/speedtest - internet speed

<b>SCHEDULER</b>
/schedule &lt;time&gt; &lt;cmd&gt; - schedule a command
/babysit &lt;cmd&gt; - watch a process
/wake &lt;mac&gt; - wake-on-LAN

<b>NETWORK</b>
/netstat - active connections by process
/lan - scan LAN for devices

<b>REMOTE</b>
/next - next slide
/prev - prev slide
/fullscreen - F5
/escape - esc
/openurl &lt;url&gt; - open in browser
/closetab - ctrl+w

<b>NOTEPAD</b>
/note &lt;text&gt; - add note
/notes - list notes

<b>WATCHERS</b>
/watch &lt;rule&gt; - add watch rule
/watches - list active rules
/unwatch &lt;id&gt; - remove rule

<b>REPORTS</b>
/report - now, on HH:MM, or off

<b>TIMELAPSE</b>
/timelapse &lt;duration&gt; - record screen GIF
/stream - burst capture GIF
/stage &lt;path&gt; - upload for offline access

<b>DAEMON</b>
/daemon - install, uninstall, or status

<b>GUARDIAN</b>
/snap - webcam snapshot
/guard - motion and USB alerts
/panic - emergency lockdown"""


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    await update.message.reply_text(
        f"<code>ghost@pc</code>  online  hi {update.effective_user.first_name}\n/help for commands.",
        parse_mode=ParseMode.HTML
    )


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
    arg = (context.args[0].lower() if context.args else '1')
    buf = BytesIO()
    with mss.mss() as sct:
        if arg == 'all':
            monitor = sct.monitors[0]
        else:
            try:
                idx = int(arg)
            except ValueError:
                idx = 1
            if idx < 1 or idx >= len(sct.monitors):
                await update.message.reply_text(
                    f"Monitor {idx} not found. Available: 1–{len(sct.monitors) - 1}"
                )
                return
            monitor = sct.monitors[idx]
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

    from utils import session as _session
    idle = _session.touch()
    if idle > 1800:
        from bot.handlers.report import send_session_summary
        import asyncio
        asyncio.create_task(
            send_session_summary(context.bot, update.effective_chat.id, idle)
        )

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


def register_core_handlers(app) -> None:
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("help",       help_cmd))
    app.add_handler(CommandHandler("exec",       run_command))
    app.add_handler(CommandHandler("screenshot", screenshot))
    app.add_handler(CommandHandler("runp",       runp))
    app.add_handler(CallbackQueryHandler(terminal_button, pattern="^py_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
