"""Hackbot dashboard — views module.

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

from .config import CONFIG
from .config import EMAIL_BASE
from .config import EMAIL_DOMAIN
from .config import FINDINGS_FILE
from .config import HUNTS_ROOT
from .config import INTIGRITI_USER
from .config import MAX_SLOTS
from .config import MISC
from .config import PAYLOADS_DIR
from .config import PLATFORM
from .config import PORT_HTTP
from .config import PORT_HTTPS
from .config import QUEUE_FILE
from .config import SESSIONS_CFG
from .config import SESSIONS_ROOT
from .config import TELEGRAM_CHAT
from .config import TELEGRAM_TOKEN
from .config import WATCHDOG_LOG
from .util import age
from .util import count_files
from .util import esc
from .util import fmt_size
from .util import fmt_time
from .util import fmt_ts
from .util import ts_key
from .state import get_findings
from .state import get_queue
from .state import MARK_LABELS
# UNRESOLVED: get_reading (same-module or missing)
from .state import get_run_dirs
from .state import get_session_dirs
from .state import get_workers
from .state import hunt_stats
from .state import all_reports
from .state import all_evidence
from .state import recent_reports
from .state import get_watchdog_reports
from .state import get_watchdog_events
from .state import watchdog_daemon
from .state import watchdog_settings
from .helpers import render_markdown
from .helpers import render_log_html
from .helpers import clp_toggle_js
from .tts import TTS_CSS
from .tts import tts_js
from .tts import tts_settings_panel
from .layout import hero
from .layout import hunt_action_btn
from .icons import icon
from .util import mtime
from .layout import need_attention
# UNRESOLVED: os (same-module or missing)
from .layout import page
from .layout import pill
# UNRESOLVED: re (same-module or missing)
from .util import read_file
from .util import redact
# UNRESOLVED: run_meta (same-module or missing)
# UNRESOLVED: search_memory (same-module or missing)
from .layout import self_hosted_badge
from .layout import severity_pill
from .util import sha
from .util import trunc
from .util import skill_dirs
# UNRESOLVED: skill_info (same-module or missing)
from .state import workers_by_handle
# UNRESOLVED: x (same-module or missing)

def v_overview():
    findings = get_findings()
    workers = get_workers()
    queue = get_queue()
    runs = get_run_dirs()
    sess = get_session_dirs()
    hs = hunt_stats()
    active_w = [w for w in workers if w.get("status") == "running"]
    pending = [t for t in queue if t.get("status") == "pending"]
    top = sorted(queue, key=lambda t: float(t.get("score") or 0), reverse=True)[:6]

    stats = ""
    st = [
        ("Reports", hs["reports"], f'{hs["evidence"]} evidence packs', "clipboard-list", "k-findings"),
        ("Workers", f"{len(active_w)}/{max(MAX_SLOTS, len(active_w))}", "active lanes", "cpu", "k-workers"),
        ("Queue", f"{len(pending)}", f"{len(queue)} programs queued", "target", "k-queue"),
        ("Hunts", hs["hunts"], f'{hs["runs"]} runs · {hs["sessions"]} sessions', "sitemap", "k-hunts"),
    ]
    for lab, val, sub, ic, kid in st:
        stats += (f'<div class="stat"><div class="lab">{icon(ic, 13)} {lab}</div>'
                  f'<div class="val" id="{kid}">{val}</div><div class="sub">{sub}</div></div>')
    stats = f'<div class="stats">{stats}</div>'

    hero_html = hero("Overview", f"{len(queue)} programs queued · {len(active_w)} workers hunting · {PLATFORM} platform")

    wr = ""
    if workers:
        rows = []
        ordered = sorted(workers, key=lambda w: 0 if w.get("status") == "running" else 1)[:10]
        for i, w in enumerate(ordered, 1):
            tname, tfull = trunc(w.get("handle", "") or "", 13)
            rows.append(f'<tr><td style="font-weight:700">{i}</td>'
                        f'<td class="mono" title="{esc(tfull)}">{esc(tname)}</td>'
                        f'<td>{pill(w.get("status",""))}</td>'
                        f'<td class="num">{w.get("bugs_found",0)}</td>'
                        f'<td>{fmt_time(w.get("started_at"))}</td>'
                        f'<td><a class="nw" href="/console?w={esc(w.get("id",""))}">log →</a></td></tr>')
        wr = (f'<div class="card"><div class="hd">Active Workers '
              f'<span class="sp"></span><span class="hint">worker pool · max {MAX_SLOTS} lanes · showing {len(ordered)}/{len(workers)}</span></div>'
              f'<table><thead><tr><th>ID</th><th>TARGET</th><th>STATE</th><th class="num">BUGS</th>'
              f'<th>STARTED</th><th></th></tr></thead>'
              f'<tbody>{"".join(rows)}</tbody></table></div>')
    else:
        wr = (f'<div class="card"><div class="bd"><div class="empty"><div class="ic">{icon("moon", 34)}</div>'
              f'<div class="t">No workers running</div><p>Start the pool from the terminal:</p>'
              f'<p><code class="inline">hackbot-workers start --slots {MAX_SLOTS}</code></p></div></div></div>')

    qrows = ""
    for t in top:
        pname, pfull = trunc(t.get("name", "") or "", 13)
        phint = f' title="{esc(pfull)}"' if pfull != pname else ""
        qrows += (f'<tr><td><a class="node-link" href="/v/assets?target={esc(t.get("handle",""))}"{phint}>{esc(pname)}</a>'
                  f' <span class="mono small muted">{esc(t.get("handle",""))}</span>{self_hosted_badge(t)}</td>'
                  f'<td>{pill(t.get("status","pending"))}</td>'
                  f'<td>{fmt_time(t.get("last_hunted"))}</td>'
                  f'<td>{hunt_action_btn(t)}</td></tr>')
    queue_card = (f'<div class="card"><div class="hd">Target Queue <span class="sp"></span>'
                  f'<span class="hint">top by score</span></div>'
                  f'<table><thead><tr><th>PROGRAM</th><th>STATE</th>'
                  f'<th>LAST HUNT</th><th></th></tr></thead>'
                  f'<tbody>{qrows}</tbody></table></div>')

    rr = recent_reports(6)
    if rr:
        rows = "".join(
            f'<tr><td class="mono">{esc(r["handle"])}</td>'
            f'<td style="font-weight:600"><a href="/report/{esc(r["handle"])}/{esc(r["name"])}">{esc(r["name"][:-3])}</a></td>'
            f'<td>{fmt_ts(r["mtime"])}</td></tr>' for r in rr)
        fr = (f'<div class="card"><div class="hd">Recent Reports <span class="sp"></span>'
              f'<span class="hint">last {len(rr)}</span></div>'
              f'<table><thead><tr><th>PROGRAM</th><th>REPORT</th><th>DRAFTED</th></tr></thead>'
              f'<tbody>{rows}</tbody></table></div>')
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
    scripts = ('setInterval(function(){fetch(\'/api/stats\').then(function(r){return r.json();}).then(function(d){'
               'if(!d||!d.ok){return;}'
               'var kf=document.getElementById(\'k-findings\');if(kf){kf.textContent=d.findings;}'
               'var kw=document.getElementById(\'k-workers\');if(kw){kw.textContent=d.workers_running+\'/\'+d.workers_total;}'
               'var kq=document.getElementById(\'k-queue\');if(kq){kq.textContent=d.queue_pending;}'
               'var kh=document.getElementById(\'k-hunts\');if(kh){kh.textContent=d.hunts_run;}}).catch(function(){})},15000);')
    return page("overview", hero_html, body, refresh=0, scripts=scripts)

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
    lead = (f'<div class="md">{render_markdown(h["interesting"])}</div>' if h["interesting"]
            else f'<div class="empty"><div class="ic">{icon("file-text", 34)}</div><div class="t">No leads captured</div></div>')
    logview = (f'<div class="terminal">{render_log_html(h["log"])}</div>'
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
        ev_rows += f'<tr><td>{icon("archive", 16)}</td><td class="mono">{esc(f)}</td><td class="num">{count_files(fp) if os.path.isdir(fp) else 1}</td><td>{age(fp)}</td><td><a class="nw" href="/evidence/{esc(safe)}/{esc(f)}">view →</a></td></tr>'
    evidence_html = (f'<table><thead><tr><th></th><th>NAME</th><th class="num">ITEMS</th><th>UPDATED</th><th></th></tr></thead>'
                     f'<tbody>{ev_rows}</tbody></table>') if h["evidence"] else f'<div class="empty"><div class="ic">{icon("archive", 34)}</div><div class="t">No evidence captured</div></div>'

    state = pill("running", "ACTIVE") if worker and worker.get("status") == "running" else pill("history", "IDLE")
    target = esc(name)
    findings_rows = ""
    for f in fl[-8:]:
        findings_rows += (f'<tr><td>{severity_pill(f.get("severity"))}</td>'
                          f'<td style="font-weight:600">{esc(f.get("title",""))}</td>'
                          f'<td>{pill(f.get("status",""))}</td>'
                          f'<td>{fmt_time(f.get("ts") or f.get("reported_at"))}</td></tr>')
    findings_html = (f'<table><thead><tr><th>SEV</th><th>TITLE</th><th>STATUS</th>'
                     f'<th>LOGGED</th></tr></thead><tbody>{findings_rows}</tbody></table>'
                     ) if fl else f'<div class="empty"><div class="ic">{icon("search", 34)}</div><div class="t">No findings for this hunt</div></div>'

    orch = ""
    if qitem:
        orch = (f'<div class="card"><div class="hd">Orchestrator · {esc(qitem.get("handle", ""))}</div>'
                f'<div class="bd"><table><thead><tr><th>FIELD</th><th>VALUE</th></tr></thead><tbody>'
                f'<tr><td>Program</td><td>{esc(qitem.get("name",""))}</td></tr>'
                f'<tr><td>State</td><td>{pill(qitem.get("status",""))}</td></tr>'
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
                 f'<tr><td>Log</td><td><a class="nw" href="/console?w={esc(worker.get("id",""))}">open console →</a></td></tr></table></div></div>')
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
                f'<div class="bd md">{render_markdown(h["session_state"] or "(no feature map captured)")}</div></div>')

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

    body = f'<div class="breadcrumb"><span>Workspace / Hunts / <b>{esc(target)}</b></span></div>'
    body += f'<div class="tabs">{tb}</div>{panels}'
    hp = hero(f"<span class='mono'>{esc(target)}</span>",
              sub=f"{esc(h['kind'])} · {esc(os.path.basename(hpath))} · evidence {len(h['evidence'])} · reports {len(h['reports'])} · threads in operator console",
              back="/v/hunts", raw=True)
    return page("hunt", hp, body, scripts=clp_toggle_js())

def v_history():
    queue = sorted(get_queue(), key=lambda t: (str(t.get("status") or ""), -(float(t.get("score") or 0))))
    findings = get_findings()

    trows = "".join(
        f'<tr class="filter-item" data-filter="filter-item" data-search="{esc(t.get("handle",""))} {esc(t.get("name",""))}">'
        f'<td><input type="checkbox" class="qsel" data-h="{esc(t.get("handle",""))}"></td>'
        f'<td><b>{esc(t.get("name",""))}</b> <span class="mono small muted">{esc(t.get("handle",""))}</span></td>'
        f'<td>{pill(t.get("status",""))}</td>'
        f'<td>{" ".join(pill(tg) for tg in (t.get("tags") or [])[:2])}</td>'
        f'<td class="num">{t.get("bugs_found",0)}</td>'
        f'<td>{fmt_time(t.get("last_hunted"))}</td>'
        f'<td>{esc(t.get("last_verdict") or "—")}</td></tr>' for t in queue)
    bulk_bar = ('<div class="fbar" style="margin-bottom:10px">'
                '<span class="muted small"><span id="qsel-n">0</span> selected</span>'
                '<span class="sp" style="flex:1"></span>'
                '<button class="btn ghost small" onclick="bulkQueue(\'start\')">Start hunts</button>'
                '<button class="btn ghost small" onclick="bulkQueue(\'reset\')">Reset</button>'
                '<button class="btn ghost small" onclick="bulkQueue(\'skip\')">Skip</button>'
                '<button class="btn ghost small" onclick="bulkQueue(\'clear\')">Clear</button></div>')
    table = (f'<div class="card"><div class="hd">Target Ledger <span class="sp"></span>'
             f'<span class="hint">{len(queue)} programs</span></div>'
             f'<div class="bd" style="padding-bottom:6px">{bulk_bar}</div>'
             f'<table><thead><tr><th></th><th>PROGRAM</th><th>STATE</th><th>TAGS</th>'
             f'<th class="num">BUGS</th><th>LAST HUNT</th><th>VERDICT</th></tr></thead><tbody>{trows}</tbody></table></div>')

    frows = "".join(
        f'<tr class="filter-item" data-filter="filter-item" data-search="{esc(f.get("program",""))} {esc(f.get("title",""))}">'
        f'<td>{severity_pill(f.get("severity"))}</td>'
        f'<td style="font-weight:600">{esc(f.get("title",""))}</td>'
        f'<td class="mono">{esc(f.get("program",""))}</td>'
        f'<td>{pill(f.get("status",""))}</td>'
        f'<td>{fmt_time(f.get("ts") or f.get("reported_at"))}</td></tr>' for f in reversed(findings))
    ftable = (f'<div class="card"><div class="hd">Findings Timeline <span class="sp"></span>'
              f'<span class="hint">{len(findings)} logged</span></div>'
              f'<table><thead><tr><th>SEV</th><th>TITLE</th><th>PROGRAM</th><th>STATUS</th>'
              f'<th>LOGGED</th></tr></thead><tbody>{frows or ""}</tbody></table></div>')

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

# ── Watchdog ───────────────────────────────────────────────────────────────────
# The 30-minute monitor used to Telegram a per-cycle summary. That delivery was
# removed; this panel is where those messages surface instead — one bubble per
# cycle report, plus the timeout alerts it still sends.

_WG_CSS = """
.wg-feed{display:flex;flex-direction:column;gap:12px}
.wg-msg{background:var(--card);border:1px solid var(--border);border-left:3px solid var(--grey);border-radius:12px;box-shadow:var(--shadow);overflow:hidden}
.wg-msg.good{border-left-color:var(--green)}
.wg-msg.warn{border-left-color:var(--amber)}
.wg-msg.bad{border-left-color:var(--accent)}
.wg-msg-hd{display:flex;align-items:center;gap:9px;padding:10px 14px;background:#fbf9f5;border-bottom:1px solid #eee8dd}
.wg-msg-hd .ic-svg{color:var(--muted);flex:none}
.wg-msg.bad .wg-msg-hd .ic-svg{color:var(--accent)}
.wg-msg.good .wg-msg-hd .ic-svg{color:var(--green)}
.wg-kind{font-size:10.5px;font-weight:800;letter-spacing:.09em;color:var(--muted)}
.wg-msg-hd time{margin-left:auto;font-size:11.5px;color:var(--muted);white-space:nowrap}
.wg-msg-body{padding:13px 15px}
.wg-counts{display:flex;flex-wrap:wrap;gap:5px 16px;margin-bottom:11px}
.wg-count{font-size:12.5px;color:var(--muted)}
.wg-count b{color:var(--ink);font-variant-numeric:tabular-nums;font-weight:800}
.wg-actions{list-style:none;display:flex;flex-direction:column;gap:9px;margin:0;padding:0}
.wg-actions li{font-size:12.5px;line-height:1.45}
.wg-actions .han{font-weight:700;color:var(--ink);margin-left:7px}
.wg-actions .act{color:var(--muted)}
.wg-why{display:block;color:var(--muted);font-size:11.5px;margin-top:2px;padding-left:2px}
"""


def _wg_clock(ts):
    """'Sep 16 · 11:40Z' from an ISO-8601 Z timestamp."""
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).strftime("%b %d · %H:%MZ")
    except Exception:
        return str(ts or "—")


def _wg_rel(ts):
    """Human '3h ago' from an ISO-8601 Z timestamp."""
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        secs = (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return ""
    if secs < 90:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def _wg_verdict(v):
    s = (v or "").strip().rstrip("*").upper()
    state = {"HEALTHY": "running", "ALIVE": "running", "DONE": "running",
             "DEAD": "failed", "FAILED": "failed",
             "STUCK": "attention", "WEDGED": "attention", "HUNG": "attention"}.get(s, "idle")
    return pill(state, s or "—")


def v_watchdog():
    daemon = watchdog_daemon()
    cfg = watchdog_settings()
    reports = get_watchdog_reports(40)
    events = get_watchdog_events(120)

    # The messages the watchdog would have pushed: one per cycle report, plus
    # the rare timeout alert (the one notification it still sends).
    notes = [{"kind": "cycle", "ts": r["ts"], "report": r} for r in reports]
    timeouts = [e for e in events if e["kind"] == "timeout"]
    notes += [{"kind": "timeout", "ts": e["ts"], "msg": e["msg"]} for e in timeouts]
    notes.sort(key=lambda n: n.get("ts") or "", reverse=True)

    last_rel = _wg_rel(reports[0]["ts"]) if reports else ""

    stats = ""
    d_color = "var(--green)" if daemon["running"] else "var(--grey)"
    d_word = "RUNNING" if daemon["running"] else "STOPPED"
    d_sub = f'PID {esc(daemon["pid"])}' if (daemon["running"] and daemon["pid"]) else "daemon idle"
    st = [
        ("Daemon", f'<span style="color:{d_color}">{d_word}</span>', d_sub, "radio"),
        ("Interval", f'{cfg["interval"] // 60} min', f'{cfg["interval"]}s between cycles', "clock"),
        ("Timeout", f'{cfg["timeout"] // 60} min', "hard cap per cycle", "alert-triangle"),
        ("Cycles", str(len(reports)), f'latest {last_rel}' if last_rel else "none recorded", "refresh-cw"),
        ("Alerts", str(len(timeouts)), "timeout notifications", "x-circle"),
    ]
    for lab, val, sub, ic in st:
        stats += (f'<div class="stat"><div class="lab">{icon(ic, 13)} {lab}</div>'
                  f'<div class="val">{val}</div><div class="sub">{esc(sub)}</div></div>')
    stats = f'<div class="stats">{stats}</div>'

    bubbles = []
    for n in notes[:40]:
        if n["kind"] == "timeout":
            body = (f'<div class="wg-counts"><span class="wg-count">Monitor cycle exceeded '
                    f'<b>{cfg["timeout"]}s</b> and was killed — the worker lane is stuck, not slow. '
                    f'This is the one alert the watchdog still sends.</span></div>')
            bubbles.append(
                f'<article class="wg-msg bad"><div class="wg-msg-hd">{icon("alert-triangle", 15)}'
                f'<span class="wg-kind">TIMEOUT</span><time>{_wg_clock(n["ts"])}</time></div>'
                f'<div class="wg-msg-body">{body}</div></article>')
            continue

        r = n["report"]
        tone = "bad" if (r["fixed"] or r["stuck"]) else "good"
        acts = ""
        for a in r["actions"]:
            why = f'<span class="wg-why">{esc(a["reason"])}</span>' if a["reason"] else ""
            acts += (f'<li>{_wg_verdict(a["verdict"])}<span class="han mono">{esc(a["handle"])}</span> '
                     f'<span class="act">→ {esc(a["action"])}</span>{why}</li>')
        if not acts:
            acts = '<li class="muted">No actions taken — every lane healthy.</li>'
        stuck_chip = f'<span class="wg-count"><b>{r["stuck"]}</b> stuck</span>' if r["stuck"] else ""
        counts = (f'<div class="wg-counts">'
                  f'<span class="wg-count"><b>{r["fixed"]}</b> fixed</span>'
                  f'<span class="wg-count"><b>{r["healthy"]}</b> healthy</span>'
                  f'<span class="wg-count"><b>{r["running"]}</b> running</span>'
                  f'{stuck_chip}'
                  f'<span class="wg-count">{r["slots"]} slots</span></div>')
        bubbles.append(
            f'<article class="wg-msg {tone}"><div class="wg-msg-hd">{icon("send", 15)}'
            f'<span class="wg-kind">CYCLE</span><time>{_wg_clock(r["ts"])}</time></div>'
            f'<div class="wg-msg-body">{counts}<ul class="wg-actions">{acts}</ul></div></article>')

    if bubbles:
        feed = (f'<div class="card"><div class="hd">Notifications <span class="sp"></span>'
                f'<span class="hint">what the watchdog sends — delivered here instead of Telegram</span></div>'
                f'<div class="bd"><div class="wg-feed">{"".join(bubbles)}</div></div></div>')
    else:
        feed = (f'<div class="card"><div class="bd"><div class="empty"><div class="ic">{icon("radio", 34)}</div>'
                f'<div class="t">No watchdog messages yet</div>'
                f'<p>Start the watchdog daemon (or run it once) — each cycle writes a report and the '
                f'messages it would send you appear here.</p></div></div></div>')

    log_lines = "\n".join(f'[{e["ts"]}] {e["msg"]}' for e in reversed(events))
    log_card = (f'<div class="card"><div class="hd">Cycle log <span class="sp"></span>'
                f'<span class="hint">{esc(os.path.basename(WATCHDOG_LOG))} · last {len(events)} lines</span></div>'
                f'<pre class="terminal">{esc(log_lines) or "(log empty)"}</pre></div>')

    hero_html = hero(
        "Watchdog",
        f"30-minute monitor · {len(reports)} cycles recorded · "
        f"{len(timeouts)} timeout alert{'s' if len(timeouts) != 1 else ''}",
    )
    return page("watchdog", hero_html, stats + feed + log_card, refresh=0, extra_css=_WG_CSS)

def rel_graph(workers, runs, sess, by_prog, findings):
    left = [("Worker " + str(w.get("slot", "?")), str(w.get("handle") or ""), f"/console?w={esc(w.get('id',''))}")
            for w in workers if w.get("status") == "running"]
    left += [(("session " + s["name"]), s["handle"], f"/hunts?name={esc(s['name'])}") for s in sess]
    left += [("run " + r["name"], r["handle"], f"/hunts?name={esc(r['name'])}") for r in runs]
    left = left[:18]

    mids = []
    for h in sorted({str(w.get("handle") or "") for w in workers if w.get("handle")}):
        mids.append(h)
    for r in runs:
        if r["handle"] not in mids:
            mids.append(r["handle"])
    for s in sess:
        if s["handle"] not in mids:
            mids.append(s["handle"])

    right = sorted(findings, key=lambda f: ts_key(f.get("ts")), reverse=True)[:14]

    if not left and not mids and not right:
        return ('<svg viewBox="0 0 940 120" xmlns="http://www.w3.org/2000/svg">'
                '<text x="470" y="70" text-anchor="middle" class="role">no relationships recorded yet</text></svg>')

    lx, mx, rx, cw = 20, 340, 660, 260
    rows = max(len(left), len(mids), len(right), 1)
    H = max(180, rows * 52 + 24)

    def col_ys(n):
        if n == 0:
            return []
        step = max(40, (H - 56) / n)
        base = 40 + step / 2
        return [int(base + i * step) for i in range(n)]

    ly = col_ys(len(left))
    my = col_ys(len(mids))
    ry = col_ys(len(right))
    mid_y = dict(zip(mids, my))

    parts = [f'<svg viewBox="0 0 940 {H}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">']

    def curve(x1, y1, x2, y2):
        dx = int(max(30, abs(x2 - x1) * 0.5))
        return (f'<path d="M{x1} {y1} C{x1+dx} {y1},{x2-dx} {y2},{x2} {y2}" fill="none"/>')

    for k, f in enumerate(right):
        prog = f.get("program") or ""
        if prog in mid_y:
            parts.append(curve(rx, ry[k], mx + cw, mid_y[prog]))
    for i, (label, handle, _href) in enumerate(left):
        if handle and handle in mid_y:
            parts.append(curve(lx + cw, ly[i], mx, mid_y[handle]))

    parts.append(f'<text x="{lx+cw-90}" y="18" class="role">SOURCES</text>')
    parts.append(f'<text x="{mx+cw-130}" y="18" class="role">HUNTS</text>')
    parts.append(f'<text x="{rx+cw-140}" y="18" class="role">FINDINGS</text>')

    for i, (label, _handle, href) in enumerate(left):
        y = ly[i]
        parts.append(f'<g class="g-run"><a href="{href}"><rect x="{lx}" y="{y-12}" width="{cw}" height="26" rx="6"/>'
                     f'<text x="{lx+cw/2}" y="{y+4}" text-anchor="middle" font-size="11">{esc(label[:30])}</text></a></g>')
    for j, h in enumerate(mids):
        y = my[j]
        parts.append(f'<g class="g-worker"><a href="/v/assets?target={esc(h)}"><rect x="{mx}" y="{y-12}" width="{cw}" height="26" rx="6"/>'
                     f'<text x="{mx+cw/2}" y="{y+4}" text-anchor="middle" font-size="11">{esc(h[:30])}</text></a></g>')
    for k, f in enumerate(right):
        y = ry[k]
        t = (f.get("title") or "?")[:32]
        parts.append(f'<g class="g-find"><a href="/v/history"><rect x="{rx}" y="{y-12}" width="{cw}" height="26" rx="6"/>'
                     f'<text x="{rx+cw/2}" y="{y+4}" text-anchor="middle" font-size="11">{esc(t)}</text></a></g>')
    parts.append('</svg>')
    return "".join(parts)

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
                      f'<div class="statline">{pill(w.get("status",""),"")} · slot {w.get("slot","?")}</div>'
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
    body = (f'<div class="graph">{rel_graph(workers, runs, sess, by_prog, findings)}</div>'
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

def _trim_program(handle: str, n: int = 24) -> str:
    """Trim a program handle for display; full value stays in data-search/link attrs."""
    h = str(handle)
    return h if len(h) <= n else h[: n - 1] + "\u2026"


def v_findings():
    hs = hunt_stats()
    reps = sorted(all_reports(), key=lambda r: r["mtime"], reverse=True)
    evi = sorted(all_evidence(), key=lambda e: e["mtime"], reverse=True)
    unread = sum(1 for r in reps if not r["read"])

    stats = (f'<div class="stats">'
             f'<div class="stat"><div class="lab">{icon("file-text", 13)} Reports</div>'
             f'<div class="val">{hs["reports"]}</div><div class="sub">{unread} unread · {len({r["handle"] for r in reps})} programs</div></div>'
             f'<div class="stat"><div class="lab">{icon("paperclip", 13)} Evidence</div>'
             f'<div class="val">{hs["evidence"]}</div><div class="sub">{len({e["handle"] for e in evi})} programs with evidence</div></div>'
             f'<div class="stat"><div class="lab">{icon("target", 13)} Coverage</div>'
             f'<div class="val">{hs["hunts"]}</div><div class="sub">{hs["runs"]} runs · {hs["sessions"]} sessions</div></div>'
             f'</div>')

    def mk_pill(mark):
        if not mark:
            return '<span class="muted small">\u2014</span>'
        return f'<span class="mk mk-{esc(mark)}">{esc(MARK_LABELS.get(mark, mark))}</span>'

    rrows = "".join(
        f'<tr class="{"unread" if not r["read"] else ""}" data-filter="filter-item" data-search="{esc(r["handle"])} {esc(r["name"])}"'
        f' data-mark="{esc(r["mark"])}" data-read="{"1" if r["read"] else "0"}">'
        f'<td>{f"<span class=dot-u></span>" if not r["read"] else ""}</td>'
        f'<td class="mono" title="{esc(r["handle"])}">{esc(_trim_program(r["handle"]))}</td>'
        f'<td style="font-weight:600"><a href="/report/{esc(r["handle"])}/{esc(r["name"])}">{esc(r["name"][:-3])}</a></td>'
        f'<td class="num">{fmt_size(os.path.getsize(r["path"]))}</td>'
        f'<td>{fmt_ts(r["mtime"])}</td>'
        f'<td>{f"<span class=unread-tag>UNREAD</span>" if not r["read"] else f"<span class=muted small>read</span>"}</td>'
        f'<td>{mk_pill(r["mark"])}</td></tr>' for r in reps)
    fbar = (f'<div class="fbar fbar-card" id="rep-filterbar">'
            f'<span class="flbl">Mark</span>'
            f'<button class="f active" data-fmark="" onclick="repFilter(this)">All marks</button>'
            + "".join(f'<button class="f" data-fmark="{mk}" onclick="repFilter(this)">{esc(lbl)}</button>'
                      for mk, lbl in MARK_LABELS.items())
            + f'<span class="sp"></span>'
            f'<span class="flbl">State</span>'
            f'<button class="f active" data-fstate="" onclick="repFilter(this)">All</button>'
            f'<button class="f" data-fstate="unread" onclick="repFilter(this)">Unread</button>'
            f'<button class="f" data-fstate="read" onclick="repFilter(this)">Read</button>'
            f'</div>')
    reports_card = (f'<div class="card" id="repcard"><div class="hd">Reports <span class="sp"></span>'
                    f'<span class="hint">{len(reps)} files · {unread} unread</span></div>'
                    f'{fbar}'
                    f'<table><thead><tr><th></th><th>PROGRAM</th><th>REPORT</th><th class="num">SIZE</th><th>DRAFTED</th><th>STATE</th><th>MARK</th></tr></thead>'
                    f'<tbody>{rrows or f"<tr><td colspan=7><span class=muted>No reports drafted yet</span></td></tr>"}</tbody></table>'
                    f'<div class="pager" id="rep-pager"></div></div>')

    erows = "".join(
        f'<tr><td class="mono" title="{esc(e["handle"])}">{esc(_trim_program(e["handle"]))}</td>'
        f'<td class="mono">{esc(e["name"])}</td>'
        f'<td>{fmt_size(os.path.getsize(e["path"]))}</td>'
        f'<td>{fmt_ts(e["mtime"])}</td></tr>' for e in evi)
    evidence_card = (f'<div class="card"><div class="hd">Evidence <span class="sp"></span>'
                     f'<span class="hint">{len(evi)} files</span></div>'
                     f'<table><thead><tr><th>PROGRAM</th><th>FILE</th><th class="num">SIZE</th><th>ADDED</th></tr></thead>'
                     f'<tbody>{erows or f"<tr><td colspan=4><span class=muted>No evidence collected yet</span></td></tr>"}</tbody></table></div>')

    find_js = """(function(){
var KEY='hb.find';var st={mark:'',read:'',page:1};
try{var s=localStorage.getItem(KEY);if(s){var o=JSON.parse(s);if(o&&typeof o==='object'){st.mark=o.mark||'';st.read=o.read||'';st.page=parseInt(o.page,10)||1;}}}catch(e){}
var PAGE=30;
function visibleRows(){
  var rows=document.querySelectorAll('#repcard tbody tr'),out=[],i,r,show;
  for(i=0;i<rows.length;i++){r=rows[i];show=true;
    if(st.mark&&r.getAttribute('data-mark')!==st.mark){show=false;}
    if(show&&st.read){var rd=r.getAttribute('data-read');show=(st.read==='unread')?(rd==='0'):(rd==='1');}
    if(show)out.push(r);}
  return out;}
function renderPager(total){
  var el=document.getElementById('rep-pager');if(!el)return;
  var pages=Math.max(1,Math.ceil(total/PAGE));
  if(st.page>pages)st.page=pages;
  if(!total){el.innerHTML='<span class="pg-info">No reports match</span>';return;}
  var start=(st.page-1)*PAGE+1,end=Math.min(st.page*PAGE,total);
  var h='<span class="pg-info">'+start+'\u2013'+end+' of '+total+'</span>';
  h+='<button class="pg-btn" data-pg="prev"'+(st.page<=1?' disabled':'')+'>\u2039 Prev</button>';
  var from=Math.max(1,st.page-2),to=Math.min(pages,st.page+2);
  if(from>1){h+='<button class="pg-btn" data-pg="1">1</button>';if(from>2)h+='<span class="pg-ell">\u2026</span>';}
  for(var p=from;p<=to;p++){h+='<button class="pg-btn'+(p===st.page?' active':'')+'" data-pg="'+p+'">'+p+'</button>';}
  if(to<pages){if(to<pages-1)h+='<span class="pg-ell">\u2026</span>';h+='<button class="pg-btn" data-pg="'+pages+'">'+pages+'</button>';}
  h+='<button class="pg-btn" data-pg="next"'+(st.page>=pages?' disabled':'')+'>Next \u203a</button>';
  el.innerHTML=h;}
function apply(){
  var vis=visibleRows();var i,r,rows=document.querySelectorAll('#repcard tbody tr');
  for(i=0;i<rows.length;i++)rows[i].classList.add('hide-js');
  var start=(st.page-1)*PAGE,end=Math.min(start+PAGE,vis.length);
  for(i=start;i<end;i++)vis[i].classList.remove('hide-js');
  var bs=document.querySelectorAll('#rep-filterbar .f'),j,b,m,s;
  for(j=0;j<bs.length;j++){b=bs[j];m=b.getAttribute('data-fmark');s=b.getAttribute('data-fstate');
    if(m!==null)b.classList.toggle('active',m===st.mark);else if(s!==null)b.classList.toggle('active',s===st.read);}
  renderPager(vis.length);}
window.repFilter=function(btn){var m=btn.getAttribute('data-fmark'),s=btn.getAttribute('data-fstate');
  if(m!==null)st.mark=m;if(s!==null)st.read=s;st.page=1;
  try{localStorage.setItem(KEY,JSON.stringify(st));}catch(e){}apply();};
window.repPage=function(btn){var pg=btn.getAttribute('data-pg');
  if(pg==='prev')st.page=Math.max(1,st.page-1);else if(pg==='next')st.page+=1;else st.page=parseInt(pg,10)||1;
  try{localStorage.setItem(KEY,JSON.stringify(st));}catch(e){}apply();};
apply();
})();"""

    body = stats + reports_card + evidence_card
    return page("findings", hero("Findings", "Reports and evidence across every hunt"), body, scripts=find_js)

def v_assets(q=None):
    queue = sorted(get_queue(), key=lambda t: -(float(t.get("score") or 0)))
    handlers = {}
    for w in get_workers():
        handlers[w.get("handle")] = w
    rows = ""
    for t in queue:
        pname, pfull = trunc(t.get("name", ""), 25)
        phint = f' title="{esc(pfull)}"' if pfull != pname else ""
        url = t.get("base_url") or ""
        udisp, ufull = trunc(url, 48)
        uhint = f' title="{esc(ufull)}"' if ufull != udisp else ""
        rows += (f'<tr class="filter-item as-row" data-filter="filter-item" data-search="{esc(t.get("handle",""))} {esc(t.get("name",""))} {esc(url)}">'
                 f'<td><b{phint}>{esc(pname)}</b>{self_hosted_badge(t)}'
                 + (f'<div class="mono small muted as-url"{uhint} data-full="{esc(url)}">{esc(udisp)}</div>' if url else "")
                 + f'</td>'
                 f'<td>{pill(t.get("status",""))}</td>'
                 f'<td>{" ".join(pill(tg) for tg in (t.get("tags") or [])[:3])}</td>'
                 f'<td>{pill("running","HUNTING") if t.get("handle") in handlers and handlers[t.get("handle")].get("status") == "running" else pill("idle","IDLE")}</td>'
                 f'<td>{hunt_action_btn(t)}</td></tr>')
    body = (f'<div class="card"><div class="hd">In-Scope Targets <span class="sp"></span>'
            f'<span class="hint">{len(queue)} programs · {sum(1 for t in queue if t.get("status")=="active")} active</span></div>'
            f'<table><thead><tr><th>PROGRAM</th><th>STATE</th>'
            f'<th>TAGS</th><th>WORKER</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>')
    js = ("(function(){"
          "document.addEventListener('click',function(e){"
          "var t=e.target.closest?e.target.closest('.as-row'):null;"
          "if(!t)return;"
          "if(e.target.closest&&e.target.closest('button,a'))return;"
          "var u=t.querySelector('.as-url');"
          "if(!u)return;"
          "var full=u.getAttribute('data-full')||'';"
          "if(u.classList.contains('open')){u.textContent=u.getAttribute('data-short')||u.textContent;u.classList.remove('open');t.classList.remove('as-open');}"
          "else{u.setAttribute('data-short',u.textContent);u.textContent=full;u.classList.add('open');t.classList.add('as-open');}"
          "});"
          "})();")
    css = (".as-row{cursor:pointer}"
           ".as-row .as-url{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:340px}"
           ".as-row.as-open .as-url{white-space:normal;word-break:break-all;max-width:none}")
    return page("assets", hero("Assets", "Every in-scope program with tags and hunt state"), body, extra_css=css, scripts=js)

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
    body += (f'<div style="margin-bottom:12px" class="fbar">'
             f'<button class="btn ghost small" onclick="newSkill()">+ New skill</button>'
             f'<button class="btn ghost small" onclick="location.reload()">Refresh</button>'
             f'<button class="btn ghost small" onclick="importSkill()">Import from Git</button></div>')
    body += lib
    smodal = ('<div class="modal-bg" id="smodal" onclick="if(event.target===this)this.style.display=\'none\'">'
              '<div class="modal"><div class="hd">New skill / Import</div><div class="bd">'
              '<div id="s-err" class="small" style="color:var(--accent);display:none;margin-bottom:8px"></div>'
              '<div class="hd" style="border:none;padding:0 0 6px;font-size:12.5px">New skill</div>'
              '<input id="s-name" class="fld" placeholder="skill name (e.g. hunt-oauth)">'
              '<input id="s-folder" class="fld" style="margin-top:6px" placeholder="folder — defaults to the first skill dir">'
              '<div style="text-align:right;margin-top:8px"><button class="btn small" onclick="newSkillSubmit()">Create skill</button></div>'
              '<div class="hd" style="border:none;padding:12px 0 6px;font-size:12.5px">Import from Git</div>'
              '<input id="s-url" class="fld" placeholder="https://github.com/user/repo or local path">'
              '<div style="text-align:right;margin-top:8px"><button class="btn small" onclick="importSkillSubmit()">Import skill</button></div>'
              '</div></div></div>')
    return page("skills", hero("Skills", "Centrally managed skill library — routed to Claude Code / Codex"),
                body + smodal)

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
            f'<span class="sp"></span>{pill("connected","CONNECTED")} <span class="btn ghost small" onclick="mailboxReconnect(this)">Reconnect</span></div>'
            f'<div class="bd"><p class="muted small">Catch-all mailbox <code class="inline">{esc(mailbox)}</code> '
            f'(OTP / verification codes land here). Credentials archived per session.</p></div></div>'
            f'<div class="card"><div class="hd">Signed-up accounts <span class="sp"></span>'
            f'<span class="hint">{total} credential sets</span></div>'
            f'<table><thead><tr><th>TARGET</th><th>FILE</th><th>EMAIL</th><th>CREATED</th><th></th></tr></thead>'
            f'<tbody>{rows or ""}</tbody></table></div>')
    return page("registrations", hero("Registrations", "Shared platform mailbox for OTP codes and account credentials"), body)
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

    donut = (f'<div class="donut" id="u-donut" style="background:conic-gradient(var(--green) 0% {int(percent*100)}%, var(--grey) {int(percent*100)}% 100%)">'
             f'<div class="core"><div class="big" id="u-pct">{int(percent*100)}%</div><div class="sm">hunted</div></div></div>')
    legend = (f'<div class="legend"><div class="lg"><span class="sw" style="background:var(--green)"></span>'
              f'<span class="name">Hunted</span><span class="pct" id="u-hunted">{hunted}</span></div>'
              f'<div class="lg"><span class="sw" style="background:var(--grey)"></span>'
              f'<span class="name">Pending</span><span class="pct" id="u-pending">{total-hunted}</span></div>'
              f'<div class="lg"><span class="sw" style="background:var(--accent)"></span>'
              f'<span class="name">Workers active</span><span class="pct">{len([w for w in workers if w.get("status")=="running"])}</span></div></div>')
    stats = "<div class='stats'>"
    stats += (f'<div class="stat"><div class="lab">HUNTS RUN</div><div class="val" id="u-hunts">{len(runs)}</div>'
              f'<div class="sub">{len(sess)} sessions</div></div>')
    stats += (f'<div class="stat"><div class="lab">FINDINGS</div><div class="val" id="u-findings">{len(findings)}</div>'
              f'<div class="sub">logged to ledger</div></div>')
    stats += (f'<div class="stat"><div class="lab">QUEUE</div><div class="val" id="u-queue">{total}</div>'
              f'<div class="sub">{sum(1 for t in queue if t.get("status")=="active")} active</div></div>')
    stats += "</div>"

    ledger = "".join(
        f'<tr class="filter-item" data-filter="filter-item" data-search="{esc(t.get("handle",""))} {esc(t.get("name",""))}">'
        f'<td><b>{esc(t.get("handle",""))}</b></td>'
        f'<td>{pill(t.get("status","pending"))}</td>'
        f'<td class="num">{t.get("score",0)}</td>'
        f'<td>{fmt_time(t.get("last_hunted"))}</td>'
        f'<td>{esc(t.get("last_verdict") or "—")}</td></tr>' for t in sorted(queue, key=lambda x: -(float(x.get("score") or 0))))
    ledger_table = (f'<div class="card"><div class="hd">Target Ledger <span class="sp"></span>'
                    f'<span class="hint">ranked · {len(queue)}</span></div>'
                    f'<table><thead><tr><th>TARGET</th><th>STATE</th>'
                    f'<th class="num">SCORE</th><th>LAST HUNT</th><th>VERDICT</th></tr></thead>'
                    f'<tbody>{ledger}</tbody></table></div>')

    share_card = (f'<div class="card"><div class="hd">HUNT SHARE <span class="sp"></span>'
                  f'<span class="hint">live coverage</span></div>'
                  f'<div class="range-pills">'
                  f'<span class="r active" onclick="usageRange(\'all\',this)">all time</span>'
                  f'<span class="r" onclick="usageRange(\'30d\',this)">30 days</span>'
                  f'<span class="r" onclick="usageRange(\'7d\',this)">7 days</span>'
                  f'<span class="r" onclick="usageRange(\'24h\',this)">24 hours</span>'
                  f'</div>'
                  f'<div class="donut-wrap">{donut}{legend}</div>'
                  f'<div class="bd small muted" style="border-top:1px solid var(--border)">'
                  f'Coverage = hunted targets against the full queue. Model token accounting hooks into the '
                  f'operator-console provider (opencode/DeepSeek); when reported, a per-model ledger renders here.</div></div>')

    body = stats + f'<div class="row"><div class="col">{share_card}</div><div class="col">{ledger_table}</div></div>'
    return page("usage", hero("Usage", "Operator activity — hunts, findings and coverage"), body)

def v_settings():
    cfg = CONFIG
    tb = ("<div class='tabs'>"
          + '<span class="t active" data-tabbtn="s" data-target="s1" onclick="showTab(\'s\',\'s1\')">Agent providers</span>'
          + '<span class="t" data-tabbtn="s" data-target="s2" onclick="showTab(\'s\',\'s2\')">Channels</span>'
          + '<span class="t" data-tabbtn="s" data-target="s3" onclick="showTab(\'s\',\'s3\')">Credentials</span>'
          + '<span class="t" data-tabbtn="s" data-target="s4" onclick="showTab(\'s\',\'s4\')">Data</span>'
          + '<span class="t" data-tabbtn="s" data-target="s5" onclick="showTab(\'s\',\'s5\')">Progress observer</span>'
          + "<span class='t' data-tabbtn='s' data-target='s6' onclick=\"showTab('s','s6')\">System prompts</span>"
          + '<span class="t" data-tabbtn="s" data-target="s7" onclick="showTab(\'s\',\'s7\')">Voice</span>'
          + "</div>")

    provider_card = (f'<div class="card"><div class="hd">opencode ({esc(PLATFORM)}) <span class="sp"></span>'
                 f'{pill("enabled")} <span class="btn ghost small" onclick="configOpen(\'providers\')">Configure</span>'
                 f'<span class="btn ghost small" onclick="testProvider(\'opencode\',this)">Test</span></div>'
                 f'<div class="bd"><table>'
                 f'<tr><td class="muted">Console CLI</td><td>opencode run --agent hunter</td></tr>'
                 f'<tr><td class="muted">Agent skill</td><td class="mono">@bug-hunting</td></tr>'
                 f'<tr><td class="muted">Models</td><td>provider-managed (opf free tier)</td></tr>'
                 f'<tr><td class="muted">Worker lanes</td><td>{MAX_SLOTS}</td></tr></table></div></div>')
    provider_card2 = (f'<div class="card"><div class="hd">DeepSeek (Anthropic) <span class="sp"></span>'
                      f'{pill("enabled")} <span class="btn ghost small" onclick="configOpen(\'providers\')">Configure</span>'
                      f'<span class="btn ghost small" onclick="testProvider(\'deepseek\',this)">Test</span></div>'
                      f'<div class="bd"><p class="small">DeepSeek v4.1 Flash (Anthropic) switchable per-console.</p></div></div>')

    chan = (f'<div class="card"><div class="hd">Telegram <span class="sp"></span>{pill("enabled")} '
        f'<span class="btn ghost small" onclick="configOpen(\'channels\')">Configure</span>'
        f'<span class="btn ghost small" onclick="testTelegram(this)">Test</span></div>'
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
              f'<div id="s6" data-tabgroup="s" style="display:none">{sysprompts}</div>'
              f'<div id="s7" data-tabgroup="s" style="display:none">{tts_settings_panel()}</div>')
    body = tb + panels + ('<div class="modal-bg" id="cmodal" onclick="if(event.target===this)this.style.display=\'none\'">'
                      '<div class="modal"><div class="hd">Configure</div><div class="bd">'
                      '<div id="c-err" class="small" style="color:var(--accent);display:none;margin-bottom:8px"></div>'
                      '<div class="lbl">Section</div><input id="c-which" class="fld" value="" readonly>'
                      '<div class="lbl">Setting key (dotted, e.g. tokens.telegram)</div><input id="c-key" class="fld" placeholder="key">'
                      '<div class="lbl">Value</div><input id="c-val" class="fld" placeholder="new value">'
                      '<div style="text-align:right;margin-top:12px">'
                      '<button class="btn ghost small" onclick="closeM(\'cmodal\')">Cancel</button>'
                      '<button class="btn small" style="margin-left:8px" onclick="configSave()">Save</button>'
                      '</div></div></div></div>')
    return page("settings", hero("Settings", "Agent providers, channels, credentials and operator data"), body,
                extra_css=TTS_CSS, scripts=tts_js())
