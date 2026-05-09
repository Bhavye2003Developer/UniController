import asyncio
import datetime
import subprocess
import time

import psutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from bot.handlers.ui import bar
from utils.windows_utils import get_active_window, get_cpu_temps, get_powerplans, lock_screen, set_powerplan

_pending_shutdown: set[int] = set()
_pending_restart: set[int] = set()


async def sysinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    status = await update.message.reply_text("...")

    def _get():
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        net = psutil.net_io_counters()
        up = str(datetime.timedelta(seconds=int(time.time() - psutil.boot_time())))
        return cpu, ram, disk, net, up

    cpu, ram, disk, net, up = await asyncio.to_thread(_get)
    sent = net.bytes_sent / 1_048_576
    recv = net.bytes_recv / 1_048_576

    text = (
        "<b>SYSINFO</b>\n\n"
        f"cpu   <b>{cpu:.0f}%</b>  {bar(cpu)}\n"
        f"ram   <b>{ram.percent:.0f}%</b>  {bar(ram.percent)}  {ram.used//1024**3}/{ram.total//1024**3} GB\n"
        f"disk  <b>{disk.percent:.0f}%</b>  {bar(disk.percent)}  {disk.free//1024**3} GB free\n"
        f"net   up {sent:.0f} MB  dn {recv:.0f} MB\n"
        f"up    {up}"
    )
    await status.edit_text(text, parse_mode=ParseMode.HTML)


async def ps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    status = await update.message.reply_text("...")

    def _get():
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x.get('cpu_percent') or 0, reverse=True)
        return procs[:15]

    top = await asyncio.to_thread(_get)

    lines = ["<b>PROCESSES</b>  top 15 by cpu\n<pre>"]
    lines.append(f"{'NAME':<20} {'CPU%':>5} {'MEM%':>5}")
    lines.append("─" * 32)
    keyboard = []
    for p in top:
        name = (p.get('name') or '?')[:20]
        cpu  = p.get('cpu_percent') or 0
        mem  = p.get('memory_percent') or 0
        pid  = p.get('pid', 0)
        lines.append(f"{name:<20} {cpu:5.1f} {mem:5.1f}")
        keyboard.append([InlineKeyboardButton(f"kill {name.strip()}", callback_data=f"killpid_{pid}")])
    lines.append("</pre>")

    await status.edit_text(
        "\n".join(lines), parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def kill_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("usage: /kill &lt;pid|name&gt;", parse_mode=ParseMode.HTML)
        return
    target = context.args[0]
    try:
        pid = int(target)
        proc = psutil.Process(pid)
        name = proc.name()
        proc.kill()
        await update.message.reply_text(f"killed {name} (pid {pid})")
    except ValueError:
        killed = []
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if (p.info.get('name') or '').lower() == target.lower():
                    p.kill()
                    killed.append(p.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed:
            await update.message.reply_text(f"killed {target}  pids: {killed}")
        else:
            await update.message.reply_text(f"no process named '{target}'")
    except psutil.NoSuchProcess:
        await update.message.reply_text(f"pid {target} not found")
    except Exception as e:
        await update.message.reply_text(f"err: {e}")


async def kill_pid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split('_')[1])
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.kill()
        await query.edit_message_text(f"killed {name} (pid {pid})")
    except psutil.NoSuchProcess:
        await query.edit_message_text("already gone.")
    except Exception as e:
        await query.edit_message_text(f"err: {e}")


async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    lock_screen()
    await update.message.reply_text("screen locked.")


async def shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    _pending_shutdown.add(update.effective_chat.id)
    await update.message.reply_text(
        "<b>Shut down?</b>  Type <code>confirm</code> to proceed.",
        parse_mode=ParseMode.HTML
    )


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    _pending_restart.add(update.effective_chat.id)
    await update.message.reply_text(
        "<b>Restart?</b>  Type <code>confirm</code> to proceed.",
        parse_mode=ParseMode.HTML
    )


async def shutdown_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _pending_shutdown.discard(update.effective_chat.id)
    await update.message.reply_text("shutting down in 3s...")
    subprocess.run(['shutdown', '/s', '/t', '3'])


async def restart_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _pending_restart.discard(update.effective_chat.id)
    await update.message.reply_text("restarting in 3s...")
    subprocess.run(['shutdown', '/r', '/t', '3'])


async def temp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    temps = await asyncio.to_thread(get_cpu_temps)
    if not temps:
        await update.message.reply_text("temp data unavailable on this system.")
        return
    lines = ["<b>TEMP</b>\n<pre>"]
    for i, t in enumerate(temps):
        status = "  HOT" if t > 90 else "  WARM" if t > 70 else ""
        lines.append(f"zone {i}  {bar(min(t, 100))}  {t:.0f}C{status}")
    lines.append("</pre>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def activewindow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    info = get_active_window()
    text = (
        "<b>ACTIVE WINDOW</b>\n\n"
        f"<b>{info['title'][:50]}</b>\n"
        f"proc  {info['name']}  |  mem {info['mem_mb']} MB  |  up {info['runtime']}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def powerplan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    plans = get_powerplans()
    if not context.args:
        lines = ["<b>POWER PLANS</b>\n<pre>"]
        for name, _, active in plans:
            marker = "* " if active else "  "
            lines.append(f"{marker}{name}")
        lines.append("</pre>")
        lines.append("/powerplan &lt;name&gt; to switch")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    query = ' '.join(context.args).lower()
    match = next(
        ((name, guid) for name, guid, _ in plans if query in name.lower()),
        None
    )
    if match is None:
        await update.message.reply_text(f"no plan matching '{query}'")
        return
    try:
        set_powerplan(match[1])
        await update.message.reply_text(f"power plan: <b>{match[0]}</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"err: {e}")


def register_system_handlers(app) -> None:
    app.add_handler(CommandHandler("sysinfo",      sysinfo))
    app.add_handler(CommandHandler("ps",           ps))
    app.add_handler(CommandHandler("kill",         kill_cmd))
    app.add_handler(CommandHandler("lock",         lock))
    app.add_handler(CommandHandler("shutdown",     shutdown))
    app.add_handler(CommandHandler("restart",      restart))
    app.add_handler(CommandHandler("activewindow", activewindow))
    app.add_handler(CommandHandler("powerplan",    powerplan))
    app.add_handler(CommandHandler("temp",         temp_cmd))
    app.add_handler(CallbackQueryHandler(kill_pid_callback, pattern="^killpid_"))
