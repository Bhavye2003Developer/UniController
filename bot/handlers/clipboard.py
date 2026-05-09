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
        return "now"
    if secs < 3600:
        return f"{secs // 60}m"
    return f"{secs // 3600}h"


async def clip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    args = context.args or []
    sub = args[0].lower() if args else 'get'

    if sub == 'get':
        content = pyperclip.paste()
        if not content:
            await update.message.reply_text("clipboard empty.")
        else:
            safe = content[:1000].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            await update.message.reply_text(
                f"<b>CLIP</b>\n<pre>{safe}</pre>", parse_mode=ParseMode.HTML
            )

    elif sub == 'set':
        if len(args) > 1:
            pyperclip.copy(' '.join(args[1:]))
            await update.message.reply_text("copied.")
            return
        reply = update.message.reply_to_message
        if reply and reply.text:
            pyperclip.copy(reply.text)
            await update.message.reply_text("copied.")
        else:
            await update.message.reply_text("usage: /clip set &lt;text&gt;  or reply to a message with /clip set", parse_mode=ParseMode.HTML)

    elif sub == 'history':
        with _lock:
            items = list(_history)
        if not items:
            await update.message.reply_text("no clipboard history yet.")
            return
        lines = [f"<b>CLIPBOARD</b>  {len(items)} items\n<pre>"]
        for i, (text, ts) in enumerate(items, 1):
            preview = text[:55].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            if len(text) > 55:
                preview += "..."
            lines.append(f"{i:2}.  {_ago(ts):<4}  {preview}")
        lines.append("</pre>")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    else:
        await update.message.reply_text("usage: /clip get | set | history")


def register_clipboard_handlers(app) -> None:
    app.add_handler(CommandHandler("clip", clip))
