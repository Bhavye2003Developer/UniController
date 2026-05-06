import asyncio
import logging
import os
import threading
import time
from io import BytesIO

import cv2
import numpy as np
from telegram import Bot

from utils.windows_utils import frame_diff_pixel_count

logger = logging.getLogger(__name__)

MOTION_THRESHOLD = int(os.getenv('MOTION_THRESHOLD', '500'))
GUARD_CHECK_INTERVAL = int(os.getenv('GUARD_CHECK_INTERVAL', '10'))


def capture_webcam_frame() -> np.ndarray | None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


def frame_to_bytesio(frame: np.ndarray) -> BytesIO:
    _, buf = cv2.imencode('.jpg', frame)
    bio = BytesIO(buf.tobytes())
    bio.name = 'alert.jpg'
    return bio


class GuardianWatcher:
    def __init__(self):
        self._running = False
        self._bot: Bot | None = None
        self._chat_id: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._baseline_frame: np.ndarray | None = None
        self._last_login_check: float = 0.0
        self._threads: list[threading.Thread] = []

    def is_active(self) -> bool:
        return self._running

    def start(self, bot: Bot, chat_id: int, loop: asyncio.AbstractEventLoop) -> None:
        if self._running:
            return
        self._bot = bot
        self._chat_id = chat_id
        self._loop = loop
        self._running = True
        self._last_login_check = time.time()
        self._baseline_frame = capture_webcam_frame()

        for target in (self._motion_loop, self._usb_loop, self._login_loop):
            t = threading.Thread(target=target, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._running = False
        self._threads.clear()

    def reset_baseline(self) -> None:
        self._baseline_frame = capture_webcam_frame()

    def _send_alert(self, text: str, photo: BytesIO | None = None) -> None:
        if photo:
            coro = self._bot.send_photo(self._chat_id, photo=photo, caption=text)
        else:
            coro = self._bot.send_message(self._chat_id, text=text)
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        future.add_done_callback(
            lambda f: logger.error("Alert send failed: %s", f.exception()) if f.exception() else None
        )

    def _motion_loop(self) -> None:
        while self._running:
            try:
                self._check_motion()
            except Exception as e:
                logger.error("Motion check error: %s", e)
            time.sleep(GUARD_CHECK_INTERVAL)

    def _check_motion(self) -> None:
        frame = capture_webcam_frame()
        if frame is None or self._baseline_frame is None:
            return
        changed = frame_diff_pixel_count(self._baseline_frame, frame)
        if changed > MOTION_THRESHOLD:
            photo = frame_to_bytesio(frame)
            self._send_alert("🚨 Motion detected at your PC!", photo)
            self._baseline_frame = frame

    def _usb_loop(self) -> None:
        try:
            import wmi
            c = wmi.WMI()
            watcher = c.watch_for(
                raw_wql="SELECT * FROM __InstanceCreationEvent WITHIN 2 "
                        "WHERE TargetInstance ISA 'Win32_PnPEntity'"
            )
            while self._running:
                try:
                    event = watcher(timeout_ms=5000)
                    if event and self._running:
                        name = getattr(event.TargetInstance, 'Name', 'Unknown device')
                        self._send_alert(f"🔌 USB device connected: {name}")
                except wmi.x_wmi_timed_out:
                    pass
        except Exception as e:
            logger.error("USB watcher error: %s", e)

    def _login_loop(self) -> None:
        while self._running:
            try:
                self._check_failed_logins()
            except Exception as e:
                logger.error("Login check error: %s", e)
            time.sleep(30)

    def _check_failed_logins(self) -> None:
        import calendar
        import win32evtlog
        handle = win32evtlog.OpenEventLog(None, 'Security')
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        now = time.time()
        try:
            while True:
                records = win32evtlog.ReadEventLog(handle, flags, 0)
                if not records:
                    break
                for record in records:
                    if (record.EventID & 0xFFFF) == 4625:
                        event_time = calendar.timegm(record.TimeGenerated.timetuple())
                        if event_time > self._last_login_check:
                            photo = self._try_snap()
                            self._send_alert("⚠️ Failed login attempt detected!", photo)
                        else:
                            return
        finally:
            win32evtlog.CloseEventLog(handle)
            self._last_login_check = now

    def _try_snap(self) -> BytesIO | None:
        frame = capture_webcam_frame()
        return frame_to_bytesio(frame) if frame is not None else None
