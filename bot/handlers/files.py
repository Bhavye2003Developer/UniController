import asyncio
import shutil
import tempfile
import time
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.handlers.core import is_authorized
from utils.windows_utils import do_cleanup, fmt_size, print_file, scan_junk, set_wallpaper

_LOCATIONS = {
    'desktop':   Path.home() / 'Desktop',
    'downloads': Path.home() / 'Downloads',
    'documents': Path.home() / 'Documents',
}


def _recent_files(n: int = 8) -> list[Path]:
    files = []
    for loc in _LOCATIONS.values():
        if not loc.exists():
            continue
        try:
            files.extend(f for f in loc.iterdir() if f.is_file())
        except PermissionError:
            pass
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files[:n]


async def _show_locations(message, context) -> None:
    lines = ["<b>FILES</b>\n"]
    keyboard = []

    for name, path in _LOCATIONS.items():
        try:
            count = sum(1 for _ in path.iterdir()) if path.exists() else 0
            lines.append(f"{name.capitalize():<12}  {count} items")
        except PermissionError:
            lines.append(f"{name.capitalize():<12}  (no access)")
        keyboard.append([InlineKeyboardButton(name.capitalize(), callback_data=f"nav_loc_{name}")])

    recent = await asyncio.to_thread(_recent_files)
    if recent:
        lines.append("\n<b>Recent</b>")
        context.user_data['browse_recent'] = {str(i): str(f) for i, f in enumerate(recent)}
        for i, f in enumerate(recent):
            age = int(time.time() - f.stat().st_mtime)
            age_str = f"{age // 3600}h ago" if age >= 3600 else f"{age // 60}m ago"
            lines.append(f"{i+1}.  {f.name[:40]}  <i>{age_str}</i>")
            keyboard.append([InlineKeyboardButton(f"send: {f.name[:30]}", callback_data=f"nav_recent_{i}")])

    await message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_dir(message, context, path: Path) -> None:
    if not path.exists() or not path.is_dir():
        await message.reply_text(f"not a directory: {path}")
        return

    try:
        items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))[:20]
    except PermissionError:
        await message.reply_text(f"permission denied: {path}")
        return

    context.user_data['browse_dir'] = str(path)
    context.user_data['browse_items'] = {str(i): str(item) for i, item in enumerate(items)}

    lines = [f"<b>FILES</b>  <code>{path}</code>\n<pre>"]
    for i, item in enumerate(items):
        name = item.name[:38]
        if item.is_dir():
            lines.append(f"{i+1:2}.  {name}/")
        else:
            lines.append(f"{i+1:2}.  {name:<40}  {fmt_size(item.stat().st_size):>8}")
    lines.append("</pre>")

    keyboard = []
    if path.parent != path:
        keyboard.append([InlineKeyboardButton(".. up", callback_data="nav_up")])
    row = []
    for i in range(len(items)):
        row.append(InlineKeyboardButton(str(i + 1), callback_data=f"nav_i_{i}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("home", callback_data="nav_home")])

    await message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if context.args:
        await _show_dir(update.message, context, Path(' '.join(context.args)))
    else:
        await _show_locations(update.message, context)


async def nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'nav_home':
        await _show_locations(query.message, context)
        return

    if data == 'nav_up':
        current = Path(context.user_data.get('browse_dir', str(Path.home())))
        await _show_dir(query.message, context, current.parent)
        return

    if data.startswith('nav_loc_'):
        name = data[len('nav_loc_'):]
        path = _LOCATIONS.get(name)
        if path:
            await _show_dir(query.message, context, path)
        return

    if data.startswith('nav_recent_'):
        idx = data.split('_')[-1]
        recent = context.user_data.get('browse_recent', {})
        path = Path(recent.get(idx, ''))
        if path.exists() and path.is_file():
            await query.message.reply_document(document=open(path, 'rb'), filename=path.name)
        else:
            await query.edit_message_text("file no longer exists.")
        return

    if data.startswith('nav_i_'):
        idx = data.split('_')[2]
        items = context.user_data.get('browse_items', {})
        item_path = Path(items.get(idx, ''))
        if not item_path.exists():
            await query.edit_message_text("item no longer exists.")
            return
        if item_path.is_dir():
            await _show_dir(query.message, context, item_path)
        else:
            await query.message.reply_document(document=open(item_path, 'rb'), filename=item_path.name)


async def download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await _show_locations(update.message, context)
        return
    path = Path(' '.join(context.args))
    if not path.exists():
        await update.message.reply_text(f"not found: {path}")
        return
    if path.is_dir():
        await _show_dir(update.message, context, path)
    else:
        await update.message.reply_document(document=open(path, 'rb'), filename=path.name)


async def _save_incoming_file(update: Update, context: ContextTypes.DEFAULT_TYPE, doc) -> None:
    filename = getattr(doc, 'file_name', None) or f"file_{doc.file_unique_id}"
    context.user_data['pending_doc_id'] = doc.file_id
    context.user_data['pending_doc_name'] = filename
    await update.message.reply_text(
        f"<b>{filename}</b>\nSave to:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Desktop",   callback_data="save_desktop"),
            InlineKeyboardButton("Downloads", callback_data="save_downloads"),
            InlineKeyboardButton("Documents", callback_data="save_documents"),
        ]])
    )


