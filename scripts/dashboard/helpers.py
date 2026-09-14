"""helpers.py — small utility functions used across the dashboard."""
import html
import json
import os
import re
from datetime import datetime


def esc(x: object) -> str:
    return html.escape(str(x), quote=True)


def read_json(path: str, default=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return default


def read_lines(path: str, limit: int = 5000) -> list:
    try:
        with open(path, errors="replace") as fh:
            return fh.read().splitlines()[:limit]
    except Exception:
        return []


def read_tail(path: str, n: int = 300) -> list:
    """Last *n* lines of a live log."""
    try:
        with open(path, errors="replace") as fh:
            lines = fh.read().splitlines()
        return lines[-n:] if n > 0 else lines
    except Exception:
        return []


def read_file(path: str) -> str:
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""


def fmt_size(n: float) -> str:
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024
    return f"{n:.1f}G"


def fmt_time(ts) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.astimezone().strftime("%b %d %Y %I:%M %p")
    except Exception:
        return str(ts)


def mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0


def age(path: str) -> str:
    t = mtime(path)
    if not t:
        return "—"
    return datetime.fromtimestamp(t).strftime("%b %d %I:%M %p")


def count_files(path: str) -> int:
    if os.path.isdir(path):
        return len(os.listdir(path))
    return 0


def word_count(path: str) -> int:
    try:
        return len(read_file(path).split())
    except Exception:
        return 0


def redact(s: str) -> str:
    s = str(s)
    if not s:
        return "—"
    if len(s) <= 8:
        return "•" * len(s)
    return s[:4] + "•" * (len(s) - 8) + s[-4:]


def sha(data: str) -> str:
    import hashlib
    return hashlib.sha256(data.encode()).hexdigest()


def short_ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")
