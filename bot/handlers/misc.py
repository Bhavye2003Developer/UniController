import os

import psutil
from rapidfuzz import fuzz, process
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from utils.windows_utils import get_volume, launch_app, list_apps, mute_toggle, set_volume

FOCUS_BLOCKLIST = [
    x.strip().lower()
    for x in os.getenv('FOCUS_BLOCKLIST', '').split(',')
    if x.strip()
]


async def volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        vol = get_volume()
        await update.message.reply_text(f"🔊 Volume: {vol:.0f}%")
        return

    arg = context.args[0].lower()
    try:
        if arg == 'up':
            set_volume(min(100, int(get_volume()) + 10))
        elif arg == 'down':
            set_volume(max(0, int(get_volume()) - 10))
        elif arg == 'mute':
            mute_toggle()
            await update.message.reply_text("🔇 Toggled mute.")
            return
        else:
            set_volume(int(arg))
        await update.message.reply_text(f"🔊 Volume set to {get_volume():.0f}%")
    except ValueError:
        await update.message.reply_text("Usage: /volume <0-100|up|down|mute>")
    except Exception as e:
        await update.message.reply_text(f"Volume error: {e}")


async def launch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /launch <app name>")
        return

    query = ' '.join(context.args)
    apps = list_apps()
    if not apps:
        await update.message.reply_text("No installed apps found.")
        return

    names = [a[0] for a in apps]
    match = process.extractOne(query, names, scorer=fuzz.WRatio)
    if match is None or match[1] < 40:
        await update.message.reply_text(f"No app matching '{query}' found.")
        return

    matched_name, score, idx = match
    app_path = apps[idx][1]
    try:
        launch_app(app_path)
        await update.message.reply_text(f"🚀 Launched {matched_name}")
    except Exception as e:
        await update.message.reply_text(f"Launch failed: {e}")


async def focus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    try:
        minutes = int(context.args[0]) if context.args else 25
    except ValueError:
        await update.message.reply_text("Usage: /focus <minutes>")
        return

    killed = []
    for proc in psutil.process_iter(['name']):
        try:
            pname = (proc.info.get('name') or '').lower().replace('.exe', '')
            if pname in FOCUS_BLOCKLIST:
                proc.kill()
                killed.append(pname)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    chat_id = update.effective_chat.id
    killed_str = f" Closed: {', '.join(set(killed))}." if killed else ""

    async def _done(ctx):
        await ctx.bot.send_message(chat_id, "✅ Focus session complete!")

    context.job_queue.run_once(_done, when=minutes * 60)
    await update.message.reply_text(
        f"🎯 Focus session started — {minutes} minutes.{killed_str}"
    )


def register_misc_handlers(app) -> None:
    app.add_handler(CommandHandler("volume", volume))
    app.add_handler(CommandHandler("launch", launch))
    app.add_handler(CommandHandler("focus",  focus))