async def doc_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    doc = update.message.document
    if doc:
        await _save_incoming_file(update, context, doc)


async def save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    query = update.callback_query
    await query.answer()
    dest_key = query.data[len('save_'):]
    dest_dir = _LOCATIONS.get(dest_key)
    if dest_dir is None:
        await query.edit_message_text("unknown destination.")
        return

    file_id = context.user_data.get('pending_doc_id')
    filename = context.user_data.get('pending_doc_name', 'file')
    if not file_id:
        await query.edit_message_text("no file pending.")
        return

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    file_obj = await context.bot.get_file(file_id)
    await file_obj.download_to_drive(str(dest))
    await query.edit_message_text(
        f"saved to {dest_key.capitalize()}: <code>{filename}</code>",
        parse_mode=ParseMode.HTML
    )


async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    reply = update.message.reply_to_message
    doc = None
    if reply:
        doc = reply.document or (reply.photo[-1] if reply.photo else None)
    if doc is None:
        await update.message.reply_text("reply to any file with /upload to save it to Downloads.")
        return
    dest_dir = _LOCATIONS['downloads']
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = getattr(doc, 'file_name', None) or f"upload_{doc.file_unique_id}"
    dest = dest_dir / filename
    file_obj = await context.bot.get_file(doc.file_id)
    await file_obj.download_to_drive(str(dest))
    await update.message.reply_text(f"saved: <code>{dest}</code>", parse_mode=ParseMode.HTML)


async def cleanup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    msg = await update.message.reply_text("scanning for junk files...")
    sizes = await asyncio.to_thread(scan_junk)
    if not sizes:
        await msg.edit_text("nothing to clean.")
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
        await query.edit_message_text("cancelled.")
        return
    categories = context.user_data.get('cleanup_categories', [])
    freed = await asyncio.to_thread(do_cleanup, categories)
    await query.edit_message_text(f"cleaned. freed: <b>{fmt_size(freed)}</b>", parse_mode=ParseMode.HTML)


async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    photo = update.message.photo[-1]
    context.user_data['pending_photo_id'] = photo.file_id
    context.user_data['pending_photo_ts'] = int(time.time())
    await update.message.reply_text(
        "photo received — save as:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("wallpaper", callback_data="photo_wallpaper"),
            InlineKeyboardButton("desktop",   callback_data="photo_desktop"),
            InlineKeyboardButton("downloads", callback_data="photo_downloads"),
        ]])
    )


async def photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    query = update.callback_query
    await query.answer()
    file_id = context.user_data.get('pending_photo_id')
    if not file_id:
        await query.edit_message_text("no photo pending.")
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
            dest = _LOCATIONS['desktop'] / filename
            shutil.copy(tmp_path, dest)
            await query.edit_message_text(f"saved to Desktop: <code>{filename}</code>", parse_mode=ParseMode.HTML)
        elif action == 'photo_downloads':
            dest = _LOCATIONS['downloads'] / filename
            shutil.copy(tmp_path, dest)
            await query.edit_message_text(f"saved to Downloads: <code>{filename}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await query.edit_message_text(f"failed: {e}")
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
        await update.message.reply_text("reply to a document with /print to send it to the default printer.")
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
        await update.message.reply_text(f"print failed: {e}")


def register_files_handlers(app) -> None:
    app.add_handler(CommandHandler("files",    files))
    app.add_handler(CommandHandler("download", download))
    app.add_handler(CommandHandler("upload",   upload))
    app.add_handler(CommandHandler("print",    print_cmd))
    app.add_handler(CommandHandler("cleanup",  cleanup_cmd))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND,    photo_received))
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, doc_received))
    app.add_handler(CallbackQueryHandler(nav_callback,     pattern="^nav_"))
    app.add_handler(CallbackQueryHandler(save_callback,    pattern="^save_"))
    app.add_handler(CallbackQueryHandler(cleanup_callback, pattern="^cleanup_"))
    app.add_handler(CallbackQueryHandler(photo_callback,   pattern="^photo_"))
