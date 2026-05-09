import sys
import winreg
from pathlib import Path

_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "UniController"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VBS_PATH = _PROJECT_ROOT / "run.vbs"


def _startup_cmd() -> str:
    return f'wscript.exe "{_VBS_PATH}"'


def install() -> str:
    if sys.platform != "win32":
        return "Startup daemon only supported on Windows."
    if not _VBS_PATH.exists():
        return f"run.vbs not found at {_VBS_PATH}"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, _startup_cmd())
        return f"✅ Startup daemon installed.\nRuns on next login via:\n<code>{_startup_cmd()}</code>"
    except Exception as e:
        return f"❌ Install failed: {e}"


def uninstall() -> str:
    if sys.platform != "win32":
        return "Startup daemon only supported on Windows."
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _REG_NAME)
        return "✅ Startup daemon removed."
    except FileNotFoundError:
        return "Startup daemon was not installed."
    except Exception as e:
        return f"❌ Uninstall failed: {e}"


def status() -> str:
    if sys.platform != "win32":
        return "Startup daemon only supported on Windows."
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, _REG_NAME)
        return f"🟢 Installed\n<code>{val}</code>"
    except FileNotFoundError:
        return "🔴 Not installed"
    except Exception as e:
        return f"❌ Status check failed: {e}"
