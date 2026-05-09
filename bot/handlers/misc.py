import asyncio
import os

import psutil
from rapidfuzz import fuzz, process
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from bot.handlers.ui import bar
from utils.windows_utils import get_volume, launch_app, list_apps, mute_toggle, set_volume, type_text
from utils import daemon as daemon_util

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
        await update.message.reply_text(
            f"vol: <b>{vol:.0f}%</b>  {bar(vol)}",
            parse_mode=ParseMode.HTML
        )
        return

    arg = context.args[0].lower()
    try:
        if arg == 'up':
            set_volume(min(100, int(get_volume()) + 10))
        elif arg == 'down':
            set_volume(max(0, int(get_volume()) - 10))
        elif arg == 'mute':
            mute_toggle()
            await update.message.reply_text("muted.")
            return
        else:
            set_volume(int(arg))
        vol = get_volume()
        await update.message.reply_text(
            f"vol: <b>{vol:.0f}%</b>  {bar(vol)}",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text("usage: /volume &lt;0-100 | up | down | mute&gt;", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"err: {e}")


async def launch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("usage: /launch &lt;app name&gt;", parse_mode=ParseMode.HTML)
        return

    query = ' '.join(context.args)
    apps = list_apps()
    if not apps:
        await update.message.reply_text("no installed apps found.")
        return

    names = [a[0] for a in apps]
    match = process.extractOne(query, names, scorer=fuzz.WRatio)
    if match is None or match[1] < 40:
        await update.message.reply_text(f"no app matching '{query}'")
        return

    matched_name, score, idx = match
    app_path = apps[idx][1]
    try:
        launch_app(app_path)
        await update.message.reply_text(f"launched: <b>{matched_name}</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"err: {e}")


async def focus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    try:
        minutes = int(context.args[0]) if context.args else 25
    except ValueError:
        await update.message.reply_text("usage: /focus &lt;minutes&gt;", parse_mode=ParseMode.HTML)
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
    killed_str = f"  closed: {', '.join(set(killed))}" if killed else ""

    async def _done(ctx):
        await ctx.bot.send_message(chat_id, "focus session complete.")

    context.job_queue.run_once(_done, when=minutes * 60)
    await update.message.reply_text(f"focus: {minutes}m{killed_str}")


async def type_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("usage: /type &lt;text&gt;", parse_mode=ParseMode.HTML)
        return
    text = ' '.join(context.args)
    await asyncio.to_thread(type_text, text)
    await update.message.reply_text(f"typed: <code>{text[:80]}</code>", parse_mode=ParseMode.HTML)


async def speedtest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    msg = await update.message.reply_text("running speed test... (~20s)")
    try:
        import speedtest as st_lib

        def _run():
            s = st_lib.Speedtest()
            s.get_best_server()
            s.download()
            s.upload()
            return s.results

        r = await asyncio.to_thread(_run)
        text = (
            "<b>SPEEDTEST</b>\n\n"
            f"down    <b>{r.download / 1_000_000:.1f} Mbps</b>\n"
            f"up      <b>{r.upload   / 1_000_000:.1f} Mbps</b>\n"
            f"ping    <b>{r.ping:.0f} ms</b>\n"
            f"server  {r.server['name']}, {r.server['country']}"
        )
    except Exception as e:
        text = f"speed test failed: {e}"
    await msg.edit_text(text, parse_mode=ParseMode.HTML)


async def daemon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    sub = (context.args or ['status'])[0].lower()
    if sub == 'install':
        msg = daemon_util.install()
    elif sub == 'uninstall':
        msg = daemon_util.uninstall()
    elif sub == 'status':
        msg = daemon_util.status()
    else:
        msg = "usage: /daemon install | uninstall | status"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


def register_misc_handlers(app) -> None:
    app.add_handler(CommandHandler("volume",    volume))
    app.add_handler(CommandHandler("launch",    launch))
    app.add_handler(CommandHandler("focus",     focus))
    app.add_handler(CommandHandler("type",      type_cmd))
    app.add_handler(CommandHandler("speedtest", speedtest_cmd))
    app.add_handler(CommandHandler("daemon",    daemon))
