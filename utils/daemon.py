import subprocess
import sys
from pathlib import Path

_TASK_NAME = "UniController"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VBS_PATH = _PROJECT_ROOT / "run.vbs"


def _task_exists() -> bool:
    r = subprocess.run(
        ['schtasks', '/query', '/tn', _TASK_NAME],
        capture_output=True, text=True
    )
    return r.returncode == 0


def install() -> str:
    if sys.platform != "win32":
        return "Startup daemon only supported on Windows."
    if not _VBS_PATH.exists():
        return f"run.vbs not found at {_VBS_PATH}"
    if _task_exists():
        return "Already installed. Runs automatically at login."
    r = subprocess.run(
        [
            'schtasks', '/create',
            '/tn', _TASK_NAME,
            '/tr', f'wscript.exe "{_VBS_PATH}"',
            '/sc', 'onlogon',
            '/f',
        ],
        capture_output=True, text=True
    )
    if r.returncode == 0:
        return "Startup task installed. Runs on next login."
    return f"Install failed: {r.stderr.strip()}"


def uninstall() -> str:
    if sys.platform != "win32":
        return "Startup daemon only supported on Windows."
    if not _task_exists():
        return "Startup task is not installed."
    r = subprocess.run(
        ['schtasks', '/delete', '/tn', _TASK_NAME, '/f'],
        capture_output=True, text=True
    )
    if r.returncode == 0:
        return "Startup task removed."
    return (
        "Could not remove automatically (task was created with elevated privileges).\n"
        "Open Task Scheduler → Task Scheduler Library → delete <b>UniController</b> manually."
    )


def status() -> str:
    if sys.platform != "win32":
        return "Startup daemon only supported on Windows."
    r = subprocess.run(
        ['schtasks', '/query', '/tn', _TASK_NAME, '/fo', 'LIST', '/v'],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        return "Not installed"
    last_run = next(
        (l.split(':', 1)[-1].strip() for l in r.stdout.splitlines() if 'Last Run Time' in l),
        "unknown"
    )
    last_result = next(
        (l.split(':', 1)[-1].strip() for l in r.stdout.splitlines() if 'Last Result' in l),
        "?"
    )
    return f"Installed\nlast run: {last_run}  exit: {last_result}"

