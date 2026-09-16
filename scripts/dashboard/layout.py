"""Hackbot dashboard — layout module.

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
from .config import MAX_SLOTS
from .config import PLATFORM
from .util import esc
from .state import get_findings
from .state import get_queue
from .state import get_workers
from .state import hunt_stats
from .state import unread_reports
from .icons import icon
# UNRESOLVED: need_attention (same-module or missing)
# UNRESOLVED: pill (same-module or missing)
# UNRESOLVED: sidebar (same-module or missing)
# UNRESOLVED: topbar (same-module or missing)

NAV = [
    ("WORKSPACE", [
        ("overview", "Overview", "dashboard"),
        ("hunts", "Hunts", "target"),
        ("findings", "Findings", "file-text"),
        ("history", "History", "clock"),
        ("monitors", "Monitors", "activity"),
        ("watchdog", "Watchdog", "radio"),
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

def self_hosted_badge(t):
    return f' <span class="pill blue"><span class="dot"></span>SELF-HOSTED</span>' if t.get("self_hosted") else ""

def hunt_action_btn(t):
    h = esc(t.get("handle", ""))
    # Trust actual worker state, not the queue's status field (which can go
    # stale when a pool is stopped/crashes without resetting the queue).
    running = any(
        w.get("handle") == t.get("handle") and w.get("status") == "running"
        for w in get_workers()
    )
    if running:
        return f'<button class="btn ghost small" onclick="hunterAction(\'stop\',\'{h}\',this)">{icon("pause", 12)} Stop</button>'
    return f'<button class="btn small" onclick="hunterAction(\'start\',\'{h}\',this)">{icon("play", 12)} Start Hunt</button>'

def need_attention():
    n = 0
    for f in get_findings():
        st = f.get("status", "").lower()
        if st not in ("paid", "dismissed", "informational", "closed", "n/a"):
            n += 1
    return n

def sidebar(active):
    hs = hunt_stats()
    queue = get_queue()
    badges = {"findings": unread_reports(), "assets": len(queue)}
    rows = []
    for sec, items in NAV:
        rows.append(f'<div class="sec">{esc(sec)}</div>')
        for key, label, ic in items:
            cls = " active" if key == active else ""
            badge = f'<span class="badge">{badges.get(key, 0)}</span>' if badges.get(key) else ""
            rows.append(
                f'<a class="{cls.strip()}" href="/v/{key}">'
                f'<span class="ic">{icon(ic)}</span><span>{esc(label)}</span>{badge}</a>')
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
  <button class="btn ghost" onclick="document.getElementById('fmodal').style.display='flex'">{icon('clipboard-list', 15)} Log finding</button>
  <button class="btn ghost" id="orch-btn" onclick="startOrchestrator()" title="Start the orchestrator chain (watchdog daemon + refill-watcher)">{icon('play', 14)} Start orchestrator</button>
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
        '<div class="layout" id="layout">\n'
        '  <aside class="sidebar">\n'
        '    <div class="logo"><div class="mark">' + icon('compass', 18) + '</div>\n'
        '      <div><div class="brand">HACKBOT</div><div class="sub">' + esc(PLATFORM) + ' operator</div></div></div>\n'
        '    <nav class="nav">' + sidebar(active) + '</nav>\n'
        '    <button class="collapse-btn" id="side-collapse" title="Collapse sidebar">'
        '<span class="ci ci-open">' + icon('chevron-left', 14) + '</span>'
        '<span class="ci ci-close">' + icon('chevron-right', 14) + '</span></button>\n'
        '  </aside>\n'
        '  <div class="console-tab" onclick="location.href=\'/console\'">CONSOLE</div>\n'
        '  <main class="main">\n'
        + topbar() + '\n'
        + hero_html + '\n'
        + '    <div class="content">' + body + '</div>\n'
        '  </main>\n</div>\n'
        '<div class="modal-bg" id="taskmodal" onclick="if(event.target===this)this.style.display=\'none\'">\n'
        '  <div class="modal"><div class="hd">New Task</div><div class="bd">\n'
        '    <div style="margin-bottom:16px">\n'
        '      <div class="hd" style="border:none;padding:0 0 6px;font-size:12.5px">Add a self-hosted target</div>\n'
        '      <p class="small muted" style="margin-bottom:10px">Not a bug bounty platform program — your own infra, a staging box, anything self-hosted. Full browser scope, no bounty ceiling, no platform out-of-scope list to respect. Adding it here is you vouching that you are authorized to test it.</p>\n'
        '      <div id="at-err" class="small" style="color:var(--accent);display:none;margin-bottom:8px"></div>\n'
        '      <input id="at-url" placeholder="https://staging.example.internal" style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:13px;margin-bottom:8px;font-family:inherit">\n'
        '      <input id="at-name" placeholder="Display name (optional)" style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:13px;margin-bottom:8px;font-family:inherit">\n'
        '      <textarea id="at-notes" placeholder="Notes for the hunter (optional)" style="width:100%;min-height:52px;padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:13px;margin-bottom:8px;font-family:inherit"></textarea>\n'
        '      <button class="btn small" id="at-submit" onclick="addSelfHostedTarget()">' + icon('plus', 13) + ' Add target</button>\n'
        '    </div>\n'
        '    <p class="small muted" style="margin-bottom:10px;border-top:1px solid #eee8dd;padding-top:12px">Everything else is orchestrated from the operator terminal:</p>\n'
        '    <ul class="cmdhelp">\n'
        '      <li><span class="cc">hackbot-workers start --slots ' + str(MAX_SLOTS) + '</span> <span class="muted">Launch worker pool</span></li>\n'
        '      <li><span class="cc">hackbot-workers stop &lt;slot&gt;</span> <span class="muted">Stop a worker</span></li>\n'
        '      <li><span class="cc">hackbot-queue next</span> <span class="muted">Pick next ranked target</span></li>\n'
        '      <li><span class="cc">hackbot-dashboard serve</span> <span class="muted">This dashboard</span></li>\n'
        '      <li><span class="cc">hackbot-dashboard add &lt;program&gt; &lt;severity&gt; &lt;title&gt;</span> <span class="muted">Log a finding</span></li>\n'
        '    </ul>\n'
        '  </div></div>\n</div>\n'
        '<div class="modal-bg" id="fmodal" onclick="if(event.target===this)this.style.display=\'none\'">\n'
        '  <div class="modal"><div class="hd">Log finding</div><div class="bd">\n'
        '    <div id="f-err" class="small" style="color:var(--accent);display:none;margin-bottom:8px"></div>\n'
        '    <div class="row">\n'
        '      <div class="col">\n'
        '        <div class="lbl">Program</div><input id="f-program" class="fld" placeholder="e.g. ably.com">\n'
        '        <div class="lbl">Severity</div>\n'
        '        <select id="f-severity" class="fld"><option>Critical</option><option>High</option><option>Medium</option><option>Low</option><option>Informational</option></select>\n'
        '        <div class="lbl">Status</div>\n'
        '        <select id="f-status" class="fld"><option value="confirmed">Confirmed</option><option value="in-progress">In progress</option><option value="reported">Reported</option><option value="paid">Paid</option><option value="dismissed">Dismissed</option><option value="informational">Informational</option></select>\n'
        '      </div>\n'
        '      <div class="col">\n'
        '        <div class="lbl">Title</div><input id="f-title" class="fld" placeholder="e.g. Reflected XSS in search">\n'
        '        <div class="lbl">URL</div><input id="f-url" class="fld" placeholder="https://…">\n'
        '        <div class="lbl">Evidence</div><textarea id="f-evidence" class="fld" style="min-height:48px" placeholder="repro / diff / request"></textarea>\n'
        '        <div class="lbl">Notes</div><textarea id="f-notes" class="fld" style="min-height:48px" placeholder="optional"></textarea>\n'
        '      </div>\n'
        '    </div>\n'
        '    <div style="text-align:right;margin-top:12px">\n'
        '      <button class="btn ghost small" onclick="document.getElementById(\'fmodal\').style.display=\'none\'">Cancel</button>\n'
        '      <button class="btn small" style="margin-left:8px" id="fs-submit" onclick="logFinding()">Log finding</button>\n'
        '    </div>\n'
        '  </div></div>\n</div>\n'
        '<div class="modal-bg" id="msgmodal" onclick="if(event.target===this)closeMsg()">\n'
        '  <div class="modal" style="width:440px;max-width:90vw">\n'
        '    <div class="hd"><span id="msg-title">Notice</span><span style="flex:1"></span><button class="btn ghost small" onclick="closeMsg()">✕</button></div>\n'
        '    <div class="bd">\n'
        '      <p id="msg-text" class="pread" style="margin:4px 0 16px"></p>\n'
        '      <div style="text-align:right"><button class="btn small" id="msg-ok" onclick="closeMsg()">OK</button></div>\n'
        '    </div>\n'
        '  </div>\n</div>\n'
        '<div class="modal-bg" id="confmodal" onclick="if(event.target===this)closeConfirm()">\n'
        '  <div class="modal" style="width:400px;max-width:90vw">\n'
        '    <div class="hd"><span id="conf-title">Confirm</span><span style="flex:1"></span><button class="btn ghost small" onclick="closeConfirm()">✕</button></div>\n'
        '    <div class="bd">\n'
        '      <p id="conf-text" class="pread" style="margin:4px 0 16px"></p>\n'
        '      <div style="text-align:right"><button class="btn ghost small" onclick="closeConfirm()">Cancel</button>'
        '<button class="btn small" style="margin-left:8px" id="conf-ok" onclick="runConfirm()">OK</button></div>\n'
        '    </div>\n'
        '  </div>\n</div>\n'
        '<script>\n'
        'function openM(id){var m=document.getElementById(id);if(m){m.style.display=\'flex\';}}\n'
        'function closeM(id){var m=document.getElementById(id);if(m){m.style.display=\'none\';}}\n'
        'function closeMsg(){\n'
        '  var m=document.getElementById(\'msgmodal\');if(m){m.style.display=\'none\';}\n'
        '}\n'
        'function showMsg(msg,title){\n'
        '  var m=document.getElementById(\'msgmodal\');if(!m)return;\n'
        '  document.getElementById(\'msg-text\').textContent=msg||\'\';\n'
        '  var t=document.getElementById(\'msg-title\');if(t){t.textContent=title||\'Notice\';}\n'
        '  m.style.display=\'flex\';\n'
        '  var ok=document.getElementById(\'msg-ok\');if(ok){ok.focus();}\n'
        '}\n'
        'var __confirmCb=null;\n'
        'function openConfirm(msg,title,cb){\n'
        '  var m=document.getElementById(\'confmodal\');if(!m)return;\n'
        '  document.getElementById(\'conf-text\').textContent=msg||\'\';\n'
        '  var t=document.getElementById(\'conf-title\');if(t){t.textContent=title||\'Confirm\';}\n'
        '  __confirmCb=typeof cb===\'function\'?cb:null;\n'
        '  m.style.display=\'flex\';\n'
        '  var ok=document.getElementById(\'conf-ok\');if(ok){ok.focus();}\n'
        '}\n'
        'function closeConfirm(){var m=document.getElementById(\'confmodal\');if(m){m.style.display=\'none\';}__confirmCb=null;}\n'
        'function runConfirm(){var cb=__confirmCb;closeConfirm();if(cb){cb();}}\n'
        'function apiPost(url,obj){return fetch(url,{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify(obj||{})}).then(function(r){return r.json().catch(function(){return {ok:false,message:\'bad response\'};});});}\n'
        'async function logFinding(){\n'
        '  var err=document.getElementById(\'f-err\');err.style.display=\'none\';\n'
        '  var payload={program:document.getElementById(\'f-program\').value.trim(),\n'
        '    title:document.getElementById(\'f-title\').value.trim(),\n'
        '    severity:document.getElementById(\'f-severity\').value,\n'
        '    status:document.getElementById(\'f-status\').value,\n'
        '    url:document.getElementById(\'f-url\').value.trim(),\n'
        '    evidence:document.getElementById(\'f-evidence\').value.trim(),\n'
        '    notes:document.getElementById(\'f-notes\').value.trim()};\n'
        '  if(!payload.program||!payload.title){err.textContent=\'Program and title are required.\';err.style.display=\'\';return;}\n'
        '  var btn=document.getElementById(\'fs-submit\');btn.disabled=true;var orig=btn.textContent;btn.textContent=\'Logging…\';\n'
        '  try{\n'
        '    var res=await fetch(\'/api/findings/add\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify(payload)});\n'
        '    var data=await res.json();\n'
        '    if(!res.ok||!data.ok){err.textContent=data.message||\'Failed to log finding.\';err.style.display=\'\';btn.disabled=false;btn.textContent=orig;return;}\n'
        '    location.reload();\n'
        '  }catch(e){err.textContent=\'Request failed: \'+e;err.style.display=\'\';btn.disabled=false;btn.textContent=orig;}\n'
        '}\n'
        'function bulkCount(){var n=document.querySelectorAll(\'.qsel:checked\').length;var e=document.getElementById(\'qsel-n\');if(e){e.textContent=n;}}\n'
        'function bulkQueue(action){\n'
        '  if(action===\'clear\'){document.querySelectorAll(\'.qsel\').forEach(function(c){c.checked=false;});bulkCount();return;}\n'
        '  var hs=[];document.querySelectorAll(\'.qsel:checked\').forEach(function(c){hs.push(c.getAttribute(\'data-h\'));});\n'
        '  if(!hs.length){showMsg(\'Select at least one program.\');return;}\n'
        '  apiPost(\'/api/queue/bulk\',{action:action,handles:hs}).then(function(data){\n'
        '    if(!data.ok){showMsg(data.message||\'Bulk operation failed.\');return;}\n'
        '    location.reload();\n'
        '  });\n'
        '}\n'
        'async function usageRange(range,btn){\n'
        '  document.querySelectorAll(\'.range-pills .r\').forEach(function(p){p.classList.remove(\'active\');});\n'
        '  if(btn){btn.classList.add(\'active\');}\n'
        '  try{\n'
        '    var res=await fetch(\'/api/usage?range=\'+encodeURIComponent(range));\n'
        '    var d=await res.json();\n'
        '    if(!d.ok){showMsg(d.message||\'Failed to load usage\');return;}\n'
        '    document.getElementById(\'u-hunts\').textContent=d.hunts_run;\n'
        '    document.getElementById(\'u-findings\').textContent=d.findings;\n'
        '    document.getElementById(\'u-queue\').textContent=d.queue_total;\n'
        '    document.getElementById(\'u-pct\').textContent=d.percent+\'%\';\n'
        '    document.getElementById(\'u-hunted\').textContent=d.hunted;\n'
        '    document.getElementById(\'u-pending\').textContent=d.pending;\n'
        '    document.getElementById(\'u-donut\').style.background=\'conic-gradient(var(--green) 0% \'+d.percent+\'%, var(--grey) \'+d.percent+\'% 100%)\';\n'
        '  }catch(e){showMsg(\'Request failed: \'+e);}\n'
        '}\n'
        'function newSkill(){openM(\'smodal\');}\n'
        'async function newSkillSubmit(){\n'
        '  var err=document.getElementById(\'s-err\');err.style.display=\'none\';\n'
        '  var name=document.getElementById(\'s-name\').value.trim();\n'
        '  var folder=document.getElementById(\'s-folder\').value.trim()||\'\';\n'
        '  if(!name){err.textContent=\'Skill name is required.\';err.style.display=\'\';return;}\n'
        '  var btn=event.target;btn.disabled=true;var orig=btn.textContent;btn.textContent=\'Creating…\';\n'
        '  try{var data=await apiPost(\'/api/skills/new\',{name:name,folder:folder});\n'
        '    if(!data.ok){err.textContent=data.message||\'Failed to create skill.\';err.style.display=\'\';btn.disabled=false;btn.textContent=orig;return;}\n'
        '    location.href=\'/v/skills?view=library&sel=\'+encodeURIComponent(data.skill||name);\n'
        '  }catch(e){err.textContent=\'Request failed: \'+e;err.style.display=\'\';btn.disabled=false;btn.textContent=orig;}\n'
        '}\n'
        'function importSkill(){openM(\'smodal\');}\n'
        'async function importSkillSubmit(){\n'
        '  var err=document.getElementById(\'s-err\');err.style.display=\'none\';\n'
        '  var url=document.getElementById(\'s-url\').value.trim();\n'
        '  if(!url){err.textContent=\'Repository URL or path is required.\';err.style.display=\'\';return;}\n'
        '  var btn=event.target;btn.disabled=true;var orig=btn.textContent;btn.textContent=\'Importing…\';\n'
        '  try{var data=await apiPost(\'/api/skills/import\',{url:url});\n'
        '    if(!data.ok){err.textContent=data.message||\'Failed to import skill.\';err.style.display=\'\';btn.disabled=false;btn.textContent=orig;return;}\n'
        '    location.href=\'/v/skills?view=library\';\n'
        '  }catch(e){err.textContent=\'Request failed: \'+e;err.style.display=\'\';btn.disabled=false;btn.textContent=orig;}\n'
        '}\n'
        'function configOpen(which){openM(\'cmodal\');document.getElementById(\'c-which\').value=which;document.getElementById(\'c-err\').style.display=\'none\';}\n'
        'async function configSave(){\n'
        '  var err=document.getElementById(\'c-err\');err.style.display=\'none\';\n'
        '  var section=document.getElementById(\'c-which\').value.trim();\n'
        '  var setting=document.getElementById(\'c-key\').value.trim();\n'
        '  var value=document.getElementById(\'c-val\').value.trim();\n'
        '  if(!setting){err.textContent=\'Setting key is required.\';err.style.display=\'\';return;}\n'
        '  var btn=event.target;btn.disabled=true;var orig=btn.textContent;btn.textContent=\'Saving…\';\n'
        '  try{var data=await apiPost(\'/api/config/update\',{section:section,setting:setting,value:value});\n'
        '    if(!data.ok){err.textContent=data.message||\'Failed to update config.\';err.style.display=\'\';btn.disabled=false;btn.textContent=orig;return;}\n'
        '    location.reload();\n'
        '  }catch(e){err.textContent=\'Request failed: \'+e;err.style.display=\'\';btn.disabled=false;btn.textContent=orig;}\n'
        '}\n'
        'async function testProvider(name,btn){\n'
        '  var orig=btn.textContent;btn.disabled=true;btn.textContent=\'Testing…\';\n'
        '  try{var data=await apiPost(\'/api/provider/test\',{name:name});\n'
        '    if(!data.ok){showMsg(data.message||\'Provider test failed.\',\'Provider test\');}else{showMsg(data.message||\'Provider OK\',\'Provider test\');}\n'
        '  }catch(e){showMsg(\'Request failed: \'+e,\'Provider test\');}\n'
        '  btn.disabled=false;btn.textContent=orig;\n'
        '}\n'
        'async function testTelegram(btn){\n'
        '  var orig=btn.textContent;btn.disabled=true;btn.textContent=\'Testing…\';\n'
        '  try{var data=await apiPost(\'/api/telegram/test\',{});\n'
        '    if(!data.ok){showMsg(data.message||\'Telegram test failed.\',\'Telegram test\');}else{showMsg(data.message||\'Telegram OK\',\'Telegram test\');}\n'
        '  }catch(e){showMsg(\'Request failed: \'+e,\'Telegram test\');}\n'
        '  btn.disabled=false;btn.textContent=orig;\n'
        '}\n'
        'async function mailboxReconnect(btn){\n'
        '  openConfirm(\'Reconnect the registration mailbox?\',\'Mailbox\',function(){doMailboxReconnect(btn);});\n'
        '}\n'
        'async function doMailboxReconnect(btn){\n'
        '  var orig=btn.textContent;btn.disabled=true;btn.textContent=\'Reconnecting…\';\n'
        '  try{var data=await apiPost(\'/api/mailbox/test\',{action:\'reconnect\'});\n'
        '    if(!data.ok){showMsg(data.message||\'Reconnect failed.\',\'Mailbox\');}else{showMsg(data.message||\'Mailbox reconfigured\',\'Mailbox\');}\n'
        '  }catch(e){showMsg(\'Request failed: \'+e,\'Mailbox\');}\n'
        '  btn.disabled=false;btn.textContent=orig;\n'
        '}\n'
        'function filterViews(){var q=(document.getElementById(\'globalsearch\')||{}).value||"";q=q.toLowerCase();\n'
        'document.querySelectorAll(\'[data-filter]\').forEach(function(el){if(el===sb)return;var hay=((el.getAttribute(\'data-search\')||"")+" "+(el.textContent||"")).toLowerCase();el.style.display=hay.indexOf(q)===-1?"none":"";});}\n'
        'var sb=document.getElementById(\'globalsearch\');\n'
        'if(sb)sb.addEventListener(\'input\',filterViews);\n'
        'function showTab(group,id){document.querySelectorAll(\'[data-tabgroup="\'+group+\'"]\').forEach(function(t){t.style.display=(t.id===id)?"":"none";});document.querySelectorAll(\'[data-tabbtn="\'+group+\'"]\').forEach(function(b){b.classList.toggle(\'active\',b.getAttribute(\'data-target\')===id);});}\n'
        'async function addSelfHostedTarget(){\n'
        '  var url=document.getElementById(\'at-url\').value.trim();\n'
        '  var name=document.getElementById(\'at-name\').value.trim();\n'
        '  var notes=document.getElementById(\'at-notes\').value.trim();\n'
        '  var err=document.getElementById(\'at-err\'); var btn=document.getElementById(\'at-submit\');\n'
        '  err.style.display=\'none\';\n'
        '  if(!url){err.textContent=\'URL is required.\';err.style.display=\'\';return;}\n'
        '  btn.disabled=true; var orig=btn.textContent; btn.textContent=\'Adding…\';\n'
        '  try{\n'
        '    var res=await fetch(\'/api/targets/add\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({url:url,name:name,notes:notes})});\n'
        '    var data=await res.json();\n'
        '    if(!res.ok||!data.ok){err.textContent=data.message||\'Failed to add target.\';err.style.display=\'\';btn.disabled=false;btn.textContent=orig;return;}\n'
        '    location.href=\'/v/assets\';\n'
        '  }catch(e){err.textContent=\'Request failed: \'+e;err.style.display=\'\';btn.disabled=false;btn.textContent=orig;}\n'
        '}\n'
        'async function hunterAction(action,handle,btn){\n'
        '  openConfirm((action===\'start\'?\'Start a hunt on \':\'Stop the hunt on \')+handle+\'?\',\'Confirm\',function(){doHunterAction(action,handle,btn);\n'
        '});\n'
        '}\n'
        'async function doHunterAction(action,handle,btn){\n'
        '  var orig=btn?btn.textContent:\'\'; if(btn){btn.disabled=true;btn.textContent=action===\'start\'?\'Starting…\':\'Stopping…\';}\n'
        '  try{\n'
        '    var res=await fetch(\'/api/targets/\'+action,{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({handle:handle})});\n'
        '    var data=await res.json();\n'
        '    if(!res.ok||!data.ok){showMsg(data.message||(\'Failed to \'+action+\' hunt.\'));if(btn){btn.disabled=false;btn.textContent=orig;}return;}\n'
        '    location.reload();\n'
        '  }catch(e){showMsg(\'Request failed: \'+e);if(btn){btn.disabled=false;btn.textContent=orig;}}\n'
        '}\n'
        'function setOrchBtn(running){\n'
        '  var b=document.getElementById(\'orch-btn\'); if(!b)return;\n'
        '  if(running){\n'
        '    b.className=\'btn ghost danger\';\n'
        '    b.title=\'Stop the orchestrator chain (watchdog, refill-watcher, worker pool)\';\n'
        '    b.innerHTML=\'<svg class="ic-svg " width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="1"/></svg> Stop orchestrator\';\n'
        '    b.onclick=function(){stopOrchestrator();};\n'
        '  }else{\n'
        '    b.className=\'btn ghost\';\n'
        '    b.title=\'Start the orchestrator chain (watchdog daemon + refill-watcher)\';\n'
        '    b.innerHTML=\'<svg class="ic-svg " width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg> Start orchestrator\';\n'
        '    b.onclick=function(){startOrchestrator();};\n'
        '  }\n'
        '}\n'
        'function refreshOrchStatus(){\n'
        '  fetch(\'/api/orchestrator/status\').then(function(r){return r.json();}).then(function(d){\n'
        '    if(d && typeof d.running!==\'undefined\') setOrchBtn(d.running);\n'
        '  }).catch(function(){});\n'
        '}\n'
        'function stopOrchestrator(){\n'
        '  openConfirm(\'Stop the entire orchestrator chain (watchdog, refill-watcher, worker pool)? The dashboard stays up.\',\'Stop orchestrator\',function(){doStopOrchestrator();});\n'
        '}\n'
        'async function doStopOrchestrator(){\n'
        '  try{\n'
        '    var res=await fetch(\'/api/orchestrator/stop\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:\'{}\'});\n'
        '    var data=await res.json();\n'
        '    if(!res.ok||!data.ok){showMsg(data.message||\'Failed to stop orchestrator.\',\'Stop orchestrator\');return;}\n'
        '    showMsg(data.message||\'Orchestrator stopped.\',\'Stop orchestrator\');\n'
        '    setOrchBtn(false);\n'
        '  }catch(e){showMsg(\'Request failed: \'+e,\'Stop orchestrator\');}\n'
        '}\n'
        'function startOrchestrator(){\n'
        '  openConfirm(\'Start the orchestrator chain (watchdog daemon + refill-watcher)?\',\'Start orchestrator\',function(){doStartOrchestrator();});\n'
        '}\n'
        'async function doStartOrchestrator(){\n'
        '  try{\n'
        '    var res=await fetch(\'/api/orchestrator/start\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:\'{}\'});\n'
        '    var data=await res.json();\n'
        '    if(!res.ok||!data.ok){showMsg(data.message||\'Failed to start orchestrator.\',\'Start orchestrator\');return;}\n'
        '    showMsg(data.message||\'Orchestrator started.\',\'Start orchestrator\');\n'
        '    setOrchBtn(true);\n'
        '  }catch(e){showMsg(\'Request failed: \'+e,\'Start orchestrator\');}\n'
        '}\n'
        'refreshOrchStatus();\n'
        + scripts +

        '(function(){\n'
        '  var RK=\'hb.recents\',TH=3,MAX=4;\n'
        '  function rGet(){try{return JSON.parse(localStorage.getItem(RK)||\'{}\');}catch(e){return {};}}\n'
        '  function rSet(o){try{localStorage.setItem(RK,JSON.stringify(o));}catch(e){}}\n'
        '  var nav=document.querySelector(\'.nav\');\n'
        '  if(nav){nav.querySelectorAll(\'a\').forEach(function(a){\n'
        '    a.addEventListener(\'click\',function(){\n'
        '      var m=(a.getAttribute(\'href\')||\'\').match(/^\\/v\\/([^\\/?#]+)/);\n'
        '      if(!m)return;var o=rGet();o[m[1]]=(o[m[1]]||0)+1;rSet(o);\n'
        '    });\n'
        '  });}\n'
        '  var o=rGet(),es=Object.keys(o).map(function(k){return {k:k,n:o[k]};})\n'
        '    .filter(function(e){return e.n>=TH;}).sort(function(a,b){return b.n-a.n;}).slice(0,MAX);\n'
        '  if(!es.length||!nav)return;\n'
        '  var html=\'<div class="sec">Recents</div>\';\n'
        '  es.forEach(function(e){\n'
        '    var a=nav.querySelector(\'a[href="/v/\'+e.k+\'"]\');if(!a)return;\n'
        '    var lbl=a.querySelector(\'span:not(.ic):not(.badge)\');\n'
        '    var ic=a.querySelector(\'.ic\');\n'
        '    var bd=a.querySelector(\'.badge\');\n'
        '    var act=(location.pathname===\'/v/\'+e.k)?\' class="active"\':\'\';\n'
        '    html+=\'<a href="/v/\'+e.k+\'"\'+act+\'>\'+(ic?ic.outerHTML:\'\')+\'<span>\'+(lbl?lbl.textContent:e.k)+\'</span>\'+(bd?bd.outerHTML:\'\')+\'</a>\';\n'
        '  });\n'
        '  nav.insertAdjacentHTML(\'afterbegin\',html);\n'
        '})();\n'

        '(function(){\n'
        '  var l=document.getElementById(\'layout\');\n'
        '  var b=document.getElementById(\'side-collapse\');\n'
        '  l.classList.toggle(\'collapsed\', localStorage.getItem(\'hb.side\') === \'off\');\n'
        '  b.addEventListener(\'click\', function(){\n'
        '    var c = !l.classList.contains(\'collapsed\');\n'
        '    l.classList.toggle(\'collapsed\', c);\n'
        '    localStorage.setItem(\'hb.side\', c ? \'off\' : \'on\');\n'
        '  });\n'
        '})();\n'
        '</script>\n</body></html>'
    )

NAV_TITLES = {k: (lbl + " · Hackbot") for _, items in NAV for k, lbl, _ in items}
