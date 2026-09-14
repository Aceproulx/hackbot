#!/usr/bin/env python3
"""Hackbot web dashboard — Wild Hunt-style operator UI.

Single-file, stdlib-only (http.server). Reads live hackbot state:
  {{HACKBOT_MISC_DIR}}/{target-queue.json, worker-pool/pool.json, findings.jsonl}
  ~/Projects/hunts/...  (run dirs + per-target session dirs)
Renders light-beige operator console with dark hero banners.
"""
import argparse
import glob
import html
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
MISC = os.environ.get("HACKBOT_MISC", "{{HACKBOT_MISC_DIR}}")
MISC = os.path.expanduser(MISC)
HUNTS_ROOT = os.path.expanduser("~/Projects/hunts")
SESSIONS_ROOT = os.path.join(HUNTS_ROOT, "sessions")
CONFIG_PATH = os.path.expanduser("~/.hackbot/config.json")

QUEUE_FILE = os.path.join(MISC, "target-queue.json")
POOL_FILE = os.path.join(MISC, "worker-pool", "pool.json")
FINDINGS_FILE = os.path.join(MISC, "findings.jsonl")
REPORTS_DIR = os.path.join(MISC, "reports")
SKILL_DIRS = [
    os.path.expanduser("~/.config/opencode/skill"),
    os.path.expanduser("~/.agents/skills"),
    os.path.expanduser("~/.gemini/skills"),
]


# ── config ─────────────────────────────────────────────────────────────────────

def load_config():
    try:
        with open(CONFIG_PATH) as fh:
            return json.load(fh)
    except Exception:
        return {}


def cfg_dir(key, default):
    v = load_config().get(key) or default
    return os.path.expanduser(v)


CONFIG = load_config()
PAYLOADS_DIR = cfg_dir("payloads_dir", "{{PAYLOADS_DIR}}")
HACKBOT_MISC_DIR = cfg_dir("hackbot_misc_dir", MISC)
SESSIONS_CFG = cfg_dir("sessions_dir", SESSIONS_ROOT)
PLATFORM = CONFIG.get("platform", "opencode")
EMAIL_BASE = CONFIG.get("email_base", "{{INTIGRITI_USERNAME}}")
EMAIL_DOMAIN = CONFIG.get("email_domain", "{{EMAIL_DOMAIN}}")
TELEGRAM_TOKEN = CONFIG.get("telegram_bot_token", "")
TELEGRAM_CHAT = CONFIG.get("telegram_chat_id", "")
INTIGRITI_USER = CONFIG.get("intigriti_username", "")
MAX_SLOTS = CONFIG.get("max_worker_slots", 2)
PORT_HTTP = CONFIG.get("port_http", 8080)
PORT_HTTPS = CONFIG.get("port_https", 8081)


# ── small helpers ──────────────────────────────────────────────────────────────

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


# ── ANSI → HTML ────────────────────────────────────────────────────────────────

_ANSI_C16 = ["#3b4048", "#e06c75", "#98c379", "#e5c07b", "#61afef", "#c678dd", "#56b6c2", "#d8dee4",
             "#5c6370", "#ff6b6b", "#a8e05f", "#ffd866", "#82aaff", "#c792ea", "#73d0ff", "#ffffff"]


