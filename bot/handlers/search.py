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
            "<b>SEARCH</b>\n<pre>"
            "usage: /search &lt;pattern&gt; [path]\n"
            "searches: py js ts txt md json yaml...\n"
            "default path: home directory"
            "</pre>",
            parse_mode=ParseMode.HTML
        )
        return

    pattern = context.args[0]
    root = Path(' '.join(context.args[1:])) if len(context.args) > 1 else Path.home()

    if not root.exists():
        await update.message.reply_text(f"path not found: {root}")
        return

    status = await update.message.reply_text(
        f"searching <code>{pattern}</code> in <code>{root}</code>...",
        parse_mode=ParseMode.HTML
    )
    results = await asyncio.to_thread(search_files, pattern, root, 15)

    if not results:
        await status.edit_text(
            f"no results for <code>{pattern}</code>", parse_mode=ParseMode.HTML
        )
        return

    lines = [
        f"<b>SEARCH</b>  \"{pattern}\"  {len(results)} result(s)\n<pre>"
    ]
    for fpath, lineno, line in results:
        try:
            rel = Path(fpath).relative_to(root)
        except ValueError:
            rel = Path(fpath)
        safe = line.strip()[:70].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        lines.append(f"{rel}:{lineno}")
        lines.append(f"  {safe}")
    lines.append("</pre>")

    await status.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)


def register_search_handlers(app) -> None:
    app.add_handler(CommandHandler("search", search_cmd))
