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
