"""helpers.py — small utility functions used across the dashboard."""
import base64
import glob
import html
import json
import os
import re
from datetime import datetime

from .config import HUNTS_ROOT
from .config import SESSIONS_ROOT


def resolve_hunt_root(name: str) -> str:
    """Resolve a target handle to its actual hunt directory.

    Hunt dirs are created as ``<handle>-<date>`` by the worker pool, but
    queue entries and report URLs only carry the bare ``<handle>``.  Try
    exact match in HUNTS_ROOT first, then date-suffixed glob, then
    SESSIONS_ROOT (for legacy session-recording dirs that lack reports/).
    """
    # 1. exact match in HUNTS_ROOT  (preferred — has reports/evidence)
    exact = os.path.join(HUNTS_ROOT, name)
    if os.path.isdir(exact):
        return exact
    # 2. date-suffixed fallback in HUNTS_ROOT  (challenge-0326-intigriti-io-20260915)
    matches = sorted(
        glob.glob(os.path.join(HUNTS_ROOT, name + "-*")),
        key=os.path.getmtime,
        reverse=True,
    )
    if matches:
        # Prefer a date-suffixed dir that actually contains reports. A
        # shell dir with an empty reports/ (created by a worker that then
        # wrote to SESSIONS_ROOT instead) would otherwise shadow the real
        # report and 404 every /report/<handle>/<file> URL.
        for m in matches:
            rp = os.path.join(m, "reports")
            if os.path.isdir(rp) and os.listdir(rp):
                return m
    # 3. SESSIONS_ROOT  (legacy session-recording dirs)
    sess = os.path.join(SESSIONS_ROOT, name)
    if os.path.isdir(sess):
        return sess
    if matches:
        return matches[0]
    return exact  # fall through for 404 logic


def esc(x: object) -> str:
    return html.escape(str(x), quote=True)


def read_json(path: str, default=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return default


def read_jsonl(path: str) -> list:
    """Read a JSONL file that may contain multi-line (pretty-printed) objects.

    Entries are normally one compact JSON object per line, but a manually
    edited or externally written entry can span several lines.  A naive
    line-by-line ``json.loads`` silently drops those.  This uses
    ``raw_decode`` to walk the whole file, extracting each top-level JSON
    value regardless of how it is formatted.
    """
    try:
        with open(path, errors="replace") as fh:
            text = fh.read()
    except Exception:
        return []
    out = []
    dec = json.JSONDecoder()
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        try:
            obj, i = dec.raw_decode(text, i)
        except Exception:
            # skip to next line on garbage so one bad entry can't kill the file
            nl = text.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


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


_CHEVRON_SVG = ('<svg class="chev ic-svg" width="14" height="14" viewBox="0 0 24 24" fill="none" '
                'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '<polyline points="9 18 15 12 9 6"/></svg>')


_ANSI_STRIP = re.compile(
    r"\x1b\[[0-9;]*m|\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Za-z0-9]|\x1b."
)


def _is_prompt(line: str) -> bool:
    """True if a log line is a shell prompt (``$ command``)."""
    return bool(re.match(r"^\s*\$\s", _ANSI_STRIP.sub("", line)))


def render_log_html(text: str, *, max_shown: int = 5) -> str:
    """Render log text with per-command collapsible blocks.

    Each shell command (a line starting with ``$ ``) becomes a
    ``<details class="clp-cmd">`` block, open by default: the command is
    the summary, the output is the body. The body is CSS-clamped to the
    first *max_shown* lines; a clickable ``+N more lines`` note appears
    when output is longer. Clicking the shown text or the note toggles
    the ``expanded`` class (full output). Text before the first command
    is rendered verbatim.
    """
    from .ansi import ansi_to_html

    lines = text.splitlines()
    blocks: list = []  # ("text", content) | ("cmd", cmd, output)
    cur_kind = "text"
    cur_text: list = []
    cur_cmd: str | None = None
    cur_out: list = []

    def flush():
        nonlocal cur_kind, cur_text, cur_cmd, cur_out
        if cur_kind == "text" and cur_text:
            blocks.append(("text", "\n".join(cur_text)))
        elif cur_kind == "cmd" and cur_cmd is not None:
            blocks.append(("cmd", cur_cmd, "\n".join(cur_out)))
        cur_text = []
        cur_cmd = None
        cur_out = []

    for line in lines:
        if _is_prompt(line):
            flush()
            cur_kind = "cmd"
            cur_cmd = line
        elif cur_kind == "cmd":
            if line.rstrip().endswith("\\"):
                cur_cmd += "\n" + line
            else:
                cur_out.append(line)
        else:
            cur_text.append(line)
    flush()

    out = []
    for b in blocks:
        if b[0] == "text":
            out.append(ansi_to_html(b[1]))
            continue
        _kind, cmd, output = b
        out_lines = output.splitlines() if output else []
        n = len(out_lines)
        cmd_text = _ANSI_STRIP.sub("", cmd).strip()
        h = sha(cmd)[:12]
        hint = f"{n} lines" if n else ""
        out_html = ansi_to_html(output) if output else ""
        more = (f'<button class="clp-more" type="button">… +{n - max_shown} more lines</button>'
                if n > max_shown else "")
        body = f'<div class="clp-out">{out_html}</div>{more}'
        out.append(
            f'<details class="clp-cmd" data-cmd="{h}" open>'
            f'<summary>{_CHEVRON_SVG}<span class="cmd">{esc(cmd_text)}</span>'
            f'<span class="hint">{hint}</span></summary>{body}</details>'
        )
    return "\n".join(out)


def clp_toggle_js() -> str:
    """Inline JS that makes command-block output expand/collapse on click.

    Clicking the shown output text or the ``+N more lines`` note toggles
    the ``expanded`` class on the parent ``details.clp-cmd`` (full output
    vs 5-line clamp). A drag guard keeps text selection working. Uses
    document-level delegation so it works wherever the blocks live.
    Returns raw JS (no <script> wrapper) for use with page(scripts=...).
    """
    return (
        "(function(){"
        "var downX=0,downY=0;"
        "document.addEventListener('mousedown',function(e){downX=e.clientX;downY=e.clientY;});"
        "document.addEventListener('click',function(e){"
        "var t=e.target;"
        "if(Math.abs(e.clientX-downX)>5||Math.abs(e.clientY-downY)>5)return;"
        "var d=t.closest?t.closest('details.clp-cmd'):null;"
        "if(!d)return;"
        "if(t.classList&&(t.classList.contains('clp-more')||t.classList.contains('clp-out'))){"
        "d.classList.toggle('expanded');"
        "}"
        "});"
        "})();"
    )


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
