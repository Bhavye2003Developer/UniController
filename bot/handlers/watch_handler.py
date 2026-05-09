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
            "<b>WATCH</b>\n<pre>"
            "usage: /watch &lt;rule&gt;\n\n"
            "/watch cpu &gt; 90\n"
            "/watch ram &gt; 80\n"
            "/watch disk free &lt; 5GB\n"
            "/watch process chrome exits\n"
            "/watch file C:\\build.log changes\n\n"
            "/watches      list active rules\n"
            "/unwatch &lt;id&gt;  remove a rule"
            "</pre>",
            parse_mode=ParseMode.HTML
        )
        return

    chat_id = update.effective_chat.id
    desc = parse_and_add(context.args, chat_id)
    if desc is None:
        await update.message.reply_text("can't parse that rule. see /watch for examples.")
        return
    await update.message.reply_text(
        f"watching: <code>{desc}</code>", parse_mode=ParseMode.HTML
    )


async def watches_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    rules = _engine.list_rules()
    if not rules:
        await update.message.reply_text("no active watches. use /watch to add one.")
        return
    lines = [f"<b>WATCHES</b>  {len(rules)} active\n<pre>"]
    for r in rules:
        lines.append(f"{r.rule_id:2}.  {r.description}")
    lines.append("</pre>\n/unwatch &lt;id&gt; to remove")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def unwatch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("usage: /unwatch &lt;id&gt;", parse_mode=ParseMode.HTML)
        return
    try:
        rule_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("provide a numeric rule ID.")
        return
    if _engine.remove(rule_id):
        await update.message.reply_text(f"watch #{rule_id} removed.")
    else:
        await update.message.reply_text(f"no watch with id {rule_id}.")


def register_watch_handlers(app) -> None:
    app.add_handler(CommandHandler("watch",   watch_cmd))
    app.add_handler(CommandHandler("watches", watches_cmd))
    app.add_handler(CommandHandler("unwatch", unwatch_cmd))
