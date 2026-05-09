import asyncio
import shutil
import threading
import time
from pathlib import Path

import psutil

from utils import session

INBOX  = Path.home() / 'UniController' / 'inbox'
OUTBOX = Path.home() / 'UniController' / 'outbox'


class ProactiveMonitor:
    def __init__(self, bot, user_id: int, loop: asyncio.AbstractEventLoop):
        self.bot = bot
        self.user_id = user_id
        self.loop = loop

    def start(self) -> None:
        INBOX.mkdir(parents=True, exist_ok=True)
        OUTBOX.mkdir(parents=True, exist_ok=True)
        (OUTBOX / 'sent').mkdir(exist_ok=True)
        for target in (self._battery_loop, self._download_loop, self._outbox_loop):
            threading.Thread(target=target, daemon=True).start()

    def _send(self, text: str) -> None:
        asyncio.run_coroutine_threadsafe(
            self.bot.send_message(chat_id=self.user_id, text=text),
            self.loop
        )

    def _send_file(self, path: Path) -> None:
        async def _do():
            await self.bot.send_document(
                chat_id=self.user_id,
                document=open(path, 'rb'),
                filename=path.name,
                caption=f"📤 Outbox: {path.name}"
            )
        asyncio.run_coroutine_threadsafe(_do(), self.loop)

    # ── Battery guardian ──────────────────────────────────────────────────────
    def _battery_loop(self) -> None:
        alerted = False
        while True:
            time.sleep(60)
            try:
                b = psutil.sensors_battery()
                if b and not b.power_plugged:
                    if b.percent <= 15 and not alerted:
                        alerted = True
                        eta = ""
                        if b.secsleft and b.secsleft > 0:
                            eta = f" · ~{b.secsleft // 60}m left"
                        msg = f"⚠️ Battery at {b.percent:.0f}%{eta} — plug in or /shutdown?"
                        session.log_event(f"Battery low: {b.percent:.0f}%")
                        self._send(msg)
                    elif b.percent > 20:
                        alerted = False
            except Exception:
                pass

    # ── Download watcher ─────────────────────────────────────────────────────
    def _download_loop(self) -> None:
        dl = Path.home() / 'Downloads'
        if not dl.exists():
            return
        known = set(dl.glob('*'))
        pending: dict[Path, int] = {}
        while True:
            time.sleep(5)
            try:
                current = {f for f in dl.glob('*') if f.is_file()}
                for f in current - known:
                    pending[f] = -1
                completed = []
                for f, last in list(pending.items()):
                    if not f.exists():
                        completed.append(f)
                        continue
                    size = f.stat().st_size
                    if size == last and size > 0:
                        from utils.windows_utils import fmt_size
                        self._send(f"📥 Download complete: {f.name} ({fmt_size(size)})")
                        session.log_event(f"Download complete: {f.name}")
                        completed.append(f)
                    else:
                        pending[f] = size
                for f in completed:
                    pending.pop(f, None)
                known = {f for f in dl.glob('*') if f.is_file()}
            except Exception:
                pass

    # ── Outbox watcher ───────────────────────────────────────────────────────
    def _outbox_loop(self) -> None:
        sent_dir = OUTBOX / 'sent'
        known = set(OUTBOX.glob('*'))
        while True:
            time.sleep(3)
            try:
                current = {f for f in OUTBOX.glob('*') if f.is_file()}
                for f in current - known:
                    self._send_file(f)
                    session.log_event(f"Outbox sent: {f.name}")
                    time.sleep(0.5)
                    shutil.move(str(f), str(sent_dir / f.name))
                known = {f for f in OUTBOX.glob('*') if f.is_file()}
            except Exception:
                pass
