import datetime
import os
import subprocess
import time

import psutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from utils.windows_utils import lock_screen

_pending_shutdown: set[int] = set()
_pending_restart: set[int] = set()


async def sysinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('C:\\')
    net = psutil.net_io_counters()
    uptime = str(datetime.timedelta(seconds=int(time.time() - psutil.boot_time())))

    msg = (
        f"💻 <b>System Info</b>\n"
        f"CPU: {cpu}%\n"
        f"RAM: {ram.percent}% "
        f"({ram.used // 1024**3:.1f}/{ram.total // 1024**3:.1f} GB)\n"
        f"Disk C: {disk.percent}% "
        f"({disk.used // 1024**3:.1f}/{disk.total // 1024**3:.1f} GB)\n"
        f"Net ↑{net.bytes_sent // 1024} KB ↓{net.bytes_recv // 1024} KB\n"
        f"Uptime: {uptime}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def ps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    procs.sort(key=lambda x: x.get('cpu_percent') or 0, reverse=True)
    top = procs[:15]

    lines = []
    keyboard = []
    for p in top:
        name = (p.get('name') or 'Unknown')[:20]
        cpu = p.get('cpu_percent') or 0
        pid = p.get('pid', 0)
        lines.append(f"{pid:6d} {cpu:5.1f}% {name}")
        keyboard.append([InlineKeyboardButton(f"🔴 {name}", callback_data=f"killpid_{pid}")])

    text = "<code>   PID   CPU% Name\n" + "\n".join(lines) + "</code>"
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def kill_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /kill <pid|name>")
        return
    target = context.args[0]
    try:
        pid = int(target)
        proc = psutil.Process(pid)
        proc.kill()
        await update.message.reply_text(f"Killed PID {pid}.")
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
            await update.message.reply_text(f"Killed: {killed}")
        else:
            await update.message.reply_text(f"No process named '{target}'.")
    except psutil.NoSuchProcess:
        await update.message.reply_text(f"PID {target} not found.")
    except Exception as e:
        await update.message.reply_text(f"Kill failed: {e}")


async def kill_pid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split('_')[1])
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.kill()
        await query.edit_message_text(f"✅ Killed {name} (PID {pid})")
    except psutil.NoSuchProcess:
        await query.edit_message_text(f"Process {pid} no longer exists.")
    except Exception as e:
        await query.edit_message_text(f"Kill failed: {e}")


async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    lock_screen()
    await update.message.reply_text("🔒 Screen locked.")


async def shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    _pending_shutdown.add(update.effective_chat.id)
    await update.message.reply_text("⚠️ Type `confirm` to shut down the PC.")


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    _pending_restart.add(update.effective_chat.id)
    await update.message.reply_text("⚠️ Type `confirm` to restart the PC.")


async def shutdown_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _pending_shutdown.discard(update.effective_chat.id)
    await update.message.reply_text("Shutting down in 3 seconds...")
    subprocess.run(['shutdown', '/s', '/t', '3'])


async def restart_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _pending_restart.discard(update.effective_chat.id)
    await update.message.reply_text("Restarting in 3 seconds...")
    subprocess.run(['shutdown', '/r', '/t', '3'])


def register_system_handlers(app) -> None:
    app.add_handler(CommandHandler("sysinfo",  sysinfo))
    app.add_handler(CommandHandler("ps",       ps))
    app.add_handler(CommandHandler("kill",     kill_cmd))
    app.add_handler(CommandHandler("lock",     lock))
    app.add_handler(CommandHandler("shutdown", shutdown))
    app.add_handler(CommandHandler("restart",  restart))
    app.add_handler(CallbackQueryHandler(kill_pid_callback, pattern="^killpid_"))
