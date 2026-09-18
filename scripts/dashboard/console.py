"""Hackbot dashboard — console module.

Full-featured operator console with:
- Toggle pause/play (single button)
- Save log to file (download)
- Tell agent (send instruction to worker)
- Agent activity status (thinking/working/writing)
- Smart auto-scroll (preserves position)
- Active console indicator in dropdown
- Collapsible large output sections
- Auto-start Caido proxy
"""
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

from .style import CSS
from .config import MISC
from .config import PLATFORM
from .config import SESSIONS_ROOT
from .ansi import ansi_to_html
from .util import esc
from .icons import icon
from .util import mtime
from .layout import pill
from .util import read_tail
from .helpers import render_log_html
from .state import get_workers

# Activity patterns to detect in logs
ACTIVITY_PATTERNS = [
    (r"(?:Thinking|Analyzing|Planning)\.\.\.", "thinking", "Thinking"),
    (r"(?:Running|Executing|Calling)\s", "working", "Running"),
    (r"(?:Write|Editing|Creating)\s", "writing", "Writing"),
    (r"(?:Reading|Loading|Fetching)\s", "reading", "Reading"),
    (r"(?:Searching|Grep|Finding)\s", "searching", "Searching"),
    (r"(?:HTTP|curl|request)\s", "requesting", "Requesting"),
    (r"(?:Error|Failed|FAIL)", "error", "Error"),
]

CAIDO_STARTED_FILE = "/tmp/hackbot-caido-started"

# Strip emoji from rendered log content (raw log files keep them).
# The dashboard enforces a no-emoji UI policy; agent output may contain emoji.
_EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2764\uFE0F\u200D]")


def _strip_emoji(text):
    return _EMOJI_RE.sub("", text) if text else text


def _jsq(s):
    """Escape a string for safe embedding inside a JS single-quoted literal."""
    return (str(s or "")
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "\\r"))


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


def _detect_activity(log_path):
    """Detect agent activity from last lines of log."""
    if not log_path or not os.path.isfile(log_path):
        return None, None
    try:
        with open(log_path, "r", errors="replace") as fh:
            lines = fh.readlines()[-30:]
        for line in reversed(lines):
            for pattern, kind, label in ACTIVITY_PATTERNS:
                if re.search(pattern, line, re.I):
                    return kind, label
    except Exception:
        pass
    return None, None


