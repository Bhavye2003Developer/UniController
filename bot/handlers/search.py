import asyncio
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from utils.windows_utils import search_files


async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: /search &lt;pattern&gt; [path]\n"
            "Searches text files (py, js, txt, md, json…)\n"
            "Default path: home directory",
            parse_mode=ParseMode.HTML
        )
        return

    pattern = context.args[0]
    root = Path(' '.join(context.args[1:])) if len(context.args) > 1 else Path.home()

    if not root.exists():
        await update.message.reply_text(f"Path not found: {root}")
        return

    status = await update.message.reply_text(f"🔍 Searching <code>{pattern}</code> in <code>{root}</code>…", parse_mode=ParseMode.HTML)
    results = await asyncio.to_thread(search_files, pattern, root, 15)

    if not results:
        await status.edit_text(f"No results for <code>{pattern}</code>", parse_mode=ParseMode.HTML)
        return

    lines = [f"🔍 <b>{len(results)} result(s)</b> for <code>{pattern}</code>:\n"]
    for fpath, lineno, line in results:
        try:
            rel = Path(fpath).relative_to(root)
        except ValueError:
            rel = Path(fpath)
        safe_line = line.replace('<', '&lt;').replace('>', '&gt;')
        lines.append(f"<code>{rel}:{lineno}</code>\n  <i>{safe_line}</i>\n")

    await status.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)


def register_search_handlers(app) -> None:
    app.add_handler(CommandHandler("search", search_cmd))
