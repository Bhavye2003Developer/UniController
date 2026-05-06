import os
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.handlers.core import is_authorized

UPLOAD_DEFAULT_PATH = os.getenv('UPLOAD_DEFAULT_PATH', str(Path.home() / 'Downloads'))


async def files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    path_str = ' '.join(context.args) if context.args else str(Path.home())
    await _show_dir(update.message, context, Path(path_str))


async def _show_dir(message, context, path: Path) -> None:
    if not path.exists() or not path.is_dir():
        await message.reply_text(f"Not a directory: {path}")
        return

    try:
        items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))[:20]
    except PermissionError:
        await message.reply_text(f"Permission denied: {path}")
        return

    context.user_data['browse_dir'] = str(path)
    context.user_data['browse_items'] = {i: str(item) for i, item in enumerate(items)}

    keyboard = []
    if path.parent != path:
        keyboard.append([InlineKeyboardButton("⬆️ ..", callback_data="nav_up")])

    for i, item in enumerate(items):
        name = item.name[:40]
        if item.is_dir():
            keyboard.append([InlineKeyboardButton(f"📁 {name}", callback_data=f"nav_d_{i}")])
        else:
            size = item.stat().st_size
            size_str = f"{size // 1024}KB" if size >= 1024 else f"{size}B"
            keyboard.append([InlineKeyboardButton(f"📄 {name} ({size_str})", callback_data=f"nav_f_{i}")])

    await message.reply_text(
        f"📂 <code>{path}</code>\n{len(items)} items",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    query = update.callback_query
    await query.answer()
    data = query.data
    current = Path(context.user_data.get('browse_dir', str(Path.home())))
    items = context.user_data.get('browse_items', {})

    if data == 'nav_up':
        await _show_dir(query.message, context, current.parent)
    elif data.startswith('nav_d_'):
        idx = int(data.split('_')[2])
        new_path = Path(items.get(idx, str(current)))
        await _show_dir(query.message, context, new_path)
    elif data.startswith('nav_f_'):
        idx = int(data.split('_')[2])
        file_path = Path(items.get(idx, ''))
        if not file_path.exists():
            await query.edit_message_text("File no longer exists.")
            return
        await query.message.reply_document(
            document=open(file_path, 'rb'),
            filename=file_path.name
        )


async def download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /download <path>")
        return
    path = Path(' '.join(context.args))
    if not path.exists():
        await update.message.reply_text(f"File not found: {path}")
        return
    if path.is_dir():
        await update.message.reply_text("Path is a directory. Use /files to browse.")
        return
    await update.message.reply_document(document=open(path, 'rb'), filename=path.name)


async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    reply = update.message.reply_to_message
    doc = None
    if reply:
        if reply.document:
            doc = reply.document
        elif reply.photo:
            doc = reply.photo[-1]
    if doc is None:
        await update.message.reply_text(
            f"Reply to a file with /upload [path] to save it.\n"
            f"Default save path: {UPLOAD_DEFAULT_PATH}"
        )
        return
    dest_dir = Path(' '.join(context.args)) if context.args else Path(UPLOAD_DEFAULT_PATH)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = getattr(doc, 'file_name', None) or f"upload_{doc.file_unique_id}"
    dest = dest_dir / filename
    file_obj = await context.bot.get_file(doc.file_id)
    await file_obj.download_to_drive(str(dest))
    await update.message.reply_text(f"✅ Saved to {dest}")


def register_files_handlers(app) -> None:
    app.add_handler(CommandHandler("files",    files))
    app.add_handler(CommandHandler("download", download))
    app.add_handler(CommandHandler("upload",   upload))
    app.add_handler(CallbackQueryHandler(nav_callback, pattern="^nav_"))
