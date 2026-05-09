import datetime
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized

_NOTES = Path.home() / 'UniController' / 'notes.txt'


def _load() -> list[str]:
    if not _NOTES.exists():
        return []
    return [l for l in _NOTES.read_text(encoding='utf-8').splitlines() if l.strip()]


def _save(lines: list[str]) -> None:
    _NOTES.parent.mkdir(parents=True, exist_ok=True)
    _NOTES.write_text('\n'.join(lines) + '\n', encoding='utf-8')


async def note_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text(
            "<b>NOTE</b>\n<pre>"
            "/note &lt;text&gt;       add note\n"
            "/note clear &lt;n&gt;   delete note #n\n"
            "/notes             list all"
            "</pre>",
            parse_mode=ParseMode.HTML
        )
        return

    if context.args[0].lower() == 'clear':
        if len(context.args) < 2:
            await update.message.reply_text("usage: /note clear &lt;n&gt;", parse_mode=ParseMode.HTML)
            return
        try:
            n = int(context.args[1]) - 1
        except ValueError:
            await update.message.reply_text("provide a note number.")
            return
        lines = _load()
        if n < 0 or n >= len(lines):
            await update.message.reply_text("note not found.")
            return
        removed = lines.pop(n)
        _save(lines)
        await update.message.reply_text(f"deleted: <code>{removed[:60]}</code>", parse_mode=ParseMode.HTML)
        return

    text = ' '.join(context.args)
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = _load()
    lines.append(f"[{ts}] {text}")
    _save(lines)
    await update.message.reply_text("noted.")


async def notes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    lines = _load()
    if not lines:
        await update.message.reply_text("no notes. use /note &lt;text&gt;", parse_mode=ParseMode.HTML)
        return
    recent = lines[-20:]
    body = "\n".join(f"{i+1:2}.  {l}" for i, l in enumerate(recent))
    await update.message.reply_text(
        f"<b>NOTES</b>  {len(lines)} entries\n<pre>{body}</pre>",
        parse_mode=ParseMode.HTML
    )


def register_notepad_handlers(app) -> None:
    app.add_handler(CommandHandler("note",  note_cmd))
    app.add_handler(CommandHandler("notes", notes_cmd))
