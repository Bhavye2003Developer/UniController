import collections
import threading
import time

import pyperclip
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized

_history: collections.deque = collections.deque(maxlen=10)
_last_clip: str = ""
_lock = threading.Lock()


def _poll():
    global _last_clip
    while True:
        try:
            current = pyperclip.paste()
            if current and current != _last_clip:
                _last_clip = current
                with _lock:
                    _history.appendleft((current, time.time()))
        except Exception:
            pass
        time.sleep(1)


threading.Thread(target=_poll, daemon=True).start()


def _ago(ts: float) -> str:
    secs = int(time.time() - ts)
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    return f"{secs // 3600}h ago"


async def clip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    args = context.args or []
    sub = args[0].lower() if args else 'get'

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

    elif sub == 'history':
        with _lock:
            items = list(_history)
        if not items:
            await update.message.reply_text("No clipboard history yet.")
            return
        lines = ["📋 <b>Clipboard History</b>", ""]
        for i, (text, ts) in enumerate(items, 1):
            preview = text[:60].replace('<', '&lt;').replace('>', '&gt;')
            if len(text) > 60:
                preview += "…"
            lines.append(f"{i}. <code>{preview}</code>  <i>{_ago(ts)}</i>")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    else:
        await update.message.reply_text(
            "Usage: /clip get  |  /clip set (reply)  |  /clip history"
        )


def register_clipboard_handlers(app) -> None:
    app.add_handler(CommandHandler("clip", clip))
