import ctypes
import os
import subprocess
import time
from io import BytesIO
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


def _vol_ctrl():
    device = AudioUtilities.GetSpeakers()
    # pycaw >= 20231222 wraps IMMDevice in AudioDevice; access raw COM via _dev
    mm_device = getattr(device, '_dev', device)
    interface = mm_device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_volume() -> float:
    return round(_vol_ctrl().GetMasterVolumeLevelScalar() * 100, 1)


def set_volume(level: int) -> None:
    _vol_ctrl().SetMasterVolumeLevelScalar(max(0.0, min(1.0, level / 100)), None)


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


def fmt_size(size: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


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


def get_cpu_temps() -> list[float]:
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature'
             ' | Select-Object -ExpandProperty CurrentTemperature'],
            capture_output=True, text=True, timeout=6
        )
        temps = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                temps.append(round(int(line) / 10 - 273.15, 1))
        return temps
    except Exception:
        return []


def list_open_windows() -> list[tuple[int, str]]:
    import win32gui
    results = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            if title:
                results.append((hwnd, title))
    win32gui.EnumWindows(_cb, None)
    return results


def window_action(hwnd: int, action: str) -> None:
    import win32gui, win32con
    if action == 'focus':
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    elif action == 'minimize':
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    elif action == 'close':
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)


def press_key(key_name: str) -> None:
    from pynput.keyboard import Key, Controller, KeyCode
    _map = {
        'right': Key.right, 'left': Key.left, 'up': Key.up, 'down': Key.down,
        'f5': Key.f5, 'f11': Key.f11, 'escape': Key.esc,
        'enter': Key.enter, 'space': Key.space, 'tab': Key.tab,
    }
    kb = Controller()
    key = _map.get(key_name.lower())
    if key:
        kb.press(key); kb.release(key)
    elif len(key_name) == 1:
        kc = KeyCode.from_char(key_name)
        kb.press(kc); kb.release(kc)


def hotkey(modifier: str, key: str) -> None:
    from pynput.keyboard import Key, Controller, KeyCode
    _mods = {'ctrl': Key.ctrl, 'alt': Key.alt, 'shift': Key.shift}
    mod = _mods.get(modifier.lower(), Key.ctrl)
    kb = Controller()
    with kb.pressed(mod):
        kc = KeyCode.from_char(key)
        kb.press(kc); kb.release(kc)


def set_wallpaper(path: str) -> None:
    ctypes.windll.user32.SystemParametersInfoW(20, 0, str(Path(path).resolve()), 3)


_TEXT_EXT = {
    '.txt', '.py', '.js', '.ts', '.md', '.json', '.yaml', '.yml',
    '.html', '.css', '.sh', '.bat', '.ini', '.cfg', '.log', '.csv',
    '.xml', '.toml', '.rs', '.go', '.java', '.c', '.cpp', '.h',
}


def search_files(pattern: str, root: Path, max_results: int = 20) -> list[tuple[str, int, str]]:
    results = []
    pat = pattern.lower()
    for path in root.rglob('*'):
        if len(results) >= max_results:
            break
        if not path.is_file() or path.suffix.lower() not in _TEXT_EXT:
            continue
        try:
            for i, line in enumerate(
                path.read_text(encoding='utf-8', errors='ignore').splitlines(), 1
            ):
                if pat in line.lower():
                    results.append((str(path), i, line.strip()[:100]))
                    if len(results) >= max_results:
                        break
        except (PermissionError, OSError):
            pass
    return results


def scan_junk() -> dict[str, tuple[int, int]]:
    results = {}
    _scan_dir(Path(os.environ.get('TEMP', 'C:\\Temp')), 'Temp', None, results)
    _scan_dir(Path.home() / 'Downloads', 'Old Downloads (>30d)',
              time.time() - 30 * 24 * 3600, results)
    return results


def _scan_dir(path: Path, label: str, cutoff, out: dict) -> None:
    total, count = 0, 0
    try:
        for f in path.rglob('*'):
            try:
                if f.is_file():
                    st = f.stat()
                    if cutoff is None or st.st_mtime < cutoff:
                        total += st.st_size
                        count += 1
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    if count:
        out[label] = (total, count)


def do_cleanup(categories: list[str]) -> int:
    freed = 0
    if 'Temp' in categories:
        freed += _clean_dir(Path(os.environ.get('TEMP', 'C:\\Temp')), None)
    if 'Old Downloads (>30d)' in categories:
        freed += _clean_dir(Path.home() / 'Downloads', time.time() - 30 * 24 * 3600)
    return freed


def _clean_dir(path: Path, cutoff) -> int:
    freed = 0
    try:
        for f in path.rglob('*'):
            try:
                if f.is_file():
                    st = f.stat()
                    if cutoff is None or st.st_mtime < cutoff:
                        freed += st.st_size
                        f.unlink()
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return freed
