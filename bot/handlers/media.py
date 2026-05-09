from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import asyncio

from bot.handlers.core import is_authorized
from utils.windows_utils import get_nowplaying, get_volume, press_media_key

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


async def nowplaying(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    info = await asyncio.to_thread(get_nowplaying)
    await update.message.reply_text(f"🎵 {info}")


def register_media_handlers(app) -> None:
    app.add_handler(CommandHandler("media",      media))
    app.add_handler(CommandHandler("nowplaying", nowplaying))
    app.add_handler(CallbackQueryHandler(media_callback, pattern="^media_"))
