import asyncio
import datetime
import time
from pathlib import Path

import psutil
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized
from bot.handlers.ui import bar

_REPORT_JOB = "daily_report"


def _build_report() -> str:
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('C:\\')
    try:
        bat = psutil.sensors_battery()
        bat_line = (
            f"bat   {bar(bat.percent)}  {bat.percent:.0f}%"
            f"{'  charging' if bat.power_plugged else ''}"
        ) if bat else None
    except Exception:
        bat_line = None

    lines = [
        f"<b>REPORT</b>  {datetime.date.today()}",
        "<pre>",
        f"cpu   {bar(cpu)}  {cpu:.0f}%",
        f"ram   {bar(ram.percent)}  {ram.percent:.0f}%  {ram.used//1024**3:.1f}/{ram.total//1024**3:.1f} GB",
        f"disk  {bar(disk.percent)}  {disk.percent:.0f}%  {disk.free//1024**3:.1f} GB free",
    ]
    if bat_line:
        lines.append(bat_line)
    lines.append("</pre>")
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
            await update.message.reply_text("usage: /report on HH:MM")
            return

        for job in context.job_queue.get_jobs_by_name(_REPORT_JOB):
            job.schedule_removal()

        chat_id = update.effective_chat.id

        async def _daily(ctx: ContextTypes.DEFAULT_TYPE) -> None:
            report = await asyncio.to_thread(_build_report)
            await ctx.bot.send_message(chat_id=chat_id, text=report, parse_mode=ParseMode.HTML)

        context.job_queue.run_daily(_daily, time=schedule_time, name=_REPORT_JOB)
        await update.message.reply_text(
            f"daily report scheduled at {schedule_time.strftime('%H:%M')}."
        )
        return

    if sub == 'off':
        removed = 0
        for job in context.job_queue.get_jobs_by_name(_REPORT_JOB):
            job.schedule_removal()
            removed += 1
        await update.message.reply_text(
            "daily report off." if removed else "no daily report was scheduled."
        )
        return

    await update.message.reply_text("usage: /report now|on HH:MM|off")


async def send_session_summary(bot, chat_id: int, idle_secs: float) -> None:
    from utils.session import pop_events
    events = pop_events()
    if not events:
        return
    h, rem = divmod(int(idle_secs), 3600)
    m = rem // 60
    away = f"{h}h {m}m" if h else f"{m}m"
    lines = [f"<b>BACK</b>  away {away}\n<pre>"]
    for ts, text in events:
        t = datetime.datetime.fromtimestamp(ts).strftime('%H:%M')
        lines.append(f"  {t}  {text}")
    lines.append("</pre>")
    await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML)


def register_report_handlers(app) -> None:
    app.add_handler(CommandHandler("report", report_cmd))
