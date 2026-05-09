from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from utils.watch_engine import _engine, parse_and_add


async def watch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: /watch &lt;rule&gt;\n\n"
            "Examples:\n"
            "  /watch cpu &gt; 90\n"
            "  /watch ram &gt; 80\n"
            "  /watch disk free &lt; 5GB\n"
            "  /watch process chrome exits\n"
            "  /watch file C:\\build.log changes\n\n"
            "/watches — list active rules\n"
            "/unwatch &lt;id&gt; — remove a rule",
            parse_mode=ParseMode.HTML
        )
        return

    chat_id = update.effective_chat.id
    desc = parse_and_add(context.args, chat_id)
    if desc is None:
        await update.message.reply_text("Couldn't parse that rule. See /watch for examples.")
        return
    await update.message.reply_text(f"👁 Watching: <code>{desc}</code>", parse_mode=ParseMode.HTML)


async def watches_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    rules = _engine.list_rules()
    if not rules:
        await update.message.reply_text("No active watches. Use /watch to add one.")
        return
    lines = ["👁 <b>Active Watches</b>", ""]
    for r in rules:
        lines.append(f"{r.rule_id}. {r.description}")
    lines.append("\n/unwatch &lt;id&gt; to remove")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def unwatch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /unwatch <id>")
        return
    try:
        rule_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Provide a numeric rule ID.")
        return
    if _engine.remove(rule_id):
        await update.message.reply_text(f"✅ Watch #{rule_id} removed.")
    else:
        await update.message.reply_text(f"No watch with ID {rule_id}.")


def register_watch_handlers(app) -> None:
    app.add_handler(CommandHandler("watch",   watch_cmd))
    app.add_handler(CommandHandler("watches", watches_cmd))
    app.add_handler(CommandHandler("unwatch", unwatch_cmd))
