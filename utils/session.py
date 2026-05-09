import threading
import time

_lock = threading.Lock()
_last_seen: float = 0.0
_events: list[tuple[float, str]] = []


def touch() -> float:
    """Mark user active. Returns idle seconds since last touch."""
    global _last_seen
    with _lock:
        now = time.time()
        idle = now - _last_seen if _last_seen else 0.0
        _last_seen = now
        return idle


def log_event(text: str) -> None:
    with _lock:
        _events.append((time.time(), text))
        if len(_events) > 100:
            _events.pop(0)


def pop_events() -> list[tuple[float, str]]:
    with _lock:
        evts = list(_events)
        _events.clear()
        return evts


def last_seen() -> float:
    with _lock:
        return _last_seen
