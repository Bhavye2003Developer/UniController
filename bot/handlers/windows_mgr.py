from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from utils.windows_utils import list_open_windows, window_action

# module-level store: index str → hwnd
_handles: dict[str, int] = {}


async def windows_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    wins = [(hwnd, title) for hwnd, title in list_open_windows()][:15]
    _handles.clear()

    lines = ["🪟 <b>Open Windows</b>", ""]
    keyboard = []
    for i, (hwnd, title) in enumerate(wins):
        _handles[str(i)] = hwnd
        lines.append(f"{i + 1}. {title[:50]}")
        keyboard.append([
            InlineKeyboardButton(f"▶ {i + 1}", callback_data=f"wm_focus_{i}"),
            InlineKeyboardButton("−",           callback_data=f"wm_min_{i}"),
            InlineKeyboardButton("✕",           callback_data=f"wm_close_{i}"),
        ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )


async def wm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    action_key, idx = parts[1], parts[2]
    hwnd = _handles.get(idx)
    if hwnd is None:
        await query.answer("Window no longer tracked.", show_alert=True)
        return
    action_map = {'focus': 'focus', 'min': 'minimize', 'close': 'close'}
    action = action_map.get(action_key, 'focus')
    try:
        window_action(hwnd, action)
        await query.answer(f"{'Focused' if action == 'focus' else action.capitalize()}d.")
    except Exception as e:
        await query.answer(f"Failed: {e}", show_alert=True)


def register_windows_handlers(app) -> None:
    app.add_handler(CommandHandler("windows", windows_cmd))
    app.add_handler(CallbackQueryHandler(wm_callback, pattern="^wm_"))
