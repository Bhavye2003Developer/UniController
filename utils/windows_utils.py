import ctypes
import os
import subprocess
from io import BytesIO
import glob
import winreg
from pathlib import Path
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER

import cv2
import numpy as np


def lock_screen() -> None:
    ctypes.windll.user32.LockWorkStation()


def disable_wifi() -> None:
    result = subprocess.run(
        ['netsh', 'interface', 'show', 'interface'],
        capture_output=True, text=True, check=True
    )
    wifi_name = None
    for line in result.stdout.splitlines():
        lower = line.lower()
        if any(kw in lower for kw in ('wi-fi', 'wifi', 'wireless', 'wlan')):
            parts = line.split()
            if parts:
                wifi_name = line.strip().split('  ')[-1].strip()
                break
    if wifi_name is None:
        raise RuntimeError("No wireless interface found via netsh")
    subprocess.run(
        ['netsh', 'interface', 'set', 'interface', wifi_name, 'disable'],
        check=True, capture_output=True, text=True
    )


def capture_webcam() -> BytesIO | None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    _, buf = cv2.imencode('.jpg', frame)
    bio = BytesIO(buf.tobytes())
    bio.name = 'snap.jpg'
    return bio


def frame_diff_pixel_count(frame_a: np.ndarray, frame_b: np.ndarray) -> int:
    diff = cv2.absdiff(frame_a, frame_b)
    return int(np.count_nonzero(diff > 30))


def get_volume() -> float:
    speakers = AudioUtilities.GetSpeakers()
    interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    return round(volume.GetMasterVolumeLevelScalar() * 100, 1)


def set_volume(level: int) -> None:
    speakers = AudioUtilities.GetSpeakers()
    interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level / 100)), None)


def mute_toggle() -> None:
    from pynput.keyboard import Key, Controller
    kb = Controller()
    kb.press(Key.media_volume_mute)
    kb.release(Key.media_volume_mute)


def press_media_key(action: str) -> None:
    from pynput.keyboard import Key, Controller
    key_map = {
        'play_pause': Key.media_play_pause,
        'next':       Key.media_next,
        'prev':       Key.media_previous,
        'vol_up':     Key.media_volume_up,
        'vol_down':   Key.media_volume_down,
        'mute':       Key.media_volume_mute,
    }
    key = key_map.get(action)
    if key is None:
        raise ValueError(f"Unknown media action: {action}")
    kb = Controller()
    kb.press(key)
    kb.release(key)


def list_apps() -> list[tuple[str, str]]:
    apps: list[tuple[str, str]] = []
    start_menu_dirs = [
        Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
        Path(os.environ.get('PROGRAMDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
    ]
    for smd in start_menu_dirs:
        if smd.exists():
            for lnk in smd.rglob('*.lnk'):
                apps.append((lnk.stem, str(lnk)))
    return apps


def launch_app(path: str) -> None:
    os.startfile(path)
