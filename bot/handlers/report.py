import asyncio
import datetime
import time
from pathlib import Path

import psutil
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized

_REPORT_JOB = "daily_report"
_IDLE_THRESHOLD = 30 * 60  # 30 minutes


def _build_report() -> str:
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('C:\\')
    try:
        bat = psutil.sensors_battery()
        bat_line = f"🔋 Battery: {bat.percent:.0f}% {'(charging)' if bat.power_plugged else ''}" if bat else ""
    except Exception:
        bat_line = ""

    lines = [
        f"📊 <b>Daily PC Report — {datetime.date.today()}</b>",
        "",
        f"CPU:  {cpu:.0f}%",
        f"RAM:  {ram.percent:.0f}%  ({ram.used // 1024**3:.1f}/{ram.total // 1024**3:.1f} GB)",
        f"Disk: {disk.percent:.0f}%  ({disk.free // 1024**3:.1f} GB free)",
    ]
    if bat_line:
        lines.append(bat_line)
    return "\n".join(lines)


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    args = context.args or []
    sub = args[0].lower() if args else 'now'

    if sub == 'now':
        report = await asyncio.to_thread(_build_report)
        await update.message.reply_text(report, parse_mode=ParseMode.HTML)
        return

    if sub == 'on':
        time_str = args[1] if len(args) > 1 else "09:00"
        try:
            h, m = map(int, time_str.split(':'))
            schedule_time = datetime.time(h, m)
        except (ValueError, IndexError):
            await update.message.reply_text("Usage: /report on HH:MM  (e.g. /report on 09:00)")
            return

        # Cancel any existing job
        for job in context.job_queue.get_jobs_by_name(_REPORT_JOB):
            job.schedule_removal()

        chat_id = update.effective_chat.id

        async def _daily(ctx: ContextTypes.DEFAULT_TYPE) -> None:
            report = await asyncio.to_thread(_build_report)
            await ctx.bot.send_message(chat_id=chat_id, text=report, parse_mode=ParseMode.HTML)

        context.job_queue.run_daily(_daily, time=schedule_time, name=_REPORT_JOB)
        await update.message.reply_text(
            f"📊 Daily report scheduled at {schedule_time.strftime('%H:%M')} every day."
        )
        return

    if sub == 'off':
        removed = 0
        for job in context.job_queue.get_jobs_by_name(_REPORT_JOB):
            job.schedule_removal()
            removed += 1
        await update.message.reply_text(
            "📊 Daily report disabled." if removed else "No daily report was scheduled."
        )
        return

    await update.message.reply_text("Usage: /report now | on HH:MM | off")


async def send_session_summary(bot, chat_id: int, idle_secs: float) -> None:
    from utils.session import pop_events
    events = pop_events()
    if not events:
        return
    h, rem = divmod(int(idle_secs), 3600)
    m = rem // 60
    away = f"{h}h {m}m" if h else f"{m}m"
    lines = [f"👋 <b>Back after {away}:</b>", ""]
    for ts, text in events:
        t = datetime.datetime.fromtimestamp(ts).strftime('%H:%M')
        lines.append(f"  [{t}] {text}")
    await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML)


def register_report_handlers(app) -> None:
    app.add_handler(CommandHandler("report", report_cmd))
