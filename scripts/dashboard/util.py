"""Hackbot dashboard — util module.

Split from the original single-file scripts/dashboard-web.py.
Function bodies are extracted verbatim.
"""
import hashlib
import os
import re
import json
import time
import html
import shutil
import subprocess
import sys
import glob
import unicodedata
import urllib.parse
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import SKILL_DIRS
# UNRESOLVED: hashlib (same-module or missing)
# UNRESOLVED: json (same-module or missing)
# UNRESOLVED: mtime (same-module or missing)
# UNRESOLVED: os (same-module or missing)
# UNRESOLVED: read_file (same-module or missing)

def esc(x):
    return html.escape(str(x), quote=True)

def read_json(path, default=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return default

def read_lines(path, limit=5000):
    try:
        with open(path, errors="replace") as fh:
            return fh.read().splitlines()[:limit]
    except Exception:
        return []

def read_tail(path, n=300):
    """Last n lines of a live log (tail semantics for the console view)."""
    try:
        with open(path, errors="replace") as fh:
            lines = fh.read().splitlines()
        return lines[-n:] if n > 0 else lines
    except Exception:
        return []

def read_file(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""

def fmt_size(n):
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}G"

def fmt_time(ts):
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.astimezone().strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return str(ts)

def fmt_ts(ts):
    """Format an epoch-seconds float/int as a human date string."""
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return str(ts)

def fmt_rel(ts):
    """Compact relative time ('20m ago') for mobile/space-constrained UIs."""
    if not ts:
        return "—"
    try:
        d = time.time() - float(ts)
    except Exception:
        return str(ts)
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)}m ago"
    if d < 86400:
        return f"{int(d // 3600)}h ago"
    if d < 86400 * 7:
        return f"{int(d // 86400)}d ago"
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%b %d")
    except Exception:
        return str(ts)

def ts_key(ts):
    """Numeric sort/filter key for a timestamp that may be epoch-seconds
    (int/float or numeric string) or an ISO-8601 string such as
    '2026-09-15T13:31:50Z'. Returns 0.0 when the value is unusable."""
    if not ts:
        return 0.0
    if isinstance(ts, (int, float)):
        return float(ts)
    s = str(ts).strip()
    try:
        return float(s)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0

def mtime(path):
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0

def age(path):
    return datetime.fromtimestamp(mtime(path)).strftime("%b %d %I:%M %p")

def rel(path, root):
    return os.path.relpath(path, root)

def count_files(path):
    n = 0
    if os.path.isdir(path):
        for _ in os.listdir(path):
            n += 1
    return n

def word_count(path):
    try:
        return len(read_file(path).split())
    except Exception:
        return 0

def trunc(s, n=19):
    """Truncate a string to *n* characters for on-screen display, appending an
    ellipsis when shortened. Returns a tuple (display, full)."""
    s = str(s)
    if len(s) <= n:
        return s, s
    return s[: n - 1] + "…", s

def redact(s):
    s = str(s)
    if not s:
        return "—"
    if len(s) <= 8:
        return "•" * len(s)
    return s[:4] + "•" * (len(s) - 8) + s[-4:]

def sha(data):
    import hashlib
    return hashlib.sha256(data.encode()).hexdigest()

def short_ts():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

def skill_dirs():
    out = []
    for base in SKILL_DIRS:
        if os.path.isdir(base):
            for d in sorted(os.listdir(base)):
                p = os.path.join(base, d)
                if os.path.isdir(p) and os.path.isfile(os.path.join(p, "SKILL.md")):
                    out.append((d, p))
    return out


_URL_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*://)?[^\s/?#]+")
_HANDLE_RE = re.compile(r"^[a-z0-9-]{1,64}$")
