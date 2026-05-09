import asyncio
import re
import threading
import time
from pathlib import Path

import psutil


class WatchRule:
    def __init__(self, rule_id: int, description: str, check_fn, chat_id: int):
        self.rule_id = rule_id
        self.description = description
        self.check_fn = check_fn
        self.chat_id = chat_id
        self._last_alerted: float = 0.0
        self._cooldown: float = 300.0  # 5 min between repeat alerts


class WatchEngine:
    def __init__(self):
        self._rules: list[WatchRule] = []
        self._next_id = 1
        self._lock = threading.Lock()
        self._bot = None
        self._loop = None

    def init(self, bot, loop: asyncio.AbstractEventLoop) -> None:
        self._bot = bot
        self._loop = loop
        threading.Thread(target=self._run, daemon=True).start()

    def add_rule(self, description: str, check_fn, chat_id: int) -> int:
        rule = WatchRule(self._next_id, description, check_fn, chat_id)
        with self._lock:
            self._rules.append(rule)
            self._next_id += 1
        return rule.rule_id

    def remove(self, rule_id: int) -> bool:
        with self._lock:
            for i, r in enumerate(self._rules):
                if r.rule_id == rule_id:
                    self._rules.pop(i)
                    return True
        return False

    def list_rules(self) -> list[WatchRule]:
        with self._lock:
            return list(self._rules)

    def _run(self) -> None:
        while True:
            time.sleep(10)
            with self._lock:
                rules = list(self._rules)
            for rule in rules:
                try:
                    alert = rule.check_fn()
                    if alert and time.time() - rule._last_alerted > rule._cooldown:
                        rule._last_alerted = time.time()
                        asyncio.run_coroutine_threadsafe(
                            self._bot.send_message(rule.chat_id, text=f"[watch] {alert}"),
                            self._loop
                        )
                except Exception:
                    pass


_engine = WatchEngine()


def parse_and_add(args: list[str], chat_id: int) -> str | None:
    """Parse a watch rule from args. Returns description or None if unparseable."""
    full = ' '.join(args)
    low = full.lower()

    # cpu > N
    m = re.match(r'cpu\s*>\s*(\d+)', low)
    if m:
        threshold = float(m.group(1))
        def _check():
            cpu = psutil.cpu_percent(interval=1)
            return f"CPU at {cpu:.0f}% (> {threshold:.0f}%)" if cpu > threshold else None
        desc = f"CPU > {threshold:.0f}%"
        _engine.add_rule(desc, _check, chat_id)
        return desc

    # ram > N
    m = re.match(r'ram\s*>\s*(\d+)', low)
    if m:
        threshold = float(m.group(1))
        def _check():
            pct = psutil.virtual_memory().percent
            return f"RAM at {pct:.0f}% (> {threshold:.0f}%)" if pct > threshold else None
        desc = f"RAM > {threshold:.0f}%"
        _engine.add_rule(desc, _check, chat_id)
        return desc

    # disk free < N gb/mb
    m = re.match(r'disk\s+free\s*<\s*(\d+)\s*(gb|mb)?', low)
    if m:
        n, unit = float(m.group(1)), (m.group(2) or 'gb')
        limit = n * (1024 ** 3 if unit == 'gb' else 1024 ** 2)
        def _check():
            free = psutil.disk_usage('C:\\').free
            if free < limit:
                return f"Disk free: {free / 1024**3:.1f} GB (< {n:.0f} {unit.upper()})"
        desc = f"Disk free < {n:.0f} {unit.upper()}"
        _engine.add_rule(desc, _check, chat_id)
        return desc

    # process "name" exits
    m = re.match(r'process\s+["\']?([^"\']+?)["\']?\s+exits?', low)
    if m:
        pname = m.group(1).strip().lower()
        def _check():
            names = {(p.info.get('name') or '').lower() for p in psutil.process_iter(['name'])}
            if not any(pname in n for n in names):
                return f"Process '{pname}' has exited"
        desc = f"Process '{pname}' exits"
        _engine.add_rule(desc, _check, chat_id)
        return desc

    # file <path> changes
    m = re.match(r'file\s+(.+?)\s+changes?$', low)
    if m:
        fpath = Path(m.group(1).strip())
        state = [fpath.stat().st_mtime if fpath.exists() else None]
        def _check():
            if not fpath.exists():
                return None
            mtime = fpath.stat().st_mtime
            if state[0] is not None and mtime != state[0]:
                state[0] = mtime
                return f"File changed: {fpath.name}"
            state[0] = mtime
        desc = f"File '{fpath.name}' changes"
        _engine.add_rule(desc, _check, chat_id)
        return desc

    return None
