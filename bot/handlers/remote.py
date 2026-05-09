import webbrowser

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from utils.windows_utils import hotkey, press_key


async def openurl_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /openurl <url>")
        return
    url = context.args[0]
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    webbrowser.open(url)
    await update.message.reply_text(f"🌐 Opened: {url}")


async def next_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    press_key('right')
    await update.message.reply_text("⏭ Next")


async def prev_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    press_key('left')
    await update.message.reply_text("⏮ Prev")


async def fullscreen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    press_key('f5')
    await update.message.reply_text("🖥 Fullscreen (F5)")


async def escape_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    press_key('escape')
    await update.message.reply_text("⎋ Escape")


async def closetab_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    hotkey('ctrl', 'w')
    await update.message.reply_text("✕ Closed tab (Ctrl+W)")


def register_remote_handlers(app) -> None:
    app.add_handler(CommandHandler("openurl",   openurl_cmd))
    app.add_handler(CommandHandler("next",      next_cmd))
    app.add_handler(CommandHandler("prev",      prev_cmd))
    app.add_handler(CommandHandler("fullscreen", fullscreen_cmd))
    app.add_handler(CommandHandler("escape",    escape_cmd))
    app.add_handler(CommandHandler("closetab",  closetab_cmd))
