import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from utils.windows_utils import get_nowplaying, get_volume, press_media_key

_MEDIA_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("⏮",   callback_data="media_prev"),
        InlineKeyboardButton("⏯",   callback_data="media_play_pause"),
        InlineKeyboardButton("⏭",   callback_data="media_next"),
    ],
    [
        InlineKeyboardButton("vol-", callback_data="media_vol_down"),
        InlineKeyboardButton("mute", callback_data="media_mute"),
        InlineKeyboardButton("vol+", callback_data="media_vol_up"),
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


def _caption(vol: float | None = None) -> str:
    vol_str = f"  vol: {vol:.0f}%" if vol is not None else ""
    return f"<b>MEDIA</b>{vol_str}"


async def media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    try:
        vol = get_volume()
    except Exception:
        vol = None
    await update.message.reply_text(
        _caption(vol), parse_mode=ParseMode.HTML, reply_markup=_MEDIA_KEYBOARD
    )


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
        except Exception:
            vol = None
        await query.edit_message_text(
            _caption(vol), parse_mode=ParseMode.HTML, reply_markup=_MEDIA_KEYBOARD
        )
    except Exception as e:
        await query.answer(f"err: {e}", show_alert=True)


async def nowplaying(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    info = await asyncio.to_thread(get_nowplaying)
    await update.message.reply_text(f"<code>{info}</code>", parse_mode=ParseMode.HTML)


def register_media_handlers(app) -> None:
    app.add_handler(CommandHandler("media",      media))
    app.add_handler(CommandHandler("nowplaying", nowplaying))
    app.add_handler(CallbackQueryHandler(media_callback, pattern="^media_"))