def _xterm_rgb(n):
    if n < 16:
        return _ANSI_C16[n]
    if n < 232:
        n -= 16
        comps = [0, 95, 135, 175, 215, 255]
        return "#%02x%02x%02x" % (comps[n // 36], comps[(n // 6) % 6], comps[n % 6])
    v = 8 + (n - 232) * 10
    return "#%02x%02x%02x" % (v, v, v)


def ansi_to_html(s):
    """Convert ANSI SGR escape sequences to inline-styled HTML; strip other CSI/OSC escapes."""
    if not s:
        return ""
    fg = bg = None
    bold = italic = underline = False
    out = []
    open_span = False
    pending = ""
    ptr = 0

    def style_str():
        st = []
        if bold:
            st.append("font-weight:700")
        if italic:
            st.append("font-style:italic")
        if underline:
            st.append("text-decoration:underline")
        if fg:
            st.append("color:" + fg)
        if bg:
            st.append("background:" + bg)
        return ";".join(st)

    def close_span():
        nonlocal open_span
        if open_span:
            out.append("</span>")
            open_span = False

    def emit_text(text):
        """Append escaped text under the pending style (lazy span-open)."""
        nonlocal pending
        if not text:
            return
        if pending:
            out.append('<span style="%s">' % pending)
            out.append(html.escape(text))
            out.append("</span>")
            pending = ""
        else:
            out.append(html.escape(text))

    def apply(params):
        nonlocal fg, bg, bold, italic, underline
        if not params:
            params = [0]
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                fg = bg = None
                bold = italic = underline = False
            elif p == 1:
                bold = True
            elif p == 3:
                italic = True
            elif p == 4:
                underline = True
            elif p == 22:
                bold = False
            elif p == 23:
                italic = False
            elif p == 24:
                underline = False
            elif 30 <= p <= 37:
                fg = _ANSI_C16[p - 30]
            elif 90 <= p <= 97:
                fg = _ANSI_C16[p - 90 + 8]
            elif p == 39:
                fg = None
            elif 40 <= p <= 47:
                bg = _ANSI_C16[p - 40]
            elif 100 <= p <= 107:
                bg = _ANSI_C16[p - 100 + 8]
            elif p == 49:
                bg = None
            elif p in (38, 48) and i + 1 < len(params) and params[i + 1] == 5 and i + 2 < len(params):
                col = _xterm_rgb(params[i + 2])
                i += 2
                if p == 38:
                    fg = col
                else:
                    bg = col
            elif p in (38, 48) and i + 1 < len(params) and params[i + 1] == 2 and i + 4 < len(params):
                col = "#%02x%02x%02x" % (params[i + 2], params[i + 3], params[i + 4])
                i += 4
                if p == 38:
                    fg = col
                else:
                    bg = col
            i += 1

    for m in re.finditer(
            r"\x1b\[([0-9;]*)m"
            r"|\x1b\[[0-9;?]*[A-Za-z]"
            r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
            r"|\x1b[()][A-Za-z0-9]"
            r"|\x1b.",
            s):
        if m.start() > ptr:
            emit_text(s[ptr:m.start()])
        ptr = m.end()
        tok = m.group(0)
        if tok.startswith("\x1b[") and tok.endswith("m"):
            apply([int(x) for x in m.group(1).split(";") if x])
            close_span()
            pending = style_str() or ""
    if ptr < len(s):
        emit_text(s[ptr:])
    close_span()
    return "".join(out)


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


# ── state readers ──────────────────────────────────────────────────────────────

def get_queue():
    data = read_json(QUEUE_FILE, [])
    if not isinstance(data, list):
        return []
    return data


def get_pool():
    return read_json(POOL_FILE, {})


def get_workers():
    pool = get_pool()
    return pool.get("workers", [])


def get_findings():
    lines = read_lines(FINDINGS_FILE, 100000)
    out = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


def get_run_dirs():
    out = []
    if os.path.isdir(HUNTS_ROOT):
        for d in sorted(os.listdir(HUNTS_ROOT)):
            p = os.path.join(HUNTS_ROOT, d)
            if d == "sessions" or not os.path.isdir(p):
                continue
            m = re.match(r"(.+)-(\d{8})$", d)
            out.append({"name": d, "handle": m.group(1) if m else d, "path": p,
                        "kind": "RUN", "mtime": mtime(p)})
    return out


def get_session_dirs():
    out = []
    if os.path.isdir(SESSIONS_ROOT):
        for d in sorted(os.listdir(SESSIONS_ROOT)):
            p = os.path.join(SESSIONS_ROOT, d)
            if not os.path.isdir(p):
                continue
            out.append({"name": d, "handle": d, "path": p,
                        "kind": "SESSION", "mtime": mtime(p)})
    return out


def workers_by_handle():
    return {w.get("handle"): w for w in get_workers()}


# ── icons (inline SVG, Lucide-style) ───────────────────────────────────────────

ICONS = {
    "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "compass": '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
    "dashboard": '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "activity": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    "git-branch": '<line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>',
    "book-open": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    "package": '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
    "star": '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/>',
    "folder": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22 6 12 13 2 6"/>',
    "bar-chart-2": '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
    "sliders": '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>',
    "terminal": '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
    "pause": '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "arrow-left": '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
    "arrow-right": '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
    "file-text": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>',
    "archive": '<rect x="2" y="3" width="20" height="5" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><line x1="10" y1="12" x2="14" y2="12"/>',
    "key": '<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>',
    "message-square": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "moon": '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
    "clipboard-list": '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><line x1="9" y1="12" x2="9" y2="12.01"/><line x1="15" y1="12" x2="15" y2="12.01"/><line x1="9" y1="16" x2="9" y2="16.01"/><line x1="15" y1="16" x2="15" y2="16.01"/>',
    "trending-up": '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
    "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>',
    "sitemap": '<rect x="9" y="2" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="16" y="16" width="6" height="6" rx="1"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="5" y1="16" x2="5" y2="12"/><line x1="19" y1="16" x2="19" y2="12"/><line x1="12" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="12" y2="12"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "check-circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "send": '<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',
    "server": '<rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>',
    "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    "external-link": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
    "alert-triangle": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "inbox": '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
}


def icon(name, size=16, cls=""):
    body = ICONS.get(name, ICONS["compass"])
    base = '<svg class="ic-svg %s" width="%d" height="%d" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    return (base % (esc(cls), size, size)) + body + "</svg>"


# ── design system ──────────────────────────────────────────────────────────────

CSS = """
:root {
  --canvas:#f7f4ee; --sidebar:#efe8dd; --card:#ffffff; --border:#e1d9cc;
  --ink:#242019; --muted:#8c8579; --accent:#8f1618; --accent-hi:#a4161a;
  --deep:#160d0c; --green:#1a7a43; --amber:#b96b00; --grey:#9a938a;
  --shadow:0 1px 2px rgba(40,25,10,.05), 0 4px 16px rgba(40,25,10,.05);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--canvas);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,system-ui,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.mono,pre,code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}

/* layout */
.layout{display:flex;min-height:100vh}
.main{flex:1;margin-left:244px;min-width:0}
.sidebar{position:fixed;left:0;top:0;bottom:0;width:244px;background:var(--sidebar);border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:50}

/* logo */
.logo{display:flex;align-items:center;gap:10px;padding:18px 16px 14px;border-bottom:1px solid var(--border)}
.logo .mark{width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,#1a0f0e,#4a1d16);display:flex;align-items:center;justify-content:center;font-size:18px;color:#f4e9dc;box-shadow:inset 0 0 0 1px rgba(255,255,255,.12)}
.logo .brand{font-weight:800;letter-spacing:.14em;font-size:15px;color:#2c231c}
.logo .sub{font-size:10px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;font-weight:600}

/* sidebar nav */
.nav{flex:1;overflow-y:auto;padding:12px 8px 120px}
.nav .sec{margin:16px 4px 6px;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.nav a{display:flex;align-items:center;gap:9px;padding:7px 10px;margin:1px 0;border-radius:8px;color:#3d352b;font-weight:500;font-size:13.5px;position:relative}
.nav a:hover{background:rgba(255,255,255,.65);text-decoration:none}
.nav a.active{background:rgba(143,22,24,.07);font-weight:700;color:var(--accent)}
.nav a.active::before{content:"";position:absolute;left:-8px;top:4px;bottom:4px;width:3px;border-radius:2px;background:var(--accent)}
.nav a .ic{width:16px;text-align:center;font-size:14px;opacity:.85}
.ic-svg{vertical-align:-3px;display:inline-block;flex:none}
.nav a .ct{position:relative}
.badge{display:inline-flex;margin-left:auto;min-width:18px;height:18px;padding:0 5px;border-radius:9px;background:var(--accent);color:#fff;font-size:10.5px;font-weight:700;align-items:center;justify-content:center}
.badge.neutral{background:#d8d0c2;color:#6c6455}

/* console tab on sidebar right edge */
.console-tab{position:fixed;left:216px;top:47%;transform:rotate(180deg);writing-mode:vertical-rl;background:#111;color:#7ee787;font:600 11px/1 ui-monospace,monospace;letter-spacing:.22em;padding:12px 7px;border-radius:0 10px 10px 0;border:1px solid #000;cursor:pointer;z-index:60;box-shadow:0 2px 10px rgba(0,0,0,.35)}
.console-tab:hover{background:#1a1a1a;color:#a5f3b0}

/* top bar */
.topbar{position:sticky;top:0;z-index:40;display:flex;align-items:center;gap:14px;padding:12px 26px;background:rgba(247,244,238,.92);backdrop-filter:blur(6px);border-bottom:1px solid var(--border)}
.searchbox{flex:1;max-width:420px;position:relative}
.searchbox input{width:100%;padding:8px 12px 8px 34px;border:1px solid var(--border);border-radius:9px;background:#fff;font-size:13px;color:var(--ink);outline:none}
.searchbox input:focus{border-color:var(--accent)}
.searchbox .glass{position:absolute;left:11px;top:8px;color:var(--muted);font-size:13px}
.topbar .grow{flex:1}
.gridicon{background:#fff;border:1px solid var(--border);border-radius:8px;width:34px;height:34px;display:grid;place-items:center;color:#6c6455;font-size:14px;cursor:pointer}
.gridicon:hover{color:var(--accent)}
.attention{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:20px;background:rgba(143,22,24,.08);color:var(--accent);font-size:12.5px;font-weight:600;border:1px solid rgba(143,22,24,.18)}
.attention .n{background:var(--accent);color:#fff;border-radius:9px;min-width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;padding:0 5px;font-size:11px;font-weight:800}
.btn{background:var(--accent);color:#fff;border:none;border-radius:8px;padding:8px 16px;font:600 13px -apple-system,sans-serif;cursor:pointer;display:inline-flex;align-items:center;gap:7px;box-shadow:0 1px 3px rgba(143,22,24,.35)}
.btn:hover{background:var(--accent-hi);text-decoration:none}
.btn.ghost{background:#fff;color:#3d352b;border:1px solid var(--border);box-shadow:none}
.btn.ghost:hover{color:var(--accent);border-color:#d8c4b8}
.btn.small{padding:4px 10px;font-size:12px;border-radius:7px}

/* hero banner */
.hero{position:relative;padding:38px 34px 32px;color:#f6efe4;background:
  radial-gradient(1200px 500px at 85% -20%, rgba(176,58,46,.42), transparent 60%),
  radial-gradient(900px 420px at 0% 120%, rgba(60,20,20,.55), transparent 55%),
  linear-gradient(135deg,#170d0c 0%,#2a1310 48%,#3b1c12 100%);
  border-bottom:1px solid #0d0807;box-shadow:inset 0 -40px 60px -60px rgba(0,0,0,.5)}
.hero h1{font-size:30px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}
.hero .sub{color:#d9c9b8;font-size:13px;margin-top:6px;max-width:720px}
.hero .topline{display:flex;align-items:center;gap:14px;margin-bottom:14px}
.back{display:inline-flex;align-items:center;gap:6px;color:#e8d9c8;font-size:12.5px;font-weight:600;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);padding:5px 12px;border-radius:7px}
.back:hover{background:rgba(255,255,255,.16);color:#fff;text-decoration:none}

/* content */
.content{padding:22px 26px 60px}
.row{display:flex;gap:16px;flex-wrap:wrap}
.col{flex:1;min-width:340px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);margin-bottom:18px;overflow:hidden}
.card .hd{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid #eee8dd;font-weight:700;font-size:13px;letter-spacing:.02em}
.card .hd .sp{flex:1}
.card .hd .hint{font-size:11.5px;color:var(--muted);font-weight:500}
.card .bd{padding:14px 16px}
.card.narrow{min-width:340px}

/* stat cards */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:20px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 18px;box-shadow:var(--shadow);position:relative}
.stat .lab{font-size:11px;font-weight:700;letter-spacing:.1em;color:var(--muted);text-transform:uppercase}
.stat .val{font-size:26px;font-weight:800;margin-top:6px;letter-spacing:.01em}
.stat .sub{font-size:11.5px;color:var(--muted);margin-top:4px}

/* tables */
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:8px 12px;color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:8px 12px;border-bottom:1px solid #f0eadf;vertical-align:top}
tr:last-child td{border-bottom:none}
tbody tr:hover{background:#fbf8f3}
td.num{text-align:right;font-variant-numeric:tabular-nums}
th.num{text-align:right}

/* pills */
.pill{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:20px;font-size:11.5px;font-weight:600;white-space:nowrap}
.pill .dot{width:7px;height:7px;border-radius:50%;background:currentColor;flex:none}
.pill.green{background:#e5f4ea;color:var(--green)}
.pill.grey{background:#efebe4;color:#7a7266}
.pill.red{background:#fae7e5;color:var(--accent)}
.pill.amber{background:#fcf0dc;color:var(--amber)}
.pill.blue{background:#e7eefb;color:#2f5cb0}
.pill.gold{background:#faf0d9;color:#8a6a14}
.pill.mono{font-family:ui-monospace,monospace}

/* hunt cards */
.hgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}
.hcard{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:8px}
.hcard .t{font-weight:700;font-size:14px;display:flex;align-items:center;gap:8px;word-break:break-all}
.hcard .m{font-size:12px;color:var(--muted)}
.hcard .foot{display:flex;align-items:center;gap:8px;margin-top:2px}
.filter-item{transition:opacity .15s}
.hide-js{display:none !important}

/* tabs */
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--border);margin-bottom:16px;flex-wrap:wrap}
.tabs .t{padding:8px 14px;border-radius:9px 9px 0 0;font-weight:600;font-size:13px;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent}
.tabs .t.active{color:var(--accent);border-bottom-color:var(--accent);background:rgba(143,22,24,.04)}
.tabs .t .cnt{font-size:10.5px;background:#e9e2d5;border-radius:8px;padding:1px 6px;margin-left:5px;color:#6c6455}

/* donut */
.donut-wrap{display:flex;align-items:center;gap:26px;padding:18px 22px;flex-wrap:wrap}
.donut{position:relative;width:168px;height:168px;border-radius:50%;flex:none}
.donut .core{position:absolute;inset:24px;background:#fff;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:inset 0 0 0 1px var(--border)}
.donut .core .big{font-size:22px;font-weight:800}
.donut .core .sm{font-size:10px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
.legend{display:flex;flex-direction:column;gap:7px;min-width:200px}
.legend .lg{display:flex;align-items:center;gap:9px;font-size:12.5px}
.legend .sw{width:10px;height:10px;border-radius:3px;flex:none}
.legend .name{flex:1}
.legend .pct{font-weight:700;font-variant-numeric:tabular-nums}
.range-pills{display:flex;gap:6px;margin:10px 16px 0;flex-wrap:wrap}
.range-pills .r{padding:4px 12px;border-radius:14px;border:1px solid var(--border);font-size:11.5px;font-weight:600;color:var(--muted);cursor:pointer}
.range-pills .r.active{background:var(--accent);border-color:var(--accent);color:#fff}

/* console terminal */
.terminal{background:#0d0f12;color:#d8dee4;font:12.5px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;padding:16px 18px;border-radius:0 0 12px 12px;overflow-x:auto;white-space:pre-wrap;word-break:break-word}
.terminal .k{color:#e06c75}.terminal .g{color:#98c379}.terminal .c{color:#5c6370}.terminal .y{color:#e5c07b}.terminal .b{color:#61afef}
.console-bar{display:flex;align-items:center;gap:12px;padding:10px 16px;background:#0a0c0f;border-bottom:1px solid #23272d;color:#9aa4b0;font-size:12px}
.console-bar .title{font-weight:700;color:#e5eaf0;display:flex;align-items:center;gap:8px}
.console-bar select{background:#16191e;color:#d8dee4;border:1px solid #2c3138;border-radius:6px;padding:4px 8px;font-size:12px;font-family:inherit}
.console-bar .btn.ghost{background:#16191e;color:#d8dee4;border-color:#2c3138;box-shadow:none}
.console-bar .btn.ghost:hover{color:#fff;border-color:#3a414c;background:#1e222a}
.console-bar .btn.ghost:disabled{opacity:.35;cursor:not-allowed;background:#16191e;color:#555b66}

/* modal + toasts */
.modal-bg{position:fixed;inset:0;background:rgba(20,12,10,.45);z-index:100;display:none;align-items:flex-start;justify-content:center;padding-top:9vh}
.modal{background:#fff;border-radius:14px;width:520px;max-width:94vw;box-shadow:0 20px 60px rgba(0,0,0,.35);overflow:hidden}
.modal .hd{padding:14px 18px;background:var(--sidebar);border-bottom:1px solid var(--border);font-weight:700;display:flex;align-items:center}
.modal .bd{padding:16px 18px;max-height:60vh;overflow-y:auto}
.modal .bd code{display:block;background:#0d0f12;color:#d8dee4;padding:9px 12px;border-radius:8px;font-size:12px;margin:6px 0 14px;white-space:pre-wrap}
.cmdhelp{list-style:none}
.cmdhelp li{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px dashed #eee8dd;font-size:12.5px}
.cmdhelp li:last-child{border-bottom:none}
.cmdhelp .cc{font-family:ui-monospace,monospace;color:var(--accent);font-weight:600}

/* empty state */
.empty{text-align:center;color:var(--muted);padding:46px 20px}
.empty .ic{font-size:34px;opacity:.5;margin-bottom:10px}
.empty .t{font-weight:600;color:#7a7266}

/* filters row */
.fbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.fbar .f{padding:5px 12px;border:1px solid var(--border);border-radius:8px;background:#fff;font-size:12px;color:#555;cursor:pointer}
.fbar .f.active{color:var(--accent);border-color:var(--accent);background:rgba(143,22,24,.05);font-weight:600}

/* misc */
.mt{margin-top:14px}.right{text-align:right}
.muted{color:var(--muted)}.small{font-size:12px}
code.inline{background:#efe9dd;border-radius:5px;padding:1px 6px;font-size:12px}
.pread{white-space:pre-wrap;word-break:break-word;font-size:12.5px;line-height:1.5}
.statline{display:flex;gap:8px;flex-wrap:wrap;font-size:12px;color:var(--muted)}
.breadcrumb{font-size:12px;color:var(--muted);margin-bottom:10px}
.node-link{color:#3d352b;font-weight:600}
"""

NAV = [
    ("WORKSPACE", [
        ("overview", "Overview", "dashboard"),
        ("hunts", "Hunts", "target"),
        ("history", "History", "clock"),
        ("monitors", "Monitors", "activity"),
        ("topology", "Topology", "git-branch"),
    ]),
    ("LIBRARY", [
        ("knowledge", "Knowledge", "book-open"),
        ("memory", "Memory", "database"),
        ("assets", "Assets", "package"),
        ("skills", "Skills", "star"),
    ]),
    ("MANAGE", [
        ("workspaces", "Workspaces", "folder"),
        ("desktops", "Desktops", "monitor"),
        ("registrations", "Registrations", "mail"),
        ("usage", "Usage", "bar-chart-2"),
        ("settings", "Settings", "sliders"),
    ]),
]


def pill(state, label=None):
    s = str(state).lower()
    if s in ("running", "active", "connected", "enabled", "open", "ready", "paid", "confirmed", "hunting"):
        return f'<span class="pill green"><span class="dot"></span>{esc(label or state)}</span>'
    if s in ("idle", "pending", "history", "drained", "stopped", "disabled"):
        return f'<span class="pill grey"><span class="dot"></span>{esc(label or state)}</span>'
    if s in ("cancelled", "failed", "dismissed", "closed", "attention", "vuln"):
        return f'<span class="pill red"><span class="dot"></span>{esc(label or state)}</span>'
    if s in ("starting", "draining", "review", "needs-work"):
        return f'<span class="pill amber"><span class="dot"></span>{esc(label or state)}</span>'
    if s in ("investigation", "hackerone", "private-program", "submissions-open", "intigriti"):
        return f'<span class="pill blue"><span class="dot"></span>{esc(label or state)}</span>'
    return f'<span class="pill grey">{esc(label or state)}</span>'


def severity_pill(sev):
    sev = (sev or "").lower()
    m = {"critical": "red", "high": "red", "medium": "amber", "low": "grey", "p0": "red", "p1": "red", "p2": "amber", "p3": "grey", "p4": "grey", "info": "blue", "informational": "blue"}
    return pill(m.get(sev, "grey"), sev.upper() or "—")


def need_attention():
    n = 0
    for f in get_findings():
        st = f.get("status", "").lower()
        if st not in ("paid", "dismissed", "informational", "closed", "n/a"):
            n += 1
    return n


def sidebar(active):
    rows = []
    for sec, items in NAV:
        rows.append(f'<div class="sec">{esc(sec)}</div>')
        for key, label, ic in items:
            cls = " active" if key == active else ""
        rows.append(
            f'<a class="{cls.strip()}" href="/v/{key}">'
            f'<span class="ic">{icon(ic)}</span><span>{esc(label)}</span></a>')
    return "".join(rows)


def masthead(left=None, right=None):
    cells = []
    if left:
        cells.append(f'<div class="grow">{left}</div>')
    if right:
        cells.append(right)
    return "".join(cells)


def topbar(active_q=None):
    att = need_attention()
    att_html = (f'<span class="attention"><span class="n">{att}</span>{"need attention" if att != 1 else "needs attention"}</span>'
                if att > 0 else
                f'<span class="attention" style="background:#efebe4;color:#7a7266;border-color:#e6dfd2"><span class="n" style="background:#b9b0a2">{att}</span>need attention</span>')
    att_html = f'<span class="attention" style="background:#efebe4;color:#7a7266;border-color:#e6dfd2"><span class="n" style="background:#b9b0a2">{att}</span>all clear</span>'
    q = f' value="{esc(active_q or "")}"' if active_q else ""
    return f"""
<div class="topbar">
  <div class="searchbox">{icon('search', 16, 'glass')}
    <input id="globalsearch" placeholder="Search this view…" data-filter="filter-item" data-key="data-search"{q}></div>
  <div class="grow"></div>
  <div class="gridicon" title="Grid">{icon('grid')}</div>
  {att_html}
  <button class="btn" onclick="document.getElementById('taskmodal').style.display='flex'">{icon('plus', 15)} New Task</button>
</div>"""


def hero(title, sub=None, back=None, crown=None, raw=False):
    t = f'<h1>{title if raw else esc(title)}</h1>'
    s = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    bl = (f'<a class="back" href="{back}">{icon("arrow-left", 14)} Back</a>' if back else "")
    cr = crown or ""
    return (f'<div class="hero"><div class="topline">{bl}{cr}</div>{t}{s}</div>')


def page(active, hero_html, body, refresh=0, extra_css="", scripts=""):
    r = ('<meta http-equiv="refresh" content="%d">' % int(refresh)) if refresh else ""
    refresh = int(refresh)  # noqa
    return (
        '<!doctype html>\n<html lang="en"><head>\n'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>Hackbot · ' + NAV_TITLES.get(active, "Operator") + '</title>' + r + '\n'
        '<style>' + CSS + extra_css + '</style></head>\n<body>\n'
        '<div class="layout">\n'
        '  <aside class="sidebar">\n'
        '    <div class="logo"><div class="mark">' + icon('compass', 18) + '</div>\n'
        '      <div><div class="brand">HACKBOT</div><div class="sub">' + esc(PLATFORM) + ' operator</div></div></div>\n'
        '    <nav class="nav">' + sidebar(active) + '</nav>\n'
        '  </aside>\n'
        '  <div class="console-tab" onclick="location.href=\'/console\'">CONSOLE</div>\n'
        '  <main class="main">\n'
        + topbar() + '\n'
        + hero_html + '\n'
        + '    <div class="content">' + body + '</div>\n'
        '  </main>\n</div>\n'
        '<div class="modal-bg" id="taskmodal" onclick="if(event.target===this)this.style.display=\'none\'">\n'
        '  <div class="modal"><div class="hd">New Task</div><div class="bd">\n'
        '    <p class="small muted" style="margin-bottom:10px">Tasks are orchestrated from the operator terminal. Useful commands:</p>\n'
        '    <ul class="cmdhelp">\n'
        '      <li><span class="cc">hackbot-workers start --slots ' + str(MAX_SLOTS) + '</span> <span class="muted">Launch worker pool</span></li>\n'
        '      <li><span class="cc">hackbot-workers stop &lt;slot&gt;</span> <span class="muted">Stop a worker</span></li>\n'
        '      <li><span class="cc">hackbot-queue next</span> <span class="muted">Pick next ranked target</span></li>\n'
        '      <li><span class="cc">hackbot-dashboard serve</span> <span class="muted">This dashboard</span></li>\n'
        '      <li><span class="cc">hackbot-dashboard add &lt;program&gt; &lt;severity&gt; &lt;title&gt;</span> <span class="muted">Log a finding</span></li>\n'
        '    </ul>\n'
        '  </div></div>\n</div>\n'
        '<script>\n'
        'function filterViews(){var q=(document.getElementById(\'globalsearch\')||{}).value||"";q=q.toLowerCase();\n'
        'document.querySelectorAll(\'[data-filter]\').forEach(function(el){if(el===sb)return;var hay=((el.getAttribute(\'data-search\')||"")+" "+(el.textContent||"")).toLowerCase();el.style.display=hay.indexOf(q)===-1?"none":"";});}\n'
        'var sb=document.getElementById(\'globalsearch\');\n'
        'if(sb)sb.addEventListener(\'input\',filterViews);\n'
        'function showTab(group,id){document.querySelectorAll(\'[data-tabgroup="\'+group+\'"]\').forEach(function(t){t.style.display=(t.id===id)?"":"none";});document.querySelectorAll(\'[data-tabbtn="\'+group+\'"]\').forEach(function(b){b.classList.toggle(\'active\',b.getAttribute(\'data-target\')===id);});}\n'
        + scripts +
        '</script>\n</body></html>'
    )


NAV_TITLES = {k: (lbl + " · Hackbot") for _, items in NAV for k, lbl, _ in items}
NAV_TITLES["hunt"] = "Hunt · Hackbot"
NAV_TITLES["console"] = "Console · Hackbot"
NAV_TITLES["report"] = "Report · Hackbot"
NAV_TITLES["overview"] = "Overview · Hackbot"


# ── views ──────────────────────────────────────────────────────────────────────

def v_overview():
    findings = get_findings()
    workers = get_workers()
    queue = get_queue()
    runs = get_run_dirs()
    sess = get_session_dirs()
    confirmed = [f for f in findings if str(f.get("status", "")).lower() in ("confirmed", "paid")]
    est = sum(float(f.get("bounty_est") or 0) for f in confirmed)
    paid = sum(float(f.get("bounty_paid") or 0) for f in findings)
    active_w = [w for w in workers if w.get("status") == "running"]
    pending = [t for t in queue if t.get("status") == "pending"]
    top = sorted(queue, key=lambda t: float(t.get("score") or 0), reverse=True)[:6]

    stats = ""
    st = [
        ("Findings", len(findings), f"{len(confirmed)} confirmed", "clipboard-list"),
        ("Est. Bounty", f"${est:,.0f}", f"${paid:,.0f} paid", "trending-up"),
        ("Workers", f"{len(active_w)}/{max(len(workers),1)}", "active lanes", "cpu"),
        ("Queue", f"{len(pending)}", "programs pending", "target"),
        ("Hunts", len(runs), f"{len(sess)} sessions", "sitemap"),
    ]
    for lab, val, sub, ic in st:
        stats += (f'<div class="stat"><div class="lab">{icon(ic, 13)} {lab}</div>'
                  f'<div class="val">{val}</div><div class="sub">{sub}</div></div>')
    stats = f'<div class="stats">{stats}</div>'

    hero_html = hero("Overview", f"{len(queue)} programs queued · {len(active_w)} workers hunting · {PLATFORM} platform")

    wr = ""
    if workers:
        rows = []
        for w in workers:
            rows.append(f'<tr><td style="font-weight:700">{esc(w.get("id",""))}</td>'
                        f'<td class="mono">{esc(w.get("handle",""))}</td>'
                        f'<td>{pill(w.get("status",""))}</td>'
                        f'<td class="num">{w.get("bugs_found",0)}</td>'
                        f'<td>{fmt_time(w.get("started_at"))}</td>'
                        f'<td class="num">${float(w.get("max_bounty") or 0):,.0f}</td>'
                        f'<td><a href="/console?w={esc(w.get("id",""))}">log →</a></td></tr>')
        wr = (f'<div class="card"><div class="hd">Active Workers '
              f'<span class="sp"></span><span class="hint">worker pool · max {MAX_SLOTS} lanes</span></div>'
              f'<table><thead><tr><th>ID</th><th>TARGET</th><th>STATE</th><th class="num">BUGS</th>'
              f'<th>STARTED</th><th class="num">MAX BX</th><th></th></tr></thead>'
              f'<tbody>{"".join(rows)}</tbody></table></div>')
    else:
        wr = (f'<div class="card"><div class="bd"><div class="empty"><div class="ic">{icon("moon", 34)}</div>'
              f'<div class="t">No workers running</div><p>Start the pool from the terminal:</p>'
              f'<p><code class="inline">hackbot-workers start --slots {MAX_SLOTS}</code></p></div></div></div>')

    qrows = "".join(
        f'<tr><td><a class="node-link" href="/v/assets?target={esc(t.get("handle",""))}">{esc(t.get("name",""))}</a>'
        f' <span class="mono small muted">{esc(t.get("handle",""))}</span></td>'
        f'<td>{pill(t.get("status","pending"))}</td>'
        f'<td class="num">${float(t.get("max_bounty") or 0):,.0f}</td>'
        f'<td class="num">{float(t.get("score") or 0):.0f}</td>'
        f'<td>{fmt_time(t.get("last_hunted"))}</td></tr>'
        for t in top)
    queue_card = (f'<div class="card"><div class="hd">Target Queue <span class="sp"></span>'
                  f'<span class="hint">top by score</span></div>'
                  f'<table><thead><tr><th>PROGRAM</th><th>STATE</th><th class="num">MAX BX</th>'
                  f'<th class="num">SCORE</th><th>LAST HUNT</th></tr></thead>'
                  f'<tbody>{qrows}</tbody></table></div>')

    fr = ""
    if findings:
        rows = "".join(
            f'<tr><td>{severity_pill(f.get("severity"))}</td>'
            f'<td style="font-weight:600">{esc(f.get("title",""))}</td>'
            f'<td class="mono">{esc(f.get("program",""))}</td>'
            f'<td>{pill(f.get("status",""))}</td>'
            f'<td class="num">${float(f.get("bounty_est") or 0):,.0f}</td>'
            f'<td>{fmt_time(f.get("ts") or f.get("reported_at"))}</td></tr>'
            for f in reversed(findings[-6:]))
        fr = (f'<div class="card"><div class="hd">Recent Findings <span class="sp"></span>'
              f'<span class="hint">last {min(6,len(findings))}</span></div>'
              f'<table><thead><tr><th>SEV</th><th>TITLE</th><th>PROGRAM</th><th>STATUS</th>'
              f'<th class="num">EST</th><th>LOGGED</th></tr></thead><tbody>{rows}</tbody></table></div>')
    else:
        fr = (f'<div class="card"><div class="bd"><div class="empty"><div class="ic">{icon("clipboard-list", 34)}</div>'
              f'<div class="t">No findings logged yet</div><p>Workers are hunting; logs land in findings.jsonl.</p></div></div></div>')

    hr = ""
    recent = sorted(runs + sess, key=lambda h: h["mtime"], reverse=True)[:6]
    if recent:
        cards = "".join(
            f'<div class="hcard filter-item" data-filter="filter-item" data-search="{esc(h["name"])} {esc(h["handle"])} {esc(h["kind"])}">'
            f'<div class="t">{pill(h["kind"], "")}{esc(h["name"])}</div>'
            f'<div class="m">{h["kind"]} · {count_files(h["path"])} items · last activity {age(h["path"])}</div>'
            f'<div class="foot"><a class="btn ghost small" href="/hunts?name={esc(h["name"])}">Open →</a></div></div>'
            for h in recent)
        hr = f'<div class="card"><div class="hd">Recent Hunts <span class="sp"></span><span class="hint">runs + sessions</span></div><div class="bd"><div class="hgrid">{cards}</div></div></div>'

    body = stats + f'<div class="row"><div class="col">{wr}{queue_card}</div><div class="col">{fr}{hr}</div></div>'
    return page("overview", hero_html, body, refresh=0)


def run_meta(path):
    files = {}
    if os.path.isdir(path):
        for f in os.listdir(path):
            p = os.path.join(path, f)
            if os.path.isfile(p):
                files[f] = (mtime(p), os.path.getsize(p))
    return files


def get_reading(hpath):
    d = {}
    if not hpath:
        return d
    d["path"] = hpath
    d["name"] = os.path.basename(hpath.rstrip("/"))
    d["mtime"] = mtime(hpath)
    d["files"] = run_meta(hpath) if os.path.isdir(hpath) else {}
    d["log"] = read_file(os.path.join(hpath, "session.log"))
    d["interesting"] = read_file(os.path.join(hpath, "interesting.md"))
    d["creds"] = []
    for f in os.listdir(hpath) if os.path.isdir(hpath) else []:
        if "creds" in f.lower():
            d["creds"].append(f)
    d["scope"] = read_file(os.path.join(hpath, "scope.json"))
    d["session_state"] = read_file(os.path.join(hpath, "session-state.md"))
    d["targets"] = read_file(os.path.join(hpath, "targets.txt"))
    for sub in ("reports", "evidence"):
        p = os.path.join(hpath, sub)
        d[sub] = []
        if os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                fp = os.path.join(p, f)
                if os.path.isfile(fp):
                    d[sub].append(f)
    return d


def hunt_detail(name):
    safe = os.path.basename(os.path.normpath(name))
    hpath = os.path.join(HUNTS_ROOT, safe)
    if not os.path.isdir(hpath):
        return None
    h = get_reading(hpath)
    handle = h["name"]
    if handle.startswith("sessions"):
        return None
    # session dirs live under sessions/<domain>
    if not os.path.exists(hpath) and os.path.isdir(os.path.join(SESSIONS_ROOT, safe)):
        hpath = os.path.join(SESSIONS_ROOT, safe)
    h = get_reading(hpath)
    h["kind"] = "RUN" if os.path.realpath(hpath).startswith(os.path.realpath(HUNTS_ROOT)) else "SESSION"
    handle = h["name"]
    return h


def v_hunts(q=None):
    runs = sorted(get_run_dirs(), key=lambda h: h["mtime"], reverse=True)
    sess = sorted(get_session_dirs(), key=lambda h: h["mtime"], reverse=True)
    workers = workers_by_handle()

    cards = []
    for h in runs + sess:
        active = h["handle"] in workers and workers[h["handle"]].get("status") == "running"
        state = pill("running", "ACTIVE") if active else pill("history", "IDLE")
        files = count_files(h["path"])
        cards.append(
            f'<div class="hcard filter-item" data-filter="filter-item" data-search="{esc(h["name"])} {esc(h["handle"])} {esc(h["kind"])}">'
            f'<div class="t"><span class="mono small">{h["kind"]}</span>{esc(h["name"])}</div>'
            f'<div class="m">{h["handle"]} · {files} items · ⇅ {age(h["path"])}</div>'
            f'<div class="foot">{state}<span class="sp" style="flex:1"></span>'
            f'<a class="btn ghost small" href="/hunts?name={esc(h["name"])}">Open →</a></div></div>')
    grid = f'<div class="hgrid">{"".join(cards) or ""}</div>' if cards else ""
    if not cards:
        grid = f'<div class="card"><div class="bd"><div class="empty"><div class="ic">{icon("target", 34)}</div><div class="t">No hunts yet</div><p>Worker runs create hunt dirs under {esc(os.path.basename(HUNTS_ROOT))}/.</p></div></div></div>'

    body = (f'<div class="card"><div class="bd"><div class="fbar">'
            f'<span class="muted small" style="align-self:center">{len(runs)} runs · {len(sess)} sessions</span>'
            f'<span class="f active" onclick="showTab(\'h\',\'all\')" data-tabbtn="h" data-target="all">All</span>'
            f'<span class="f" onclick="showTab(\'h\',\'active\')" data-tabbtn="h" data-target="active">Active</span>'
            f'<span class="f" onclick="showTab(\'h\',\'done\')" data-tabbtn="h" data-target="done">Finalized</span>'
            f'</div></div></div>'
            f'<div id="tab-all" data-tabgroup="h">{grid}</div>'
            f'<div id="tab-active" data-tabgroup="h" style="display:none">'
            f'<div class="hgrid">{"".join(c for c in [])}</div></div>'
            f'<div id="tab-done" data-tabgroup="h" style="display:none"></div>')
    # make per-group divs for active/done via JS on page: quick inline swap handled by data-search filter instead
    body = (f'<div class="card"><div class="bd"><div class="fbar">'
            f'<span class="muted small" style="align-self:center">{len(runs)} runs · {len(sess)} sessions</span>'
            f'<span class="muted small">use search to filter</span>'
            f'</div></div></div>'
            f'{grid}')
    return page("hunts", hero("Hunts", "Every campaign, per-target session and their working dirs"), body)


def v_hunt(name):
    safe = os.path.basename(os.path.normpath(name or ""))
    if not safe:
        return None
    hpath = os.path.join(HUNTS_ROOT, safe)
    if not os.path.isdir(hpath):
        sdir = os.path.join(SESSIONS_ROOT, safe)
        hpath = sdir if os.path.isdir(sdir) else None
    if not hpath:
        return None
    h = get_reading(hpath)
    h["kind"] = "RUN" if os.path.realpath(hpath).startswith(os.path.realpath(HUNTS_ROOT)) else "SESSION"
    handle = h["name"]
    worker = workers_by_handle().get(handle)
    qitem = next((t for t in get_queue() if t.get("handle") == handle), None)
    findings = [f for f in get_findings() if f.get("program") in (handle, hpath)]
    fl = [f for f in get_findings() if str(f.get("program", "")) == handle or (f.get("program") or "").find(handle) >= 0]

    files = {k: v[0] for k, v in h["files"].items()}
    lead = esc(h["interesting"]) if h["interesting"] else f'<div class="empty"><div class="ic">{icon("file-text", 34)}</div><div class="t">No leads captured</div></div>'
    logview = (f'<pre class="terminal">{esc(h["log"]) or "(no session.log yet)"}</pre>'
               if h["log"] else f'<div class="empty"><div class="ic">{icon("monitor", 34)}</div><div class="t">No console output yet</div></div>')

    cred_txt = ""
    for c in h["creds"]:
        cred_txt += f'<div class="card"><div class="hd mono">{esc(c)}</div><pre class="terminal">{esc(read_file(os.path.join(hpath, c)) or "")}</pre></div>'
    cred_html = cred_txt or f'<div class="empty"><div class="ic">{icon("key", 34)}</div><div class="t">No credentials stored</div></div>'

    rep_rows = []
    for f in h["reports"]:
        fp = os.path.join(hpath, "reports", f)
        rep_rows.append(
            f'<div class="hcard filter-item" data-filter="filter-item" data-search="{esc(f)}">'
            f'<div class="t" style="font-size:12.5px"><a href="/report/{esc(safe)}/{esc(f)}">{icon("file-text", 14)} {esc(f)}</a></div>'
            f'<div class="m">{age(fp)}</div></div>')
    reports_html = (f'<div class="hgrid">{"".join(rep_rows)}</div>'
                    if h["reports"] else '<div class="empty"><div class="t">No reports drafted</div></div>')

    ev_rows = ""
    for f in h["evidence"]:
        fp = os.path.join(hpath, "evidence", f)
        ev_rows += f'<tr><td>{icon("archive", 16)}</td><td class="mono">{esc(f)}</td><td class="num">{count_files(fp) if os.path.isdir(fp) else 1}</td><td>{age(fp)}</td><td><a href="/evidence/{esc(safe)}/{esc(f)}">view →</a></td></tr>'
    evidence_html = (f'<table><thead><tr><th></th><th>NAME</th><th class="num">ITEMS</th><th>UPDATED</th><th></th></tr></thead>'
                     f'<tbody>{ev_rows}</tbody></table>') if h["evidence"] else f'<div class="empty"><div class="ic">{icon("archive", 34)}</div><div class="t">No evidence captured</div></div>'

    state = pill("running", "ACTIVE") if worker and worker.get("status") == "running" else pill("history", "IDLE")
    target = esc(name)
    findings_rows = ""
    for f in fl[-8:]:
        findings_rows += (f'<tr><td>{severity_pill(f.get("severity"))}</td>'
                          f'<td style="font-weight:600">{esc(f.get("title",""))}</td>'
                          f'<td>{pill(f.get("status",""))}</td>'
                          f'<td class="num">${float(f.get("bounty_est") or 0):,.0f}</td>'
                          f'<td>{fmt_time(f.get("ts") or f.get("reported_at"))}</td></tr>')
    findings_html = (f'<table><thead><tr><th>SEV</th><th>TITLE</th><th>STATUS</th>'
                     f'<th class="num">EST</th><th>LOGGED</th></tr></thead><tbody>{findings_rows}</tbody></table>'
                     ) if fl else f'<div class="empty"><div class="ic">{icon("search", 34)}</div><div class="t">No findings for this hunt</div></div>'

    orch = ""
    if qitem:
        orch = (f'<div class="card"><div class="hd">Orchestrator · {esc(qitem.get("handle", ""))}</div>'
                f'<div class="bd"><table><thead><tr><th>FIELD</th><th>VALUE</th></tr></thead><tbody>'
                f'<tr><td>Program</td><td>{esc(qitem.get("name",""))}</td></tr>'
                f'<tr><td>State</td><td>{pill(qitem.get("status",""))}</td></tr>'
                f'<tr><td>Max bounty</td><td>${float(qitem.get("max_bounty") or 0):,.0f}</td></tr>'
                f'<tr><td>Tags</td><td>{" ".join(pill(t) for t in (qitem.get("tags") or []))}</td></tr>'
                f'<tr><td>Confidentiality</td><td>{pill(qitem.get("confidentiality",""), (qitem.get("confidentiality") or "").upper())}</td></tr>'
                f'<tr><td>Score</td><td>{qitem.get("score", 0)}</td></tr>'
                f'<tr><td>Last hunted</td><td>{fmt_time(qitem.get("last_hunted"))}</td></tr>'
                f'<tr><td>Last verdict</td><td>{esc(qitem.get("last_verdict") or "—")}</td></tr>'
                f'<tr><td>Bugs found</td><td>{qitem.get("bugs_found", 0)}</td></tr>'
                f'</tbody></table></div></div>')
    if worker:
        orch += (f'<div class="card"><div class="hd">Worker slot {worker.get("slot")} · {esc(worker.get("id",""))}</div>'
                 f'<div class="bd"><table><tr><td>State</td><td>{pill(worker.get("status",""))}</td></tr>'
                 f'<tr><td>Started</td><td>{fmt_time(worker.get("started_at"))}</td></tr>'
                 f'<tr><td>Bugs found</td><td>{worker.get("bugs_found",0)}</td></tr>'
                 f'<tr><td>Log</td><td><a href="/console?w={esc(worker.get("id",""))}">open console →</a></td></tr></table></div></div>')
    if not orch:
        orch = f'<div class="empty"><div class="ic">{icon("sliders", 34)}</div><div class="t">No orchestrator record for this hunt</div></div>'

    overview = (f'<div class="card"><div class="hd">Overview</div><div class="bd">'
                f'<div class="statline">{pill(h["kind"])}{state}'
                f'<span>⇅ {age(hpath)}</span><span>{len(h["files"])} files</span></div>'
                f'<table style="margin-top:12px"><tbody>'
                f'<tr><td class="muted">Scope</td><td class="mono">{esc(h["name"])}</td></tr>'
                f'<tr><td class="muted">Evidence packs</td><td>{len(h["evidence"])}</td></tr>'
                f'<tr><td class="muted">Reports drafted</td><td>{len(h["reports"])}</td></tr>'
                f'<tr><td class="muted">Credentials</td><td>{", ".join(esc(c) for c in h["creds"]) or "none"}</td></tr>'
                f'</tbody></table></div></div>'
                f'<div class="card"><div class="hd">Feature Map</div>'
                f'<div class="bd"><pre class="pread">{esc(h["session_state"] or "(no feature map captured)")}</pre></div></div>')

    tabs = [
        ("overview", "Overview", overview, True),
        ("features", "Features", lead, False),
        ("creds", "Credentials", cred_html, False),
        ("reports", "Reports", reports_html, False),
        ("evidence", "Sessions / Evidence", evidence_html, False),
        ("chat", "Agent chat", logview, False),
        ("orch", "Orchestrator", orch, False),
    ]
    tb = ""
    for i, (key, lbl, _unused, is_active) in enumerate(tabs):
        cls = " active" if is_active else ""
        tb += f'<span class="t{cls}" onclick="showTab(\'hunt\',\'t-{key}\')" data-tabbtn="hunt" data-target="t-{key}">{lbl}</span>'
    panels = "".join(
        f'<div id="t-{key}" data-tabgroup="hunt" style="display:{"" if active else "none"}">{content}</div>'
        for key, _lbl, content, active in tabs)

    body = f'<div class="breadcrumb">Workspace / Hunts / <b>{esc(target)}</b></div>'
    body += f'<div class="tabs">{tb}</div>{panels}'
    hp = hero(f"<span class='mono'>{esc(target)}</span>",
              sub=f"{esc(h['kind'])} · {esc(os.path.basename(hpath))} · evidence {len(h['evidence'])} · reports {len(h['reports'])} · threads in operator console",
              back="/v/hunts", raw=True)
    return page("hunt", hp, body)


def v_history():
    queue = sorted(get_queue(), key=lambda t: (str(t.get("status") or ""), -(float(t.get("score") or 0))))
    findings = get_findings()

    trows = "".join(
        f'<tr class="filter-item" data-filter="filter-item" data-search="{esc(t.get("handle",""))} {esc(t.get("name",""))}">'
        f'<td><b>{esc(t.get("name",""))}</b> <span class="mono small muted">{esc(t.get("handle",""))}</span></td>'
        f'<td>{pill(t.get("status",""))}</td>'
        f'<td>{" ".join(pill(tg) for tg in (t.get("tags") or [])[:2])}</td>'
        f'<td class="num">${float(t.get("max_bounty") or 0):,.0f}</td>'
        f'<td class="num">{t.get("bugs_found",0)}</td>'
        f'<td>{fmt_time(t.get("last_hunted"))}</td>'
        f'<td>{esc(t.get("last_verdict") or "—")}</td></tr>' for t in queue)
    table = (f'<div class="card"><div class="hd">Target Ledger <span class="sp"></span>'
             f'<span class="hint">{len(queue)} programs</span></div>'
             f'<table><thead><tr><th>PROGRAM</th><th>STATE</th><th>TAGS</th><th class="num">MAX BX</th>'
             f'<th class="num">BUGS</th><th>LAST HUNT</th><th>VERDICT</th></tr></thead><tbody>{trows}</tbody></table></div>')

    frows = "".join(
        f'<tr class="filter-item" data-filter="filter-item" data-search="{esc(f.get("program",""))} {esc(f.get("title",""))}">'
        f'<td>{severity_pill(f.get("severity"))}</td>'
        f'<td style="font-weight:600">{esc(f.get("title",""))}</td>'
        f'<td class="mono">{esc(f.get("program",""))}</td>'
        f'<td>{pill(f.get("status",""))}</td>'
        f'<td class="num">${float(f.get("bounty_est") or 0):,.0f}</td>'
        f'<td>{fmt_time(f.get("ts") or f.get("reported_at"))}</td></tr>' for f in reversed(findings))
    ftable = (f'<div class="card"><div class="hd">Findings Timeline <span class="sp"></span>'
              f'<span class="hint">{len(findings)} logged</span></div>'
              f'<table><thead><tr><th>SEV</th><th>TITLE</th><th>PROGRAM</th><th>STATUS</th>'
              f'<th class="num">EST</th><th>LOGGED</th></tr></thead><tbody>{frows or ""}</tbody></table></div>')

    body = table + ftable
    return page("history", hero("History", "Campaign ledger and findings timeline"), body)


def v_monitors():
    workers = get_workers()
    runs = get_run_dirs()
    att = need_attention()

    active_card = ""
    if workers:
        cards = []
        for w in workers:
            st = w.get("status", "")
            logpath = w.get("log", "")
            prompt_src = read_file(logpath)
            cards.append(
                f'<div class="card filter-item" data-filter="filter-item" data-search="{esc(w.get("handle",""))} {esc(w.get("id",""))}">'
                f'<div class="hd">Auto-mode watchdog · {esc(w.get("handle",""))} '
                f'<span class="sp"></span>{pill(st, st.upper())} <span class="hint">console #{sha(w.get("id",""))[:8]}</span></div>'
                f'<div class="bd"><table><tr><td class="muted">Worker</td><td class="mono">{esc(w.get("id",""))}</td></tr>'
                f'<tr><td class="muted">Started</td><td>{fmt_time(w.get("started_at"))}</td></tr>'
                f'<tr><td class="muted">Max bounty</td><td>${float(w.get("max_bounty") or 0):,.0f}</td></tr>'
                f'<tr><td class="muted">Bugs found</td><td>{w.get("bugs_found",0)}</td></tr></table>'
                f'<details style="margin-top:10px"><summary class="small"><b>View prompt/log</b></summary>'
                f'<pre class="terminal" style="margin-top:8px">{(prompt_src or "(log not readable)")[-4000:]}</pre></details>'
                f'</div></div>')
        active_card = f'{"".join(cards)}'
    else:
        active_card = f'<div class="empty"><div class="ic">{icon("activity", 34)}</div><div class="t">No active monitors</div><p>Start the worker pool to create watchdogs.</p></div>'

    hrows = ""
    for r in runs:
        hrows += (f'<tr class="filter-item" data-filter="filter-item" data-search="{esc(r["name"])}">'
                  f'<td class="mono">{esc(r["name"])}</td><td>{pill("history","FINISHED")}</td>'
                  f'<td>run-{esc(r["name"])}</td><td>{count_files(r["path"])}</td>'
                  f'<td>{age(r["path"])}</td></tr>')
    hcard = (f'<div class="card"><div class="hd">Monitor History <span class="sp"></span>'
             f'<span class="hint">{len(runs)} completed campaigns</span></div>'
             f'<table><thead><tr><th>CAMPAIGN</th><th>STATE</th><th>RUN ID</th>'
             f'<th class="num">FILES</th><th>ENDED</th></tr></thead><tbody>{hrows or ""}</tbody></table></div>')

    body = (f'<div class="tabs"><span class="t active" data-tabbtn="m" data-target="t-a" onclick="showTab(\'m\',\'t-a\')">Active '
            f'<span class="cnt">{len(workers)}</span></span><span class="t" data-tabbtn="m" data-target="t-h" onclick="showTab(\'m\',\'t-h\')">History '
            f'<span class="cnt">{len(runs)}</span></span></div>'
            f'<div id="t-a" data-tabgroup="m">{active_card}</div>'
            f'<div id="t-h" data-tabgroup="m" style="display:none">{hcard}</div>')
    return page("monitors", hero("Monitors", f"Watchdogs, worker lanes and campaign history · {att} items need attention"), body, refresh=0)


def v_topology():
    workers = get_workers()
    runs = get_run_dirs()
    sess = get_session_dirs()
    findings = get_findings()
    by_prog = {}
    for f in findings:
        by_prog.setdefault(f.get("program", "?"), []).append(f)

    nodes = []
    for w in workers:
        mk = "running"
        nodes.append(f'<div class="card narrow filter-item" data-filter="filter-item" data-search="{esc(w.get("handle",""))} worker">'
                      f'<div class="hd">Worker {w.get("slot","?")}</div><div class="bd">'
                      f'<div class="statline">{pill(w.get("status",""),"")} · ${float(w.get("max_bounty") or 0):,.0f} max</div>'
                      f'<a class="btn ghost small" style="margin-top:10px" href="/console?w={esc(w.get("id",""))}">Console →</a></div></div>')
    for r in runs:
        prog = r["handle"]
        w_active = prog in workers_by_handle() and workers_by_handle()[prog].get("status") == "running"
        fcount = len(by_prog.get(prog, []))
        nodes.append(f'<div class="card narrow filter-item" data-filter="filter-item" data-search="{esc(prog)}">'
                     f'<div class="hd">{icon("target", 16)} {esc(prog)}</div><div class="bd">'
                     f'<div class="statline">{pill("running","HUNTING") if w_active else pill("history","SLEEP")}'
                     f' · {fcount} findings · {count_files(r["path"])} files</div></div></div>')
    for s in sess:
        fcount = len(by_prog.get(s["handle"], []))
        nodes.append(f'<div class="card narrow filter-item" data-filter="filter-item" data-search="{esc(s["handle"])}">'
                     f'<div class="hd">{icon("archive", 16)} {esc(s["handle"])}</div><div class="bd">'
                     f'<div class="statline">session · {fcount} findings · {count_files(s["path"])} files</div>'
                     f'<a class="btn ghost small" style="margin-top:10px" href="/hunts?name={esc(s["name"])}">Open →</a></div></div>')
    grid = f'<div class="hgrid">{"".join(nodes)}</div>'
    body = (f'<div class="card"><div class="bd"><div class="fbar">'
            f'<span class="muted small">relationship graph — targets, workers, sessions, findings</span></div></div></div>'
            + grid)
    return page("topology", hero("Topology", "How hunts, workers, sessions and findings connect"), body)


def search_memory(q):
    q = (q or "").lower().strip()
    hits = []
    roots = []
    if os.path.isdir(HUNTS_ROOT):
        roots.append(HUNTS_ROOT)
    for root, dirs, files in os.walk(HUNTS_ROOT):
        if any(part.startswith(".") for part in root.split(os.sep)):
            continue
        for f in files:
            if not f.endswith((".md", ".log", ".txt", ".json")):
                continue
            p = os.path.join(root, f)
            try:
                with open(p, errors="replace") as fh:
                    content = fh.read()
            except Exception:
                continue
            if q and q not in content.lower() and q not in os.path.basename(p).lower():
                continue
            shots = []
            if q:
                for m in re.finditer(re.escape(q), content.lower()):
                    s = max(0, m.start() - 60)
                    shots.append("…" + content[s:m.end() + 90].replace("\n", " ") + "…")
                    if len(shots) >= 2:
                        break
            hits.append({"path": p, "name": f, "size": os.path.getsize(p),
                         "mtime": mtime(p), "words": len(content.split()), "shots": shots})
    hits.sort(key=lambda h: h["mtime"], reverse=True)
    return hits


def v_knowledge(q=None):
    hits = search_memory(q)
    rows = ""
    for i, hh in enumerate(hits[:50]):
        rel = os.path.relpath(hh["path"], HUNTS_ROOT)
        preview = hh["shots"][0] if hh["shots"] else ""
        rows += (f'<tr class="filter-item" data-filter="filter-item" data-search="{esc(hh["name"])} {esc(rel)}">'
                 f'<td class="mono">{rel}</td>'
                 f'<td class="num">{hh["words"]}</td>'
                 f'<td class="num">{fmt_size(hh["size"])}</td>'
                 f'<td>{fmt_time(hh["mtime"])}</td>'
                 f'<td class="pread" style="max-width:340px">{esc(preview[:180])}</td></tr>')
    empty = (f'<div class="empty"><div class="ic">{icon("book-open", 34)}</div>'
             '<div class="t">No memory records match</div></div>') if not rows else ""
    body = (f'<div class="card"><div class="bd"><div class="fbar">'
            f'<input style="flex:1;max-width:340px;padding:8px 12px;border:1px solid var(--border);border-radius:8px;font-size:13px" '
            f'placeholder="Semantic search across hunt memory (notes, logs, recon)…" value="{esc(q or "")}" '
            f'onkeydown="if(event.key===\'Enter\')location.href=\'/v/knowledge?q=\'+encodeURIComponent(this.value)"></span>'
            f'<span class="muted small" style="align-self:center">{len(hits)} records</span></div></div></div>'
            f'<div class="card"><div class="hd">Memory Search <span class="sp"></span>'
            f'<span class="hint">reads recorded from {esc(os.path.basename(HUNTS_ROOT))}/</span></div>'
            f'<table><thead><tr><th>SOURCE</th><th class="num">WORDS</th><th class="num">SIZE</th>'
            f'<th>READ</th><th>MATCH</th></tr></thead><tbody>{rows if rows else empty}</tbody></table></div>')
    return page("knowledge", hero("Knowledge", "A searchable memory of hunts, notes and recon reads"), body)


def v_memory():
    hits = search_memory("")
    cards = ""
    for hh in hits[:24]:
        rel = os.path.relpath(hh["path"], HUNTS_ROOT)
        s = os.path.basename(os.path.dirname(hh["path"]))
        cards += (f'<div class="hcard filter-item" data-filter="filter-item" data-search="{esc(s)} {esc(hh["name"])}">'
                  f'<div class="t" style="font-size:12.5px"><span class="mono small">{esc(s)}</span>{esc(hh["name"])}</div>'
                  f'<div class="m">{hh["words"]} words · {fmt_size(hh["size"])} · {age(hh["path"])}</div>'
                  f'<div class="foot"><span class="sp" style="flex:1"></span>'
                  f'<a class="btn ghost small" href="/v/knowledge?q={esc(hh["name"].replace(".md","").replace(".txt",""))}">browse →</a></div></div>')
    body = (f'<div class="hgrid">{cards}</div>' if cards
            else f'<div class="card"><div class="bd"><div class="empty"><div class="ic">{icon("database", 34)}</div><div class="t">Memory is empty</div></div></div></div>')
    return page("memory", hero("Memory", "Hunt notes, recon and session state"), body)


def v_assets(q=None):
    queue = sorted(get_queue(), key=lambda t: -(float(t.get("max_bounty") or 0)))
    handlers = {}
    for w in get_workers():
        handlers[w.get("handle")] = w
    rows = "".join(
        f'<tr class="filter-item" data-filter="filter-item" data-search="{esc(t.get("handle",""))} {esc(t.get("name",""))}">'
        f'<td><b>{esc(t.get("name",""))}</b></td>'
        f'<td class="mono">{esc(t.get("handle",""))}</td>'
        f'<td>{pill(t.get("status",""))}</td>'
        f'<td class="num">{esc(t.get("program_id","")[:8])}</td>'
        f'<td class="num">${float(t.get("max_bounty") or 0):,.0f}</td>'
        f'<td>{" ".join(pill(tg) for tg in (t.get("tags") or [])[:3])}</td>'
        f'<td>{pill("running","HUNTING") if t.get("handle") in handlers and handlers[t.get("handle")].get("status") == "running" else pill("idle","IDLE")}</td></tr>'
        for t in queue)
    body = (f'<div class="card"><div class="hd">In-Scope Targets <span class="sp"></span>'
            f'<span class="hint">{len(queue)} programs · {sum(1 for t in queue if t.get("status")=="active")} active</span></div>'
            f'<table><thead><tr><th>PROGRAM</th><th>HANDLE</th><th>STATE</th><th class="num">ID</th>'
            f'<th class="num">MAX BX</th><th>TAGS</th><th>WORKER</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return page("assets", hero("Assets", "Every in-scope program with bounty, tags and hunt state"), body)


def skill_info(path):
    raw = read_file(path)
    lines = raw.splitlines()
    name = os.path.basename(os.path.dirname(path))
    desc = ""
    tags = [os.path.basename(os.path.dirname(path))]
    for i, ln in enumerate(lines[:12]):
        if ln.startswith("#"):
            continue
        if ln.startswith("---"):
            continue
        if ln.startswith("description"):
            desc = ln.split(":", 1)[1].strip().strip('"')
            continue
        if not desc and ln.strip():
            desc = ln.strip().strip("*").strip()
            break
    if not desc and len(lines) > 1:
        desc = lines[1].strip()
    return name, desc, tags


def v_skills(view="library", sel=None):
    skills = []
    for name, base in skill_dirs():
        n, desc, tags = skill_info(os.path.join(base, "SKILL.md"))
        skills.append((name, base, desc, tags))
    skills.sort(key=lambda s: s[0])

    if view == "activations":
        total = len(skills)
        body = (f'<div class="fbar" style="margin-bottom:16px">'
                f'<span class="f">Window · Last 30 days</span><span class="f">Agent · Claude + Codex</span>'
                f'<span class="f">Surface · Tasks + consoles</span><span class="f">Role · Root + subagents</span></div>'
                f'<div class="stats">'
                f'<div class="stat"><div class="lab">ACTIVATIONS</div><div class="val">0</div><div class="sub">since usage tracking lands</div></div>'
                f'<div class="stat"><div class="lab">CONTEXTS USING SKILLS</div><div class="val">0</div><div class="sub">of available</div></div>'
                f'<div class="stat"><div class="lab">SKILLS IN LIBRARY</div><div class="val">{total}</div><div class="sub">centrally managed</div></div>'
                f'<div class="stat"><div class="lab">CAPTURE COVERAGE</div><div class="val">—</div><div class="sub">{"(tracking not wired)"}</div></div>'
                f'</div>'
                f'<div class="card"><div class="bd"><div class="empty"><div class="ic">{icon("activity", 34)}</div>'
                f'<div class="t">Activation capture not wired yet</div>'
                f'<p>Skill activations are recorded once the operator console provider reports per-skill usage. '
                f'Library shows the centrally managed skill set below.</p></div></div></div>')
        return page("skills", hero("Skills", "Activations — usage observability for the skill library"),
                    f'<div class="tabs"><a class="t" href="/v/skills?view=library">Library <span class="cnt">{len(skills)}</span></a>'
                    f'<span class="t active">Activations</span></div>' + body)

    sel = (sel or "") or (skills[0][0] if skills else "")
    lb = ""
    for name, base, desc, tags in skills:
        cls = "active" if name == sel else ""
        lb += (f'<a class="filter-item" data-filter="filter-item" data-search="{esc(name)} {esc(" ".join(tags))}" '
               f'href="/v/skills?view=library&sel={esc(name)}" style="display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:8px;'
               f'margin:1px 0;background:{cls and "rgba(143,22,24,.06)" or "transparent"};color:{"var(--accent)" if cls else "#3d352b"};font-weight:{"700" if cls else "500"}">'
               f'<span class="mono small">{esc(name)}</span><span style="flex:1"></span>{pill("enabled","ENABLED") if False else ""}</a>')
    detail = ""
    for name, base, desc, tags in skills:
        if name == sel:
            fpath = os.path.join(base, "SKILL.md")
            raw = read_file(fpath)
            detail = (f'<div class="card"><div class="bd">'
                      f'<div class="hd" style="border:none;padding:0 0 8px">Skill</div>'
                      f'<table><tr><td class="muted" style="width:150px">Name</td><td class="mono">{esc(name)}</td></tr>'
                      f'<tr><td class="muted">ID</td><td class="mono">{esc(name)}</td></tr>'
                      f'<tr><td class="muted">Status</td><td>{pill("enabled")}</td></tr>'
                      f'<tr><td class="muted">Tags</td><td>{" ".join(pill(t) for t in tags)}</td></tr>'
                      f'<tr><td class="muted">Agent skills</td><td>☑ Claude Code&nbsp;&nbsp;☑ Codex</td></tr>'
                      f'<tr><td class="muted">Version</td><td class="mono">latest (from {esc(os.path.basename(base))})</td></tr></table>'
                      f'<div class="hd" style="border:none;padding:12px 0 6px">Description</div>'
                      f'<textarea style="width:100%;min-height:74px;border:1px solid var(--border);border-radius:8px;padding:10px;font:12.5px ui-monospace,monospace;color:#333;background:#fbf9f5" readonly>{esc(desc)}</textarea>'
                      f'<div class="hd" style="border:none;padding:12px 0 6px">Frontmatter</div>'
                      f'<pre class="terminal">{(raw[:1200] + ("…" if len(raw) > 1200 else "")) }</pre>'
                      f'</div></div>')
            break
    if not detail and skills:
        detail = f'<div class="empty"><div class="t">Select a skill</div></div>'

    lib = (f'<div class="row"><div class="col" style="min-width:260px;max-width:340px">'
           f'<div class="card"><div class="hd">Library <span class="sp"></span><span class="hint">{len(skills)}</span></div>'
           f'<div class="bd" style="padding:6px">{lb}</div></div></div>'
           f'<div class="col">{detail}</div></div>')
    body = (f'<div class="tabs"><span class="t active">Library <span class="cnt">{len(skills)}</span></span>'
            f'<a class="t" href="/v/skills?view=activations">Activations</a></div>')
    body += (f'<div style="margin-bottom:12px" class="fbar"><span class="btn ghost small">+ New skill</span>'
             f'<span class="btn ghost small">Refresh</span><span class="btn ghost small">Import from Git or workspace</span></div>')
    body += lib
    return page("skills", hero("Skills", "Centrally managed skill library — routed to Claude Code / Codex"), body)


def v_workspaces():
    data = {
        "Hunts (working dirs)": (HUNTS_ROOT, "r/w", "runs + per-target sessions"),
        "Worker pool": (os.path.join(MISC, "worker-pool"), "r/w", "pool.json + worker logs"),
        "Sessions": (SESSIONS_ROOT, "r/w", "evidence, creds, reports per target"),
        "Payloads": (PAYLOADS_DIR, "r/w", "shared payload collections"),
        "Misc data": (MISC, "r/w", "findings.jsonl, target-queue.json, reports/"),
    }
    cards = ""
    for lab, (path, perm, hint) in data.items():
        n = count_files(path) if os.path.isdir(path) else 0
        cards += (f'<div class="hcard filter-item" data-filter="filter-item" data-search="{esc(lab)}">'
                  f'<div class="t" style="font-size:13px">{esc(lab)}</div>'
                  f'<div class="m mono" style="word-break:break-all">{esc(path)}</div>'
                  f'<div class="m">{n} items · {hint}</div>'
                  f'<div class="foot">{pill("connected","R/W")}<span class="sp" style="flex:1"></span></div></div>')
    body = f'<div class="hgrid">{cards}</div>'
    return page("workspaces", hero("Workspaces", "Operator workspace mounts — read/write accessible, read-only from the terminal"), body)


def v_desktops():
    runs = get_run_dirs()
    sess = get_session_dirs()
    cards = ""
    for h in runs + sess:
        st = pill("running", "Running") if h["handle"] in workers_by_handle() else pill("idle", "Idle")
        cards += (f'<div class="hcard filter-item" data-filter="filter-item" data-search="{esc(h["name"])}">'
                  f'<div class="t" style="font-size:12.5px"><span class="mono">{esc(h["name"])}</span></div>'
                  f'<div class="m">lease {age(h["path"])} · {count_files(h["path"])} items</div>'
                  f'<div class="foot">{st}<span class="sp" style="flex:1"></span>'
                  f'<a class="btn ghost small" href="/console?d={esc(h["name"])}">Console →</a></div></div>')
    body = (f'<div class="card"><div class="hd">Headless runtimes / profiles</div><div class="bd">'
            f'<div class="mounts">'
            f'<div class="row"><div class="col"><div class="hgrid">{cards}</div></div></div>'
            f'</div></div></div>'
            f'<div class="card"><div class="bd"><div class="empty"><div class="ic">{icon("monitor", 34)}</div>'
            f'<div class="t">No GPU-backed desktops configured</div>'
            f'<p>Hackbot runs headless workers; browser/GPU lanes arrive with the agent-browser profile host.</p></div></div></div>')
    return page("desktops", hero("Desktops", "Agent runtimes, profiles and leases"), body)


def v_registrations():
    rows = ""
    total = 0
    for d in get_session_dirs():
        for f in sorted(os.listdir(d["path"])):
            if "creds" in f.lower():
                p = os.path.join(d["path"], f)
                content = read_file(p)
                email = ""
                m = re.search(r"email=(\S+)", content)
                if m:
                    email = m.group(1)
                rows += (f'<tr class="filter-item" data-filter="filter-item" data-search="{esc(d["name"])} {esc(email)}">'
                         f'<td class="mono">{esc(d["name"])}</td>'
                         f'<td class="mono">{esc(f)}</td>'
                         f'<td class="mono">{esc(email)}</td>'
                         f'<td>{age(p)}</td>'
                         f'<td><a class="btn ghost small" href="/hunts?name={esc(d["name"])}">open →</a></td></tr>')
                total += 1
    mailbox = f"{EMAIL_BASE}+target@{EMAIL_DOMAIN}"
    body = (f'<div class="card"><div class="hd">Registration inbox '
            f'<span class="sp"></span>{pill("connected","CONNECTED")} <span class="btn ghost small">Reconnect</span></div>'
            f'<div class="bd"><p class="muted small">Catch-all mailbox <code class="inline">{esc(mailbox)}</code> '
            f'(OTP / verification codes land here). Credentials archived per session.</p></div></div>'
            f'<div class="card"><div class="hd">Signed-up accounts <span class="sp"></span>'
            f'<span class="hint">{total} credential sets</span></div>'
            f'<table><thead><tr><th>TARGET</th><th>FILE</th><th>EMAIL</th><th>CREATED</th><th></th></tr></thead>'
            f'<tbody>{rows or ""}</tbody></table></div>')
    return page("registrations", hero("Registrations", "Shared platform mailbox for OTP codes and account credentials"), body)


def v_usage():
    queue = get_queue()
    workers = get_workers()
    findings = get_findings()
    sess = get_session_dirs()
    runs = get_run_dirs()
    hunted = sum(1 for t in queue if t.get("bugs_found", 0) > 0 or t.get("status") == "active")
    total = max(len(queue), 1)
    percent = hunted / total

    donut = (f'<div class="donut" style="background:conic-gradient(var(--green) 0% {int(percent*100)}%, var(--grey) {int(percent*100)}% 100%)">'
             f'<div class="core"><div class="big">{int(percent*100)}%</div><div class="sm">hunted</div></div></div>')
    legend = (f'<div class="legend"><div class="lg"><span class="sw" style="background:var(--green)"></span>'
              f'<span class="name">Hunted</span><span class="pct">{hunted}</span></div>'
              f'<div class="lg"><span class="sw" style="background:var(--grey)"></span>'
              f'<span class="name">Pending</span><span class="pct">{total-hunted}</span></div>'
              f'<div class="lg"><span class="sw" style="background:var(--accent)"></span>'
              f'<span class="name">Workers active</span><span class="pct">{len([w for w in workers if w.get("status")=="running"])}</span></div></div>')
    stats = "<div class='stats'>"
    stats += (f'<div class="stat"><div class="lab">HUNTS RUN</div><div class="val">{len(runs)}</div>'
              f'<div class="sub">{len(sess)} sessions</div></div>')
    stats += (f'<div class="stat"><div class="lab">FINDINGS</div><div class="val">{len(findings)}</div>'
              f'<div class="sub">logged to ledger</div></div>')
    stats += (f'<div class="stat"><div class="lab">QUEUE</div><div class="val">{total}</div>'
              f'<div class="sub">{sum(1 for t in queue if t.get("status")=="active")} active</div></div>')
    payload_sum = sum(float(f.get("bounty_est") or 0) for f in findings)
    stats += (f'<div class="stat"><div class="lab">EST BOUNTY</div><div class="val">${payload_sum:,.0f}</div>'
              f'<div class="sub">confirmed pipeline</div></div>')
    stats += "</div>"

    ledger = "".join(
        f'<tr class="filter-item" data-filter="filter-item" data-search="{esc(t.get("handle",""))} {esc(t.get("name",""))}">'
        f'<td><b>{esc(t.get("handle",""))}</b></td>'
        f'<td>{pill(t.get("status","pending"))}</td>'
        f'<td class="num">${float(t.get("max_bounty") or 0):,.0f}</td>'
        f'<td class="num">{t.get("score",0)}</td>'
        f'<td>{fmt_time(t.get("last_hunted"))}</td>'
        f'<td>{esc(t.get("last_verdict") or "—")}</td></tr>' for t in sorted(queue, key=lambda x: -(float(x.get("score") or 0))))
    ledger_table = (f'<div class="card"><div class="hd">Target Ledger <span class="sp"></span>'
                    f'<span class="hint">ranked · {len(queue)}</span></div>'
                    f'<table><thead><tr><th>TARGET</th><th>STATE</th><th class="num">MAX BX</th>'
                    f'<th class="num">SCORE</th><th>LAST HUNT</th><th>VERDICT</th></tr></thead>'
                    f'<tbody>{ledger}</tbody></table></div>')

    share_card = (f'<div class="card"><div class="hd">HUNT SHARE <span class="sp"></span>'
                  f'<span class="hint">trailing since queue init</span></div>'
                  f'<div class="range-pills"><span class="r small">all time</span></div>'
                  f'<div class="donut-wrap">{donut}{legend}</div>'
                  f'<div class="bd small muted" style="border-top:1px solid var(--border)">'
                  f'Model token accounting hooks into the operator-console provider (opencode/DeepSeek). '
                  f'When usage is reported, a per-model ledger renders in this panel.</div></div>')

    body = stats + f'<div class="row"><div class="col">{share_card}</div><div class="col">{ledger_table}</div></div>'
    return page("usage", hero("Usage", "Operator activity — hunts, findings, coverage and bounties"), body)


def v_settings():
    cfg = CONFIG
    tb = ("<div class='tabs'>"
          + '<span class="t active" data-tabbtn="s" data-target="s1" onclick="showTab(\'s\',\'s1\')">Agent providers</span>'
          + '<span class="t" data-tabbtn="s" data-target="s2" onclick="showTab(\'s\',\'s2\')">Channels</span>'
          + '<span class="t" data-tabbtn="s" data-target="s3" onclick="showTab(\'s\',\'s3\')">Credentials</span>'
          + '<span class="t" data-tabbtn="s" data-target="s4" onclick="showTab(\'s\',\'s4\')">Data</span>'
          + '<span class="t" data-tabbtn="s" data-target="s5" onclick="showTab(\'s\',\'s5\')">Progress observer</span>'
          + "<span class='t' data-tabbtn='s' data-target='s6' onclick=\"showTab('s','s6')\">System prompts</span>"
          + "</div>")

    provider_card = (f'<div class="card"><div class="hd">opencode ({esc(PLATFORM)}) <span class="sp"></span>'
                     f'{pill("enabled")} <span class="btn ghost small">Configure</span><span class="btn ghost small">Test</span></div>'
                     f'<div class="bd"><table>'
                     f'<tr><td class="muted">Console CLI</td><td>opencode run --agent hunter</td></tr>'
                     f'<tr><td class="muted">Agent skill</td><td class="mono">@bug-hunting</td></tr>'
                     f'<tr><td class="muted">Models</td><td>provider-managed (opf free tier)</td></tr>'
                     f'<tr><td class="muted">Worker lanes</td><td>{MAX_SLOTS}</td></tr></table></div></div>')
    provider_card2 = (f'<div class="card"><div class="hd">DeepSeek (Anthropic) <span class="sp"></span>'
                      f'{pill("enabled")} <span class="btn ghost small">Configure</span><span class="btn ghost small">Test</span></div>'
                      f'<div class="bd"><p class="small">DeepSeek v4.1 Flash (Anthropic) switchable per-console.</p></div></div>')

    chan = (f'<div class="card"><div class="hd">Telegram <span class="sp"></span>{pill("enabled")} '
            f'<span class="btn ghost small">Configure</span><span class="btn ghost small">Test</span></div>'
            f'<div class="bd"><table>'
            f'<tr><td class="muted">Bot token</td><td class="mono">{redact(TELEGRAM_TOKEN)}</td></tr>'
            f'<tr><td class="muted">Chat id</td><td class="mono">{redact(TELEGRAM_CHAT)}</td></tr>'
            f'<tr><td class="muted">Status</td><td>{pill("connected")} smoke test passed</td></tr></table></div></div>')

    cred = (f'<div class="card"><div class="hd">Credentials <span class="sp"></span><span class="hint">tokens redacted</span></div>'
            f'<div class="bd"><table>'
            f'<tr><td class="muted">Intigriti username</td><td class="mono">{esc(INTIGRITI_USER)}</td></tr>'
            f'<tr><td class="muted">Intigriti API token</td><td class="mono">{redact(os.environ.get("INTIGRITI_API_TOKEN", "unset"))}</td></tr>'
            f'<tr><td class="muted">Email base / domain</td><td class="mono">{esc(EMAIL_BASE)} · {esc(EMAIL_DOMAIN)}</td></tr>'
            f'<tr><td class="muted">Blind XSS endpoint</td><td class="mono">{os.environ.get("BLIND_XSS_URL", "xss.report/…")}</td></tr></table></div></div>')

    data = (f'<div class="card"><div class="hd">Data & mounts</div><div class="bd"><table>'
            f'<tr><td class="muted">Hunts root</td><td class="mono">{esc(HUNTS_ROOT)}</td></tr>'
            f'<tr><td class="muted">Sessions</td><td class="mono">{esc(SESSIONS_CFG)}</td></tr>'
            f'<tr><td class="muted">Payloads</td><td class="mono">{esc(PAYLOADS_DIR)}</td></tr>'
            f'<tr><td class="muted">Findings ledger</td><td class="mono">{esc(FINDINGS_FILE)}</td></tr>'
            f'<tr><td class="muted">Queue</td><td class="mono">{esc(QUEUE_FILE)}</td></tr>'
            f'<tr><td class="muted">Ports</td><td class="mono">{PORT_HTTP} / {PORT_HTTPS}</td></tr></table></div></div>')

    progress = (f'<div class="card"><div class="bd"><div class="empty"><div class="ic">{icon("bar-chart-2", 34)}</div>'
                f'<div class="t">Progress observer not configured</div>'
                f'<p>Used to score and steer running workers per tick.</p></div></div></div>')
    sysprompts = (f'<div class="card"><div class="bd"><div class="empty"><div class="ic">{icon("file-text", 34)}</div>'
                  f'<div class="t">System prompt overrides live with the worker skill</div></div></div></div>')

    panels = (f'<div id="s1" data-tabgroup="s">{provider_card}{provider_card2}</div>'
              f'<div id="s2" data-tabgroup="s" style="display:none">{chan}</div>'
              f'<div id="s3" data-tabgroup="s" style="display:none">{cred}</div>'
              f'<div id="s4" data-tabgroup="s" style="display:none">{data}</div>'
              f'<div id="s5" data-tabgroup="s" style="display:none">{progress}</div>'
              f'<div id="s6" data-tabgroup="s" style="display:none">{sysprompts}</div>')
    body = tb + panels
    return page("settings", hero("Settings", "Agent providers, channels, credentials and operator data"), body)


# ── router ─────────────────────────────────────────────────────────────────────

def route(path, qs):
    parts = path.split("?")[0].rstrip("/").split("/")
    p = [x for x in parts if x]

    if not p or p[0] == "v":
        view = p[1] if len(p) > 1 else "overview"
        q = qs.get("q", [""])[0]
        sel = qs.get("sel", [""])[0]
        target = qs.get("target", [""])[0]
        views = {
            "overview": v_overview,
            "hunts": lambda: v_hunts(q),
            "history": v_history,
            "monitors": v_monitors,
            "topology": v_topology,
            "knowledge": lambda: v_knowledge(q) if q else v_knowledge(""),
            "memory": v_memory,
            "assets": lambda: v_assets(target) if target else v_assets(""),
            "skills": lambda: v_skills(qs.get("view", ["library"])[0], sel),
            "workspaces": v_workspaces,
            "desktops": v_desktops,
            "registrations": v_registrations,
            "usage": v_usage,
            "settings": v_settings,
        }
        fn = views.get(view, v_overview)
        out = fn()
        return out.encode()

    if p[0] == "hunts":
        name = qs.get("name", [""])[0]
        if name:
            safe = os.path.basename(os.path.normpath(name))
            hpath = os.path.join(HUNTS_ROOT, safe)
            if not os.path.isdir(hpath):
                hpath = os.path.join(SESSIONS_ROOT, safe)
            if os.path.isdir(hpath):
                out = v_hunt(safe)
                if out:
                    return out.encode()
        return v_hunts("").encode()

    if p[0] == "report":
        safe = os.path.basename(os.path.normpath(p[1])) if len(p) > 1 else ""
        fname = os.path.basename(os.path.normpath("/".join(p[2:]))) if len(p) > 2 else ""
        rroot = os.path.join(HUNTS_ROOT, safe)
        if not os.path.isdir(rroot):
            rroot = os.path.join(SESSIONS_ROOT, safe)
        rp = os.path.join(rroot, "reports", fname)
        if os.path.isfile(rp):
            body = f'<div class="breadcrumb">Hunt / Reports / <b>{esc(fname)}</b></div>'
            body += (f'<div class="card"><div class="hd">{icon("file-text", 16)} {esc(fname)} <span class="sp"></span>'
f'<a class="btn ghost small" href="/hunts?name={esc(safe)}">{icon("arrow-left", 13)} Hunt</a></div>'
                     f'<div class="bd"><pre class="pread">{esc(read_file(rp))}</pre></div></div>')
            return page("report", hero("Report", f"Staged submission for {esc(fname)}", back=f"/hunts?name={esc(safe)}"), body).encode()
        return b"404 report not found"

    if p[0] == "evidence":
        safe = os.path.basename(os.path.normpath(p[1])) if len(p) > 1 else ""
        ep = os.path.join(SESSIONS_ROOT, safe, "evidence")
        if not os.path.isdir(ep):
            ep = os.path.join(HUNTS_ROOT, safe, "evidence")
        if os.path.isdir(ep):
            rows = ""
            for f in sorted(os.listdir(ep)):
                fp = os.path.join(ep, f)
                rows += f'<tr><td>{icon("archive", 16)}</td><td class="mono">{esc(f)}</td><td class="num">{count_files(fp) if os.path.isdir(fp) else 1}</td><td>{age(fp)}</td></tr>'
            body = (f'<div class="card"><div class="hd">Evidence · {esc(safe)} <span class="sp"></span>'
                    f'<a class="btn ghost small" href="/hunts?name={esc(safe)}">{icon("arrow-left", 13)} Hunt</a></div>'
                    f'<table><thead><tr><th></th><th>PACK</th><th class="num">ITEMS</th><th>UPDATED</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table></div>')
            return page("report", hero("Evidence", f"Replay packs for {esc(safe)}", back=f"/hunts?name={esc(safe)}"), body).encode()
        return b"404 evidence not found"

    if p[0] == "console":
        w = qs.get("w", [""])[0]
        l = qs.get("l", [""])[0]
        d = qs.get("d", [""])[0]
        lines = int((qs.get("lines", ["300"])[0] or "300") or 300)
        return _console_for(l, w, d, lines).encode()

    if p[0] == "api":
        if p[1] == "findings":
            return json.dumps(get_findings(), default=str).encode()
        if p[1] == "queue":
            return json.dumps(get_queue(), default=str).encode()
        if p[1] == "pool":
            return json.dumps(get_pool(), default=str).encode()
        if p[1] == "memory":
            q = qs.get("q", [""])[0]
            return json.dumps(search_memory(q), default=str).encode()
        if p[1] == "skills":
            return json.dumps(skill_dirs(), default=str).encode()
        if p[1] == "console":
            w = qs.get("w", [""])[0]
            l = qs.get("l", [""])[0]
            d = qs.get("d", [""])[0]
            lines = int((qs.get("lines", ["300"])[0] or "300") or 300)
            sel = _resolve_log(l, w, d)
            payload = {
                "mtime": mtime(sel) if sel else 0,
                "html": ansi_to_html("\n".join(read_tail(sel, lines))) if sel else "(no logs yet)",
            }
            return json.dumps(payload).encode()
        return b"{}"

    return b"404"


def _log_index():
    """Return list of (unique_rel_key, abspath) for every console log."""
    logs = []
    pool_logdir = os.path.join(MISC, "worker-pool")
    if os.path.isdir(pool_logdir):
        for f in sorted(os.listdir(pool_logdir)):
            if f.endswith(".log"):
                logs.append((os.path.join("worker-pool", f), os.path.join(pool_logdir, f)))
    if os.path.isdir(SESSIONS_ROOT):
        for d in sorted(os.listdir(SESSIONS_ROOT)):
            p = os.path.join(SESSIONS_ROOT, d, "session.log")
            if os.path.isfile(p):
                logs.append((os.path.join("sessions", d, "session.log"), p))
    return logs


def _resolve_log(lname, wname, desktop):
    logs = _log_index()
    by_key = dict(logs)
    if lname:
        if lname in by_key:
            return by_key[lname]
        hits = [p for k, p in logs if os.path.basename(k) == lname]
        if len(hits) == 1:
            return hits[0]
    if wname:
        p0 = os.path.join(MISC, "worker-pool", wname + ".log")
        if os.path.isfile(p0):
            return p0
    if desktop:
        p0 = os.path.join(SESSIONS_ROOT, desktop, "session.log")
        if os.path.isfile(p0):
            return p0
    logs.sort(key=lambda kv: mtime(kv[1]), reverse=True)
    return logs[0][1] if logs else None


def _console_for(lname, wname, desktop, lines=300):
    return v_console_build(_resolve_log(lname, wname, desktop), lines)


def v_console_build(selected, lines=300):
    logs = _log_index()
    selected = selected or (sorted(logs, key=lambda kv: mtime(kv[1]), reverse=True) or [(None, None)])[0][1]
    key = ""
    for k, l in logs:
        if l == selected:
            key = k
            break
    opts = ""
    for k, l in sorted(logs, key=lambda kv: mtime(kv[1]), reverse=True):
        sel = ' selected' if l == selected else ""
        label = k if k.startswith("sessions/") else os.path.basename(l)
        opts += f'<option value="{esc(k)}"{sel}>{esc(label)}</option>'
    line_opts = ""
    for n in (100, 300, 1000, 5000):
        s = ' selected' if n == lines else ""
        line_opts += f'<option value="{n}"{s}>{n} lines</option>'
    content = ansi_to_html("\n".join(read_tail(selected, lines))) if selected else "(no logs yet)"
    title = os.path.basename(selected) if selected else "operator console"
    body = (f'<div class="card"><div class="console-bar"><div class="title">{icon("terminal", 15)} Operator Console <span class="hint">'
            f'{esc(PLATFORM)} · worker lanes · max effort</span></div>'
            f'<select onchange="location.href=\'/console?l=\'+encodeURIComponent(this.value)">{opts}</select>'
            f'<select onchange="location.href=\'/console?l={esc(key)}&lines=\'+encodeURIComponent(this.value)" title="tail window">{line_opts}</select>'
            f'<span class="sp" style="flex:1"></span>'
            f'<span id="pstatus">{pill("ready", "LIVE")}</span>'
            f'<button class="btn ghost small" id="bpause" onclick="con_pause()">{icon("pause", 13)} Pause</button>'
            f'<button class="btn ghost small" id="bcont" onclick="con_continue()">{icon("play", 13)} Continue</button>'
            f'<a class="btn ghost small" href="/console">latest</a></div>'
            f'<pre class="terminal" id="termlog" style="height:72vh;overflow-y:auto">{content}</pre></div>')
    js = (
        "<script>"
        "(function(){"
        "var pre=document.getElementById('termlog');"
        "var poll=null,lastM=-1,running=true,pinned=document.getElementById('plock')?false:true;"
        "function atBottom(){return pre.scrollHeight-pre.scrollTop-pre.clientHeight<48;}"
        "function pin(){pre.scrollTop=pre.scrollHeight;}"
        "function paint(){"
        "fetch('/api/console?l=" + esc(key) + "&lines=" + str(lines) + "').then(function(r){return r.json();}).then(function(d){"
        "if(d.mtime===lastM)return;lastM=d.mtime;var stay=atBottom();pre.innerHTML=d.html;if(stay)pin();"
        "}).catch(function(){});}"
        "function setState(on){running=on;document.getElementById('bpause').disabled=!on;document.getElementById('bcont').disabled=on;"
        "document.getElementById('pstatus').innerHTML=on?" + json.dumps(pill("ready", "LIVE")) + ":" + json.dumps(pill("amber", "PAUSED")) + ";}"
        "window.con_pause=function(){if(!running)return;if(poll){clearInterval(poll);poll=null;}setState(false);};"
        "window.con_continue=function(){if(running)return;setState(true);paint();poll=setInterval(paint,2000);};"
        "paint();poll=setInterval(paint,2000);"
        "})();"
        "</script>"
    )
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>Console · Hackbot</title>'
            f'<style>{CSS}</style></head><body>'
            f'<div class="topbar" style="background:#0f1216;border-color:#23272d"><div style="color:#e5eaf0;font-weight:800;letter-spacing:.1em">'
            f'CONSOLE</div><span class="sp" style="flex:1"></span>'
            f'<a class="btn ghost small" href="/v/overview">{icon("arrow-left", 13)} Dashboard</a></div>'
            f'<div style="padding:20px 26px 60px">{body}</div>{js}</body></html>')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path, _, qraw = self.path.partition("?")
        from urllib.parse import parse_qs
        qs = parse_qs(qraw)
        try:
            data = route(path, qs)
        except Exception as e:
            data = (f'<!doctype html><html><body style="font-family:monospace;padding:30px"><h2>Dashboard error</h2>'
                    f'<pre>{esc(e.__class__.__name__)}: {esc(e)}</pre></body></html>').encode()
        if path.startswith("/api/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser(description="Hackbot web dashboard")
    ap.add_argument("--port", type=int, default=7878)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"Hackbot dashboard → http://{a.host}:{a.port}/", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()