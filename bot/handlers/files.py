import asyncio
import os
import shutil
import tempfile
import time
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.handlers.core import is_authorized
from utils.proactive import INBOX
from utils.windows_utils import do_cleanup, fmt_size, print_file, scan_junk, set_wallpaper

UPLOAD_DEFAULT_PATH = os.getenv('UPLOAD_DEFAULT_PATH', str(Path.home() / 'Downloads'))
_ROOT = Path(os.path.abspath(os.sep))


async def files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    path_str = ' '.join(context.args) if context.args else str(_ROOT)
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

    lines = [f"<b>FILES</b>  <code>{path}</code>\n<pre>"]
    for i, item in enumerate(items):
        name = item.name[:38]
        if item.is_dir():
            lines.append(f"{i+1:2}.  {name}/")
        else:
            size_str = fmt_size(item.stat().st_size)
            lines.append(f"{i+1:2}.  {name:<40}  {size_str:>8}")
    lines.append("</pre>")
    lines.append(f"{len(items)} items")

    keyboard = []
    if path.parent != path:
        keyboard.append([InlineKeyboardButton(".. (up)", callback_data="nav_up")])

    row = []
    for i in range(len(items)):
        row.append(InlineKeyboardButton(str(i + 1), callback_data=f"nav_i_{i}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )


async def nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    query = update.callback_query
    await query.answer()
    data = query.data
    current = Path(context.user_data.get('browse_dir', str(_ROOT)))
    items = context.user_data.get('browse_items', {})

    if data == 'nav_up':
        await _show_dir(query.message, context, current.parent)
    elif data.startswith('nav_i_'):
        idx = int(data.split('_')[2])
        item_path = Path(items.get(idx, ''))
        if not item_path.exists():
            await query.edit_message_text("Item no longer exists.")
            return
        if item_path.is_dir():
            await _show_dir(query.message, context, item_path)
        else:
            await query.message.reply_document(
                document=open(item_path, 'rb'),
                filename=item_path.name
            )


async def download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await _show_dir(update.message, context, _ROOT)
        return
    path = Path(' '.join(context.args))
    if not path.exists():
        await update.message.reply_text(f"File not found: {path}")
        return
    if path.is_dir():
        await _show_dir(update.message, context, path)
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
    await update.message.reply_text(f"saved: <code>{dest}</code>", parse_mode=ParseMode.HTML)


async def cleanup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    msg = await update.message.reply_text("🔍 Scanning for junk files…")
    sizes = await asyncio.to_thread(scan_junk)
    if not sizes:
        await msg.edit_text("Nothing to clean.")
        return
    total = sum(s for s, _ in sizes.values())
    lines = ["<b>CLEANUP</b>\n<pre>"]
    for label, (size, count) in sizes.items():
        lines.append(f"{label:<18}  {fmt_size(size):>8}  ({count} files)")
    lines.append(f"\n{'total':<18}  {fmt_size(total):>8}")
    lines.append("</pre>")
    context.user_data['cleanup_categories'] = list(sizes.keys())
    await msg.edit_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("clean all", callback_data="cleanup_all"),
            InlineKeyboardButton("cancel",    callback_data="cleanup_cancel"),
        ]])
    )


async def cleanup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    query = update.callback_query
    await query.answer()
    if query.data == "cleanup_cancel":
        await query.edit_message_text("cleanup cancelled.")
        return
    categories = context.user_data.get('cleanup_categories', [])
    freed = await asyncio.to_thread(do_cleanup, categories)
    await query.edit_message_text(f"cleaned. freed: {fmt_size(freed)}")


async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    photo = update.message.photo[-1]
    context.user_data['pending_photo_id'] = photo.file_id
    context.user_data['pending_photo_ts'] = int(time.time())
    await update.message.reply_text(
        "photo received:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("wallpaper", callback_data="photo_wallpaper"),
            InlineKeyboardButton("desktop",   callback_data="photo_desktop"),
            InlineKeyboardButton("inbox",     callback_data="photo_inbox"),
        ]])
    )


async def photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    query = update.callback_query
    await query.answer()
    file_id = context.user_data.get('pending_photo_id')
    if not file_id:
        await query.edit_message_text("No photo pending.")
        return
    ts = context.user_data.get('pending_photo_ts', int(time.time()))
    filename = f"photo_{ts}.jpg"
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        tmp_path = tmp.name
    file_obj = await context.bot.get_file(file_id)
    await file_obj.download_to_drive(tmp_path)
    action = query.data
    try:
        if action == 'photo_wallpaper':
            await asyncio.to_thread(set_wallpaper, tmp_path)
            await query.edit_message_text("wallpaper set.")
        elif action == 'photo_desktop':
            dest = Path.home() / 'Desktop' / filename
            shutil.copy(tmp_path, dest)
            await query.edit_message_text(f"saved to desktop: {filename}")
        elif action == 'photo_inbox':
            INBOX.mkdir(parents=True, exist_ok=True)
            shutil.copy(tmp_path, INBOX / filename)
            await query.edit_message_text(f"saved to inbox: {filename}")
    except Exception as e:
        await query.edit_message_text(f"Failed: {e}")
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass


async def print_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    reply = update.message.reply_to_message
    doc = reply.document if reply else None
    if doc is None:
        await update.message.reply_text(
            "Reply to a document with /print to print it on the PC's default printer."
        )
        return
    suffix = Path(doc.file_name).suffix if doc.file_name else '.pdf'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
    file_obj = await context.bot.get_file(doc.file_id)
    await file_obj.download_to_drive(tmp_path)
    try:
        await asyncio.to_thread(print_file, tmp_path)
        await update.message.reply_text(f"sent to printer: {doc.file_name}")
    except Exception as e:
        await update.message.reply_text(f"Print failed: {e}")


def register_files_handlers(app) -> None:
    app.add_handler(CommandHandler("files",    files))
    app.add_handler(CommandHandler("download", download))
    app.add_handler(CommandHandler("upload",   upload))
    app.add_handler(CommandHandler("print",    print_cmd))
    app.add_handler(CommandHandler("cleanup",  cleanup_cmd))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, photo_received))
    app.add_handler(CallbackQueryHandler(nav_callback,      pattern="^nav_"))
    app.add_handler(CallbackQueryHandler(cleanup_callback,  pattern="^cleanup_"))
    app.add_handler(CallbackQueryHandler(photo_callback,    pattern="^photo_"))
