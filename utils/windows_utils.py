import ctypes
import os
import subprocess
import time
from io import BytesIO
import glob
import winreg
from pathlib import Path
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER

import cv2
import numpy as np
import psutil


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


def get_active_window() -> dict:
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
    title = buf.value or "Unknown"
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        proc = psutil.Process(pid.value)
        name = proc.name()
        mem_mb = proc.memory_info().rss // (1024 * 1024)
        runtime = int(time.time() - proc.create_time())
        h, rem = divmod(runtime, 3600)
        m, s = divmod(rem, 60)
        runtime_str = f"{h}h {m}m" if h else f"{m}m {s}s"
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        name, mem_mb, runtime_str = "Unknown", 0, "N/A"
    return {"title": title, "name": name, "mem_mb": mem_mb, "runtime": runtime_str}


def get_powerplans() -> list[tuple[str, str, bool]]:
    list_out = subprocess.run(['powercfg', '/list'], capture_output=True, text=True)
    active_out = subprocess.run(['powercfg', '/getactivescheme'], capture_output=True, text=True)
    active_guid = ""
    for part in active_out.stdout.split():
        if len(part) == 36 and part.count('-') == 4:
            active_guid = part
            break
    plans = []
    for line in list_out.stdout.splitlines():
        if 'GUID:' in line:
            rest = line.split('GUID:')[1].strip()
            parts = rest.split(None, 1)
            if not parts:
                continue
            guid = parts[0]
            name = parts[1].strip(' ()*') if len(parts) > 1 else guid
            plans.append((name, guid, guid == active_guid))
    return plans


def set_powerplan(guid: str) -> None:
    subprocess.run(['powercfg', '/setactive', guid], check=True)


def get_nowplaying() -> str:
    script = (
        "$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,"
        "Windows.Media.Control,ContentType=WindowsRuntime];"
        "$mgr = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]"
        "::RequestAsync().GetResults();"
        "$sess = $mgr.GetCurrentSession();"
        "if ($null -eq $sess) { 'Nothing playing'; exit };"
        "$props = $sess.TryGetMediaPropertiesAsync().GetResults();"
        "$status = $sess.GetPlaybackInfo().PlaybackStatus;"
        "\"$($props.Artist) - $($props.Title) [$status]\""
    )
    result = subprocess.run(
        ['powershell', '-NoProfile', '-Command', script],
        capture_output=True, text=True, timeout=6
    )
    return result.stdout.strip() or "Nothing playing"


def type_text(text: str) -> None:
    from pynput.keyboard import Controller
    Controller().type(text)


def print_file(path: str) -> None:
    import win32api
    win32api.ShellExecute(0, "print", path, None, ".", 0)
