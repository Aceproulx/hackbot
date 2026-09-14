"""Hackbot dashboard — console module.

Split from the original single-file scripts/dashboard-web.py.
Function bodies are extracted verbatim.
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
# UNRESOLVED: _log_index (same-module or missing)
# UNRESOLVED: _resolve_log (same-module or missing)
from .ansi import ansi_to_html
from .util import esc
from .icons import icon
# UNRESOLVED: json (same-module or missing)
# UNRESOLVED: kv (same-module or missing)
from .util import mtime
# UNRESOLVED: os (same-module or missing)
from .layout import pill
from .util import read_tail
# UNRESOLVED: v_console_build (same-module or missing)

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