def _ensure_caido():
    """Start Caido proxy if not already running."""
    if os.path.exists(CAIDO_STARTED_FILE):
        # Check if still running
        try:
            with open(CAIDO_STARTED_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return  # still running
        except (OSError, ValueError):
            os.remove(CAIDO_STARTED_FILE)

    # Check if caido-cli is available
    caido_path = shutil.which("caido-cli") or shutil.which("caido")
    if not caido_path:
        return

    try:
        proc = subprocess.Popen(
            [caido_path, "--listen", "127.0.0.1:8080"],
            stdout=open("/tmp/caido.log", "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        with open(CAIDO_STARTED_FILE, "w") as f:
            f.write(str(proc.pid))
    except Exception:
        pass


def _worker_id_from_log(key):
    """Extract worker ID from a log key like worker-pool/worker-1-challenge-0426-intigriti-io.log"""
    if not key:
        return ""
    base = os.path.basename(key)
    if base.endswith(".log"):
        base = base[:-4]
    return base


def v_console_build(selected, lines=300):
    _ensure_caido()
    logs = _log_index()
    selected = selected or (sorted(logs, key=lambda kv: mtime(kv[1]), reverse=True) or [(None, None)])[0][1]
    key = ""
    for k, l in logs:
        if l == selected:
            key = k
            break

    # Which worker logs belong to currently-running workers (from pool state)
    running_logs = set()
    for w in get_workers():
        if w.get("status") == "running":
            lp = w.get("log", "")
            if lp:
                running_logs.add(os.path.basename(lp))

    # Build log options with active indicator
    opts = ""
    now = time.time()
    for k, l in sorted(logs, key=lambda kv: mtime(kv[1]), reverse=True):
        sel = ' selected' if l == selected else ""
        label = k if k.startswith("sessions/") else os.path.basename(l)
        # Show active indicator if log was written in last 30 seconds
        is_active = (now - mtime(l)) < 30 if os.path.isfile(l) else False
        active_dot = f' {icon("circle", 8)}' if is_active else ""
        opts += f'<option value="{esc(k)}"{sel}>{esc(label)}{active_dot}</option>'

    # Custom dropdown: dog icon for watchdog logs, RUNNING badge for live workers
    dd_items = ""
    for k, l in sorted(logs, key=lambda kv: mtime(kv[1]), reverse=True):
        base = os.path.basename(l)
        label = k if k.startswith("sessions/") else base
        is_running = base in running_logs
        is_watchdog = base.startswith("watchdog")
        is_active = (now - mtime(l)) < 30 if os.path.isfile(l) else False
        sel_cls = ' sel' if l == selected else ""
        run_cls = ' running' if is_running else ""
        wd_cls = ' watchdog' if is_watchdog else ""
        ic = icon("dog", 13) if is_watchdog else icon("terminal", 13)
        badge = f'<span class="dd-badge">{icon("radio", 9)} RUNNING</span>' if is_running else ""
        dot = f'<span class="dd-dot"></span>' if is_active else ""
        dd_items += (f'<a class="dd-item{sel_cls}{run_cls}{wd_cls}" href="/console?l={esc(k)}">'
                     f'<span class="dd-ic">{ic}</span>'
                     f'<span class="dd-label">{esc(label)}</span>'
                     f'{dot}{badge}</a>')

    # Current selection for the dropdown button
    cur_base = os.path.basename(selected) if selected else ""
    cur_running = cur_base in running_logs
    cur_watchdog = cur_base.startswith("watchdog")
    cur_ic = icon("dog", 13) if cur_watchdog else icon("terminal", 13)
    cur_badge = f'<span class="dd-badge">{icon("radio", 9)} RUNNING</span>' if cur_running else ""
    dd = (f'<div class="dd" id="logdd">'
          f'<button class="dd-btn" onclick="ddToggle(event)">'
          f'<span class="dd-ic">{cur_ic}</span>'
          f'<span class="dd-label">{esc(cur_base or "select log")}</span>'
          f'{cur_badge}'
          f'<span class="dd-caret">{icon("chevron-down", 12)}</span>'
          f'</button>'
          f'<div class="dd-menu">{dd_items}</div>'
          f'</div>')

    line_opts = ""
    for n in (100, 300, 1000, 5000):
        s = ' selected' if n == lines else ""
        line_opts += f'<option value="{n}"{s}>{n} lines</option>'

    content = _strip_emoji(render_log_html("\n".join(read_tail(selected, lines)))) if selected else "(no logs yet)"
    title = os.path.basename(selected) if selected else "operator console"

    # Detect current activity
    activity_kind, activity_label = _detect_activity(selected)
    activity_html = ""
    if activity_kind:
        color_map = {
            "thinking": "var(--accent)",
            "working": "#22c55e",
            "writing": "#f59e0b",
            "reading": "#8b5cf6",
            "searching": "#06b6d4",
            "requesting": "#f97316",
            "error": "#ef4444",
        }
        color = color_map.get(activity_kind, "var(--muted)")
        activity_html = (f'<span class="activity-indicator" style="color:{color};margin-right:8px">'
                         f'{icon("radio", 10)} {esc(activity_label)}</span>')

    # Worker ID for tell-agent
    worker_id = _worker_id_from_log(key)

    body = (f'<pre class="terminal" id="termlog">{content}</pre>'
            # Tell agent input
            f'<div class="console-bar input-bar">'
            f'{icon("message-square", 13)} '
            f'<input type="text" id="agent-msg" placeholder="Tell the agent something..." '
            f'style="flex:1;background:var(--bg);border:1px solid var(--border);color:var(--fg);'
            f'padding:6px 10px;border-radius:6px;font-size:13px;font-family:inherit" '
            f'onkeydown="if(event.key===\'Enter\')sendMsg()">'
            f'<button class="btn ghost small" onclick="sendMsg()">{icon("send", 13)} Send</button>'
            f'<span id="msg-status" style="margin-left:8px;font-size:12px;color:var(--muted)"></span>'
            f'</div>')

    js = (
        "<script>"
        "(function(){"
        # --- State ---
        "var pre=document.getElementById('termlog');"
        "pre.scrollTop=pre.scrollHeight;"  # open at the latest output
        "var poll=null,lastM=-1,running=true,first=true;"
        "var openCmds={};"  # data-cmd hash -> open state, survives polls
        # --- Log dropdown toggle ---
        "window.ddToggle=function(e){e.stopPropagation();var m=document.getElementById('logdd');if(m)m.classList.toggle('open');};"
        "document.addEventListener('click',function(){var m=document.getElementById('logdd');if(m)m.classList.remove('open');});"
        # --- Smart auto-scroll ---
        "function atBottom(){return pre.scrollHeight-pre.scrollTop-pre.clientHeight<48;}"
        "function pin(){pre.scrollTop=pre.scrollHeight;}"
        "var wasAtBottom=true;"  # track state across paints
        # --- Track collapse state on user toggle ---
        "pre.addEventListener('toggle',function(e){var d=e.target;if(d&&d.tagName==='DETAILS'&&d.classList.contains('clp-cmd')){if(d.open){openCmds[d.getAttribute('data-cmd')]=1;}else{delete openCmds[d.getAttribute('data-cmd')];}}},true);"
        # --- Expand/collapse output on click (drag guard keeps text selection) ---
        "var downX=0,downY=0;"
        "pre.addEventListener('mousedown',function(e){downX=e.clientX;downY=e.clientY;});"
        "pre.addEventListener('click',function(e){"
        "var t=e.target;"
        "if(Math.abs(e.clientX-downX)>5||Math.abs(e.clientY-downY)>5)return;"
        "var d=t.closest?t.closest('details.clp-cmd'):null;"
        "if(!d)return;"
        "if(t.classList&&(t.classList.contains('clp-more')||t.classList.contains('clp-out'))){"
        "d.classList.toggle('expanded');"
        "}"
        "});"
        # --- Paint (poll) ---
        "function paint(){"
        "fetch('/api/console?l=" + esc(key) + "&lines=" + str(lines) + "').then(function(r){return r.json();}).then(function(d){"
        "if(d.mtime===lastM)return;lastM=d.mtime;"
        "if(first){wasAtBottom=true;first=false;}else{wasAtBottom=atBottom();}"
        # Preserve scroll position across innerHTML replacement
        "var oldScrollTop=pre.scrollTop;var oldScrollHeight=pre.scrollHeight;"
        # Save which command blocks are open / expanded, then re-apply after replace
        "var saved={};var savedExp={};"
        "pre.querySelectorAll('details.clp-cmd').forEach(function(d){"
        "if(d.open)saved[d.getAttribute('data-cmd')]=1;"
        "if(d.classList.contains('expanded'))savedExp[d.getAttribute('data-cmd')]=1;"
        "});"
        "pre.innerHTML=d.html;"
        "pre.querySelectorAll('details.clp-cmd').forEach(function(d){"
        "var c=d.getAttribute('data-cmd');"
        "if(saved[c])d.open=true;"
        "if(savedExp[c])d.classList.add('expanded');"
        "});"
        # Restore or pin
        "if(wasAtBottom){pre.scrollTop=pre.scrollHeight;}"
        "else{var ratio=oldScrollTop/oldScrollHeight;pre.scrollTop=ratio*pre.scrollHeight;}"
        # Update activity indicator
        "if(d.activity){var ai=document.querySelector('.activity-indicator');if(ai){ai.innerHTML=d.activity_html;ai.style.color=d.activity_color;}}"
        "}).catch(function(){});}"
        # --- Toggle ---
        "window.con_toggle=function(){"
        "var b=document.getElementById('btoggle');"
        "if(running){if(poll){clearInterval(poll);poll=null;}running=false;"
        "b.innerHTML='" + json.dumps(icon("play", 13)) + "';b.title='Resume live updates';"
        "document.getElementById('pstatus').innerHTML=" + json.dumps(pill("amber", "PAUSED")) + ";"
        "}else{running=true;paint();poll=setInterval(paint,2000);"
        "b.innerHTML='" + json.dumps(icon("pause", 13)) + "';b.title='Pause live updates';"
        "document.getElementById('pstatus').innerHTML=" + json.dumps(pill("ready", "LIVE")) + ";}"
        "};"
        # --- Tell agent ---
        "window.sendMsg=function(){"
        "var inp=document.getElementById('agent-msg');var msg=inp.value.trim();if(!msg)return;"
        "var st=document.getElementById('msg-status');st.textContent='Sending...';st.style.color='var(--muted)';"
        "fetch('/api/console/tell',{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({worker_id:'" + _jsq(worker_id) + "',message:msg})})"
        ".then(function(r){return r.json();}).then(function(d){"
        "if(d.ok){st.textContent='Sent';st.style.color='#22c55e';inp.value='';setTimeout(function(){st.textContent='';},3000);}"
        "else{st.textContent=d.message||'Failed';st.style.color='#ef4444';}"
        "}).catch(function(){st.textContent='Network error';st.style.color='#ef4444';});"
        "};"
        # --- Start ---
        "paint();poll=setInterval(paint,2000);"
        "})();"
        "</script>"
    )

    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">'
            f'<title>Console · Hackbot</title>'
            f'<style>{CSS}</style></head>'
            f'<body class="console-page">'
            f'<header class="con-hdr">'
            f'<div class="con-brand" title="Operator Console">{icon("terminal", 14)}<span>CONSOLE</span></div>'
            f'{dd}'
            f'<span style="flex:1"></span>'
            f'<div class="con-ctl">'
            f'<select onchange="location.href=\'/console?l={esc(key)}&lines=\'+encodeURIComponent(this.value)" title="Tail window">{line_opts}</select>'
            f'{activity_html}'
            f'<span id="pstatus">{pill("ready", "LIVE")}</span>'
            f'<button class="btn ghost small" id="btoggle" onclick="con_toggle()" title="Pause live updates">{icon("pause", 13)}</button>'
            f'<a class="btn ghost small" href="/api/console/save?l={esc(key)}" title="Save full log to file">{icon("download", 13)}</a>'
            f'<a class="btn ghost small" href="/v/overview" title="Back to dashboard">{icon("arrow-left", 13)}</a>'
            f'</div>'
            f'</header>'
            f'<div class="console-body">{body}</div>{js}</body></html>')
