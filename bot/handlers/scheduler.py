import asyncio
import datetime
import re
import subprocess

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized, commandExecutor


def _parse_delay(s: str) -> float | None:
    """Return delay in seconds or None if unparseable."""
    s = s.lower().strip()
    # "in 5m", "in 2h", "in 30s"
    m = re.match(r'in\s*(\d+)\s*([smh])', s)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return n * {'s': 1, 'm': 60, 'h': 3600}[unit]
    # "11:30pm", "23:30", "11:30"
    m = re.match(r'(\d{1,2}):(\d{2})\s*(am|pm)?$', s)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        ampm = m.group(3)
        if ampm == 'pm' and h != 12:
            h += 12
        elif ampm == 'am' and h == 12:
            h = 0
        now = datetime.datetime.now()
        target = now.replace(hour=h, minute=mn, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return (target - now).total_seconds()
    return None


def _delay_str(secs: float) -> str:
    if secs < 60:
        return f"{secs:.0f}s"
    if secs < 3600:
        return f"{secs / 60:.0f}m"
    return f"{secs / 3600:.1f}h"


async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /schedule <time> <cmd>\n"
            "Examples:\n"
            "  /schedule in 5m exec ls\n"
            "  /schedule in 2h shutdown\n"
            "  /schedule 11:30pm exec git pull"
        )
        return

    time_str = context.args[0]
    cmd_parts = context.args[1:]
    delay = _parse_delay(time_str)
    if delay is None:
        await update.message.reply_text(f"Can't parse time: <code>{time_str}</code>", parse_mode=ParseMode.HTML)
        return

    cmd_name = cmd_parts[0].lower()
    cmd_rest = cmd_parts[1:]
    chat_id = update.effective_chat.id

    if cmd_name == 'exec':
        async def _job(ctx):
            result = commandExecutor.run(cmd_rest)
            await ctx.bot.send_message(
                chat_id=chat_id,
                text=f"⏰ Scheduled <code>/exec {' '.join(cmd_rest)}</code>:\n{result}",
                parse_mode=ParseMode.HTML
            )
    elif cmd_name == 'shutdown':
        async def _job(ctx):
            await ctx.bot.send_message(chat_id=chat_id, text="⏰ Scheduled shutdown — running now.")
            subprocess.run(['shutdown', '/s', '/t', '3'])
    elif cmd_name == 'restart':
        async def _job(ctx):
            await ctx.bot.send_message(chat_id=chat_id, text="⏰ Scheduled restart — running now.")
            subprocess.run(['shutdown', '/r', '/t', '3'])
    else:
        await update.message.reply_text(f"Unsupported scheduled command: {cmd_name}")
        return

    context.job_queue.run_once(_job, when=delay, name=f"sched_{chat_id}")
    label = ' '.join(cmd_parts)
    await update.message.reply_text(
        f"⏰ Scheduled <code>/{label}</code> in {_delay_str(delay)}",
        parse_mode=ParseMode.HTML
    )


async def babysit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /babysit <command>")
        return
    cmd = ' '.join(context.args)
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"👀 Watching: <code>{cmd}</code>", parse_mode=ParseMode.HTML)

    async def _watch():
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            stdout, _ = await proc.communicate()
            output = (stdout.decode(errors='replace')[-500:] if stdout else "(no output)").strip()
            text = (
                f"✅ <code>{cmd}</code> exited (code {proc.returncode})\n"
                f"<code>{output}</code>"
            )
        except Exception as e:
            text = f"❌ <code>{cmd}</code> failed: {e}"
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)

    asyncio.create_task(_watch())


async def wake_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
        await update.message.reply_text(
            f"<code>{result.stdout[:3500]}</code>\n\nUsage: /wake &lt;mac-address&gt;",
            parse_mode=ParseMode.HTML
        )
        return
    mac = context.args[0]
    try:
        from wakeonlan import send_magic_packet
        send_magic_packet(mac)
        await update.message.reply_text(f"📡 WoL magic packet sent to <code>{mac}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")


def register_scheduler_handlers(app) -> None:
    app.add_handler(CommandHandler("schedule", schedule_cmd))
    app.add_handler(CommandHandler("babysit",  babysit_cmd))
    app.add_handler(CommandHandler("wake",     wake_cmd))
