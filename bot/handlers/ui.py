def bar(pct: float, width: int = 16) -> str:
    filled = max(0, min(width, round(pct / 100 * width)))
    return '█' * filled + '░' * (width - filled)
