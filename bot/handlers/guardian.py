import asyncio

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler

from bot.handlers.core import is_authorized
from utils.guardian_watcher import GuardianWatcher
from utils.windows_utils import capture_webcam, lock_screen, disable_wifi

_watcher = GuardianWatcher()
_pending_panic: set[int] = set()


async def snap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    photo = capture_webcam()
    if photo is None:
        await update.message.reply_text("❌ No webcam found or capture failed.")
        return
    await update.message.reply_photo(photo=photo)


async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    arg = (context.args or [''])[0].lower()

    if arg == 'on':
        if _watcher.is_active():
            await update.message.reply_text("🛡 Guard is already active.")
            return
        loop = asyncio.get_running_loop()
        _watcher.start(context.bot, update.effective_chat.id, loop)
        await update.message.reply_text("🛡 <b>Guard ON</b>  —  watching for motion, USB, and logins.", parse_mode=ParseMode.HTML)

    elif arg == 'off':
        if not _watcher.is_active():
            await update.message.reply_text("🛡 Guard is not active.")
            return
        _watcher.stop()
        await update.message.reply_text("🛡 Guard OFF.")

    elif arg == 'status':
        if _watcher.is_active():
            await update.message.reply_text("🛡 Guard is <b>active</b>.", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("🛡 Guard is <b>inactive</b>.", parse_mode=ParseMode.HTML)

    else:
        await update.message.reply_text("usage: /guard on | off | status")


async def panic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    chat_id = update.effective_chat.id

    if chat_id not in _pending_panic:
        _pending_panic.add(chat_id)
        await update.message.reply_text(
            "🚨 <b>PANIC MODE</b>\n\n"
            "This will:\n"
            "  📸  Snap webcam photo\n"
            "  🔒  Lock the screen\n"
            "  📵  Disable Wi-Fi\n\n"
            "Type <code>confirm</code> to proceed.",
            parse_mode=ParseMode.HTML
        )
        return

    _pending_panic.discard(chat_id)
    await _execute_panic(update, context)


async def panic_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    chat_id = update.effective_chat.id
    if chat_id not in _pending_panic:
        return
    _pending_panic.discard(chat_id)
    await _execute_panic(update, context)


async def _execute_panic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    photo = capture_webcam()
    if photo:
        await update.message.reply_photo(photo=photo, caption="📸 Webcam snap taken.")
    else:
        await update.message.reply_text("⚠️ No webcam — skipping snap.")

    await update.message.reply_text("🔒 Locking screen and disabling Wi-Fi...")

    try:
        lock_screen()
    except Exception as e:
        await update.message.reply_text(f"❌ Lock failed: {e}")

    try:
        disable_wifi()
    except Exception as e:
        await update.message.reply_text(f"❌ Wi-Fi disable failed: {e}")


def register_guardian_handlers(app) -> None:
    app.add_handler(CommandHandler("snap",  snap))
    app.add_handler(CommandHandler("guard", guard))
    app.add_handler(CommandHandler("panic", panic))
