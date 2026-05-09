import asyncio
import collections
import threading
import time

import pyperclip
from telegram import Update
from telegram.constants import ParseMode
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


def _escape(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


async def clip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    args = context.args or []
    sub = args[0].lower() if args else 'get'

    if sub == 'get':
        content = await asyncio.to_thread(pyperclip.paste)
        if not content:
            await update.message.reply_text("clipboard is empty.")
        else:
            await update.message.reply_text(
                f"<b>CLIPBOARD</b>\n\n{_escape(content[:1000])}",
                parse_mode=ParseMode.HTML
            )

    elif sub == 'set':
        if len(args) > 1:
            await asyncio.to_thread(pyperclip.copy, ' '.join(args[1:]))
            await update.message.reply_text("copied.")
            return
        reply = update.message.reply_to_message
        if reply and reply.text:
            await asyncio.to_thread(pyperclip.copy, reply.text)
            await update.message.reply_text("copied.")
        else:
            await update.message.reply_text(
                "/clip set &lt;text&gt;  — or reply to any message with /clip set",
                parse_mode=ParseMode.HTML
            )

    elif sub == 'history':
        with _lock:
            items = list(_history)
        if not items:
            await update.message.reply_text("no clipboard history yet.")
            return
        lines = [f"<b>CLIPBOARD HISTORY</b>  ({len(items)} items)\n"]
        for i, (text, ts) in enumerate(items, 1):
            preview = _escape(text[:60])
            if len(text) > 60:
                preview += "..."
            lines.append(f"{i}.  {_ago(ts)}\n    {preview}\n")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    else:
        await update.message.reply_text(
            "/clip — read clipboard\n"
            "/clip set &lt;text&gt; — write to clipboard\n"
            "/clip history — last 10 items",
            parse_mode=ParseMode.HTML
        )


def register_clipboard_handlers(app) -> None:
    app.add_handler(CommandHandler("clip", clip))
