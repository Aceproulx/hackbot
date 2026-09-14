"""helpers.py — small utility functions used across the dashboard."""
import base64
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


_CV_START = re.compile(r"^\s*(?:\$\s*)?curl\b")
_CV_METHOD = re.compile(r"-\w*[Xx]\s+([A-Z]+)|\-\-request\s+([A-Z]+)")
_CV_URL = re.compile(r"https?://[^\s'\"\\]+")


def _cv_units(text: str) -> list:
    """Split a block of text into individual curl commands.

    A command starts on a line beginning with ``curl`` (optionally with a
    ``$`` prompt) and swallows following lines joined by trailing backslashes.
    """
    cmds = []
    lines = text.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        if not _CV_START.match(lines[i]):
            i += 1
            continue
        parts = [lines[i]]
        j = i + 1
        while j < n and lines[j].rstrip().endswith("\\"):
            parts.append(lines[j])
            j += 1
        if len(parts) > 1 and j < n and lines[j].strip() and not lines[j].lstrip().startswith("#"):
            parts.append(lines[j])
            j += 1
        cmds.append("\n".join(parts))
        i = j
    return cmds


def _cv_label(cmd: str) -> str:
    m = _CV_METHOD.search(cmd)
    method = ((m.group(1) or m.group(2)) if m else "GET")
    u = _CV_URL.search(cmd)
    if u:
        url = u.group(0).rstrip(".,;")
        host = re.sub(r"^https?://", "", url).split("/", 1)[0]
        path = "/" + url.split("://", 1)[-1].split("/", 1)[1] if "/" in url.split("://", 1)[-1] else ""
        return f"{method} {host}{path[:60]}"
    return method


_RAW_REQ = re.compile(
    r"^\s*(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE|CONNECT)\s+\S+\s+HTTP/\d(?:\.\d)?\s*$",
    re.I,
)


def _raw_units(text: str) -> list:
    """Split a block into raw HTTP request units.

    A unit starts with a request line (``METHOD target HTTP/x.y``) and runs
    until the next one. Surrounding header wraps with no request line (e.g. a
    pasted HTTP *response*) are ignored.
    """
    units = []
    cur = None
    for ln in text.splitlines():
        if _RAW_REQ.match(ln):
            if cur:
                units.append("\n".join(cur))
            cur = [ln]
        elif cur is not None:
            cur.append(ln)
    if cur:
        units.append("\n".join(cur))
    return units


def _raw_label(raw: str) -> str:
    m = re.match(r"^\s*(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE|CONNECT)\s+(\S+)", raw, re.I)
    if not m:
        return "HTTP"
    target = m.group(2)
    if target.startswith(("http://", "https://")):
        target = re.sub(r"^https?://[^/]*", "", target) or "/"
    return "%s %s" % (m.group(1).upper(), target[:60])


def decorate_curls(rendered_html: str) -> str:
    """Post-process rendered markdown / evidence text.

    Every <pre> block that contains curl commands or raw HTTP requests is
    wrapped in a ``.cv-wrap`` container with a control bar of per-unit play
    buttons. Everything else is left byte-for-byte untouched, so reports and
    evidence still render exactly as before unless the "curl verify" toggle is
    on (body.cv-on).
    """
    ent = html.unescape

    def repl(m):
        inner = m.group(1)
        cm = re.match(r"^\s*<code[^>]*>(.*?)</code>\s*$", inner, re.S)
        raw = ent(ent(cm.group(1) if cm else inner))
        units = _cv_units(raw)
        kind = "curl"
        if not units:
            units = _raw_units(raw)
            kind = "raw"
        if not units:
            return m.group(0)
        chips = []
        for i, u in enumerate(units, 1):
            lbl = _cv_label(u) if kind == "curl" else _raw_label(u)
            chips.append(
                '<button class="cv-chip" data-k="%s" data-curl="%s" onclick="cvRun(this)">'
                '<span class="tri">▶</span>%d · %s</button>'
                % (kind, base64.b64encode(u.encode("utf-8", "replace")).decode(), i, esc(lbl))
            )
        return (
            '<div class="cv-wrap">'
            '<div class="cv-ctl">' + "".join(chips)
            + '<span class="cv-hint">executes on server</span></div>'
            + m.group(0)
            + '<div class="cv-out" hidden></div></div>'
        )

    return re.sub(r"<pre(?:\s[^>]*)?>(.*?)</pre>", repl, rendered_html, flags=re.S)


def render_markdown(text) -> str:
    """Render markdown to safe HTML. Falls back to a plain pre block on error."""
    try:
        import mistune
        md = mistune.create_markdown(escape=True, plugins=["strikethrough", "url", "task_lists", "table"])
        return md(text or "")
    except Exception:
        return f'<pre class="pread">{esc(text)}</pre>'


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
