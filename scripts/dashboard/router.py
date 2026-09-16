"""Hackbot dashboard — router module.

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
import hashlib
import unicodedata
import urllib.parse
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import HUNTS_ROOT
from .config import SESSIONS_ROOT
from .actions import _api_add_target
from .actions import _api_start_target
from .actions import _api_stop_target
from .actions import _api_config_update
from .actions import _api_findings_add
from .actions import _api_findings_update
from .actions import _api_mailbox_test
from .actions import _api_pool_action
from .actions import _api_provider_test
from .actions import _api_queue_bulk
from .actions import _api_report_mark
from .actions import _api_skills_import
from .actions import _api_skills_new
from .actions import _api_telegram_test
from .actions import _api_console_tell
from .console import _console_for
from .console import _resolve_log
from .console import _detect_activity
from .console import _ensure_caido
from .console import _worker_id_from_log
from .console import _strip_emoji
from .util import age
from .ansi import ansi_to_html
from .util import count_files
from .util import esc
from .util import fmt_size
from .state import get_findings
from .state import get_pool
from .state import get_queue
from .state import get_run_dirs
from .state import get_session_dirs
from .state import get_workers
from .state import hunt_stats
from .state import MARK_LABELS
from .helpers import decorate_curls
from .helpers import render_markdown
from .helpers import render_log_html
from .helpers import resolve_hunt_root
from .tts import TTS_CSS
from .tts import tts_js
from .tts import tts_reader_bar
from .state import mark_report_read
from .state import report_mark
from .layout import hero
from .icons import icon
# UNRESOLVED: json (same-module or missing)
from .util import mtime
# UNRESOLVED: os (same-module or missing)
from .layout import page
# UNRESOLVED: re (same-module or missing)
from .util import read_file
from .util import read_tail
from .views import search_memory
from .util import skill_dirs
from .views import v_assets
from .views import v_findings
from .views import v_history
from .views import v_hunt
from .views import v_hunts
from .views import v_knowledge
from .views import v_memory
from .views import v_monitors
from .views import v_overview
from .views import v_registrations
from .views import v_settings
from .views import v_skills
from .views import v_topology
from .views import v_usage
from .views import v_workspaces
from .layout import need_attention


def _resolve_hunt_root(name: str) -> str:
    """Back-compat alias — the resolver now lives in helpers."""
    return resolve_hunt_root(name)

TEXT_EXTS = {".md", ".markdown", ".txt", ".log", ".json", ".req", ".http", ".py", ".sh", ".yaml", ".yml",
             ".toml", ".csv", ".ts", ".js", ".html", ".htm", ".xml", ".graphql", ".gql", ".conf",
             ".ini", ".env", ".j2", ".crt", ".pem", ".sql", ".css", ".scss"}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".avif"}

MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".bmp": "image/bmp",
    ".avif": "image/avif",
    ".pdf": "application/pdf",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".har": "application/json",
}


def looks_text(path):
    "Whitelist extension or sniff first 4KB for NUL bytes."
    if os.path.splitext(path)[1].lower() in TEXT_EXTS:
        return True
    try:
        with open(path, "rb") as fh:
            return b"\x00" not in fh.read(4096)
    except Exception:
        return False


def _evidence_root(safe):
    rroot = _resolve_hunt_root(safe)
    ep = os.path.join(rroot, "evidence")
    return ep if os.path.isdir(ep) else ""


def jsq(s):
    "Escape a string for embedding inside a single-quoted JS string literal."
    return str(s).replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")


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
            "findings": v_findings,
            "assets": lambda: v_assets(target) if target else v_assets(""),
            "skills": lambda: v_skills(qs.get("view", ["library"])[0], sel),
            "workspaces": v_workspaces,
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
            hpath = _resolve_hunt_root(safe)
            if os.path.isdir(hpath):
                out = v_hunt(safe)
                if out:
                    return out.encode()
        return v_hunts("").encode()

    if p[0] == "report":
        safe = os.path.basename(os.path.normpath(p[1])) if len(p) > 1 else ""
        fname = os.path.basename(os.path.normpath("/".join(p[2:]))) if len(p) > 2 else ""
        rroot = _resolve_hunt_root(safe)
        rp = os.path.join(rroot, "reports", fname)
        if os.path.isfile(rp):
            mark_report_read(safe, fname)
            packs = []
            evd = os.path.join(rroot, "evidence")
            if os.path.isdir(evd):
                for d in sorted(os.listdir(evd)):
                    dp = os.path.join(evd, d)
                    if os.path.isdir(dp):
                        packs.append({"name": d, "count": count_files(dp), "age": age(dp),
                                      "url": f"/evidence/{safe}/{urllib.parse.quote(d)}",
                                      "nq": jsq(d)})
            packs_json = json.dumps(packs)
            evn = f'<span class="evn">{len(packs)}</span>' if packs else "<span class=\"evn\">0</span>"
            ev_btn = (f'<button class="ev-hero-btn" onclick="openEvidence()">{icon("archive", 15)} Evidence {evn}</button>')

            def _pack_html(grid):
                return "".join(
                    '<div class="ev-pack">'
                    '<button class="ev-open" onclick="%s">'
                    '<span class="pkg">%s</span>'
                    '<span class="meta">%d %s · %s</span></button>'
                    '<a class="ev-pg" href="%s" title="Open full page">↗</a></div>' % (
                        esc("evShowPack('%s',EV_SAFE,'%s')" % (grid, p["nq"])),
                        esc(p["name"]), p["count"],
                        "item" if p["count"] == 1 else "items", esc(p["age"]),
                        esc(p["url"]))
                    for p in packs) or ('<div class="empty" style="padding:24px 0"><div class="t">No evidence packs</div></div>')

            ev_ui = (f'<div class="ev-backdrop" id="evbackdrop" onclick="if(event.target===this)closeEvidence()">'
                     f'<div class="ev-modal"><div class="hd"><span class="ev-title">{icon("archive", 15)} Evidence · {esc(safe)}</span>'
                     f'<button class="btn ghost small" onclick="toPanel()">{icon("columns", 13)} Open as side panel</button>'
                     f'<button class="ev-x" onclick="closeEvidence()">×</button></div>'
                     f'<div class="ev-scroll" id="evgrid">{_pack_html("evgrid")}</div></div></div>'
                     f'<div class="ev-panel" id="evpanel"><div class="hd"><span class="ev-title">{icon("archive", 15)} Evidence · {esc(safe)}</span>'
                     f'<button class="btn ghost small" onclick="toPopup()">{icon("maximize-2", 13)} Open as popup</button>'
                     f'<button class="ev-x" onclick="closePanel()">×</button></div>'
                     f'<div class="ev-scroll" id="evpgrid">{_pack_html("evpgrid")}</div></div>')

            ev_js_tpl = """var EV_SAFE=__SAFE__;
var EV_PACKS=__PACKS__;
var EV_BACK='__ARROW__';
function escapeHtml(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function getEvidenceMode(){var m=document.cookie.match(/(?:^|; )evidence_mode=([^;]+)/);return m?m[1]:'popup';}
function setEvidenceMode(v){document.cookie='evidence_mode='+v+';max-age=31536000;path=/';}
function openEvidence(){var b=document.getElementById('evbackdrop'),p=document.getElementById('evpanel');if(getEvidenceMode()==='panel'){p.classList.add('open');document.getElementById('layout').classList.add('ev-side');}else{b.classList.add('open');}}
function closeEvidence(){closePanel();var b=document.getElementById('evbackdrop');if(b)b.classList.remove('open');}
function closePanel(){var p=document.getElementById('evpanel');if(p)p.classList.remove('open');var l=document.getElementById('layout');if(l)l.classList.remove('ev-side');}
function toPanel(){setEvidenceMode('panel');closeEvidence();openEvidence();}
function toPopup(){setEvidenceMode('popup');closePanel();openEvidence();}
function evShowPacks(id){var el=document.getElementById(id);var h=EV_PACKS.map(function(p){return '<div class="ev-pack"><button class="ev-open" onclick="evShowPack(\\''+id+'\\',EV_SAFE,\\''+p.nq+'\\')"><span class="pkg">'+escapeHtml(p.name)+'</span><span class="meta">'+p.count+' '+(p.count===1?'item':'items')+' · '+escapeHtml(p.age)+'</span></button><a class="ev-pg" href="'+p.url+'" title="Open full page">↗</a></div>';}).join('');el.innerHTML='<div class="ev-subhead"><b>Evidence packs</b><span class="sp"></span><span class="muted small">'+EV_PACKS.length+'</span></div>'+h;}
function evShowPack(id,safe,pack){var el=document.getElementById(id);var pq=pack.replace(/'/g,"\\\\'");el.innerHTML='<div class="ev-load">Loading…</div>';fetch('/api/evpack/'+encodeURIComponent(safe)+'/'+encodeURIComponent(pack)).then(function(r){return r.json();}).then(function(d){if(!d.ok){el.innerHTML='<div class="ev-load">'+escapeHtml(d.reason)+'</div>';return;}var rows=d.files.map(function(f){if(f.bin){return '<div class="ev-file"><span class="nm">'+escapeHtml(f.name)+'</span><span class="sz tag">binary · '+f.hsize+'</span></div>';}var tag=f.img?'<span class="sz tag img">image · '+f.hsize+'</span>':'<span class="sz">'+f.hsize+' · '+escapeHtml(f.age)+'</span>';return '<button class="ev-file" onclick="evShowFile(\\''+id+'\\',\\''+safe+'\\',\\''+pq+'\\',\\''+f.rq+'\\')"><span class="nm">'+escapeHtml(f.name)+'</span>'+tag+'</button>';}).join('');el.innerHTML='<div class="ev-subhead"><button class="btn ghost small" onclick="evShowPacks(\\''+id+'\\')">'+EV_BACK+' All packs</button><b>'+escapeHtml(pack)+'</b></div>'+rows;}).catch(function(){el.innerHTML='<div class="ev-load">Failed to load</div>';});}
function evShowFile(id,safe,pack,rel){var el=document.getElementById(id);var pq=pack.replace(/'/g,"\\\\'");el.innerHTML='<div class="ev-load">Loading…</div>';fetch('/api/evfile/'+encodeURIComponent(safe)+'/'+encodeURIComponent(pack)+'/'+rel.split('/').map(encodeURIComponent).join('/')).then(function(r){return r.json();}).then(function(d){if(!d.ok){el.innerHTML='<div class="ev-load">'+escapeHtml(d.reason)+(d.url?' <a href="'+d.url+'" target="_blank">open raw file ↗</a>':'')+'</div>';return;}var c='';if(d.kind==='image'){c='<div class="ev-img-wrap"><div class="ev-img-bar"><span class="sz tag img">image · '+escapeHtml(d.hsize)+'</span><span class="sp"></span><a class="btn ghost small" href="'+d.url+'" target="_blank">Open original ↗</a></div><div class="ev-img-box"><a href="'+d.url+'" target="_blank" title="Click to open original in new tab"><img class="ev-img" src="'+d.url+'" alt="'+escapeHtml(d.name)+'"></a></div></div>';}else{c=d.kind==='cv'?d.html:(d.kind==='md'?d.html:'<pre class="ev-body">'+escapeHtml(d.text)+'</pre>');}el.innerHTML='<div class="ev-subhead"><button class="btn ghost small" onclick="evShowPack(\\''+id+'\\',\\''+safe+'\\',\\''+pq+'\\')">'+EV_BACK+' '+escapeHtml(pack)+'</button><b>'+escapeHtml(d.name)+'</b></div>'+c;}).catch(function(){el.innerHTML='<div class="ev-load">Failed to load</div>';});}
"""
            ev_js = (ev_js_tpl
                     .replace("__SAFE__", json.dumps(safe))
                     .replace("__PACKS__", packs_json)
                     .replace("__ARROW__", icon("arrow-left", 13)))
            cur = report_mark(safe, fname)
            mbtns = "".join(
                f'<button class="bc-btn mk-{mk}{" active" if mk == cur else ""}" data-mark="{mk}" onclick="reportMark(this)">{esc(MARK_LABELS[mk])}</button>'
                for mk in ("duplicate", "unreportable", "valid", "underreview"))
            marks_bar = (f'<span class="bcsep">{icon("flag", 12)} Mark:</span>{mbtns}'
                         f'<button class="bc-btn bc-clear{" off" if not cur else ""}" onclick="reportClear()"'
                         f'{" disabled" if not cur else ""}>Clear</button>')
            body = (f'<div class="breadcrumb"><span>Hunt / Reports / <b>{esc(fname)}</b></span>'
                    f'<span class="sp"></span>{marks_bar}</div>')
            mkcls = f' mk-bg-{cur}' if cur else ''
            body += (f'<div class="card{mkcls}"><div class="hd">{icon("file-text", 16)} {esc(fname)} <span class="sp"></span>'
                     f'{tts_reader_bar()}'
                     f'<button class="btn ghost small" onclick="copyReportMd()" title="Copy report as markdown">{icon("copy", 13)} Copy MD</button>'
                     f'<a class="btn ghost small" href="/hunts?name={esc(safe)}">{icon("arrow-left", 13)} Hunt</a></div>'
                     f'<div class="bd md tts-root" id="tts-root">{decorate_curls(render_markdown(read_file(rp)))}</div></div>')
            body += ev_ui
            cv_toggle = (
                f'<button class="cv-toggle" id="cv-toggle" onclick="cvToggle()" '
                f'title="Curl verify: toggle curl runner" '
                f'aria-label="Curl verify">{icon("terminal", 20)}</button>'
            )
            cv_js = (
                "function cvCookie(){var m=document.cookie.match(/(?:^|; )curlverify=([^;]+)/);return m?m[1]:'off';}\n"
                "function cvApply(){var on=cvCookie()==='on';document.body.classList.toggle('cv-on',on);var t=document.getElementById('cv-toggle');if(t){t.classList.toggle('on',on);}}\n"
                "function cvToggle(){document.cookie='curlverify='+(cvCookie()==='on'?'off':'on')+';max-age=31536000;path=/';cvApply();}\n"
                "function cvEsc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');}\n"
                "function cvRun(btn){var u=atob(btn.getAttribute('data-curl'));var k=btn.getAttribute('data-k')||'curl';var ep='api/'+(k==='raw'?'rawverify':'curlverify');var wrap=btn.closest('.cv-wrap');var out=wrap.querySelector('.cv-out');\n"
                "btn.disabled=true;btn.classList.add('run');var tri=btn.querySelector('.tri');var old=tri?tri.textContent:'';if(tri){tri.textContent='…';}\n"
                "out.hidden=false;out.innerHTML='<div class=\"cv-st ok\">running…</div>';\n"
                "var bodyObj=(k==='raw')?{raw:u}:{cmd:u};\n"
                "fetch('/'+ep,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bodyObj)})\n"
                ".then(function(r){return r.json().catch(function(){return {ok:false,reason:'bad response'};});})\n"
                ".then(function(d){btn.disabled=false;if(tri){tri.textContent=old;}btn.classList.remove('run');\n"
                "if(!d.ok){btn.classList.add('bad');out.innerHTML='<div class=\"cv-st bad\">'+cvEsc(d.reason||'failed')+'</div>'+((d.out)?'<pre>'+cvEsc(d.out)+'</pre>':'');return;}\n"
                "var head='';if(d.code){head+='HTTP '+cvEsc(d.code)+' · ';}head+=d.ms+'ms · exit '+d.exit;\n"
                "var cls=(d.code && d.code.charAt(0)==='5')?'bad':((d.code && d.code.charAt(0)==='4')?'warn':'ok');\n"
                "btn.classList.add(cls==='bad'?'bad':'ok');\n"
                "out.innerHTML='<div class=\"cv-st '+cls+'\">'+head+'</div><pre>'+cvEsc(d.out)+'</pre>';})\n"
                ".catch(function(e){btn.disabled=false;if(tri){tri.textContent=old;}btn.classList.remove('run');out.hidden=false;out.innerHTML='<div class=\"cv-st bad\">request failed: '+cvEsc(e)+'</div>';});}\n"
                "cvApply();")
            mark_js = (
                "function reportMark(btn){var m=btn.getAttribute('data-mark');\n"
                "apiPost('/api/report/mark',{handle:'" + jsq(safe) + "',name:'" + jsq(fname) + "',mark:m})\n"
                ".then(function(d){if(!d.ok){showMsg(d.message||'Failed to mark report.');return;}location.reload();});}\n"
                "function reportClear(){apiPost('/api/report/mark',{handle:'" + jsq(safe) + "',name:'" + jsq(fname) + "',mark:''})\n"
                ".then(function(d){if(!d.ok){showMsg(d.message||'Failed to clear mark.');return;}location.reload();});}\n"
                "var REPORT_MD=" + json.dumps(read_file(rp)) + ";\n"
                "function copyReportMd(){\n"
                "var done=function(){var b=document.querySelector('.btn[onclick=\"copyReportMd()\"]');if(b){var o=b.innerHTML;b.innerHTML='"+icon("check", 13)+" Copied';setTimeout(function(){b.innerHTML=o;},1500);}};\n"
                "if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(REPORT_MD).then(done,function(){fallbackCopy(REPORT_MD);done();});}\n"
                "else{fallbackCopy(REPORT_MD);done();}\n"
                "}\n"
                "function fallbackCopy(t){var ta=document.createElement('textarea');ta.value=t;ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();try{document.execCommand('copy');}catch(e){}document.body.removeChild(ta);}\n")
            return page("report", hero("Report", f"Staged submission for {esc(fname)}", back=f"/hunts?name={esc(safe)}", crown=ev_btn + cv_toggle),
                        body, extra_css=TTS_CSS, scripts=ev_js + cv_js + mark_js + tts_js()).encode()
        return b"404 report not found"

    if p[0] == "evidence":
        safe = os.path.basename(os.path.normpath(p[1])) if len(p) > 1 else ""
        ep = _evidence_root(safe)
        if not ep or not os.path.isdir(ep):
            return b"404 evidence not found"
        if len(p) >= 3 and p[2]:
            pack = os.path.basename(os.path.normpath(urllib.parse.unquote(p[2])))
            pd = os.path.join(ep, pack)
            if not os.path.isdir(pd):
                return b"404 evidence pack not found"
            files_html = []
            for root, _dirs, fns in os.walk(pd):
                for fn in sorted(fns):
                    fp = os.path.join(root, fn)
                    rp = os.path.relpath(fp, pd)
                    sz = os.path.getsize(fp)
                    ext = os.path.splitext(rp)[1].lower()
                    raw_url = f"/api/evraw/{urllib.parse.quote(safe)}/{urllib.parse.quote(pack)}/{'/'.join(urllib.parse.quote(x) for x in rp.split(os.sep))}"
                    if ext in IMAGE_EXTS:
                        files_html.append(
                            f'<div class="card" style="margin-bottom:14px"><div class="hd">{icon("eye", 15)} {esc(rp)} '
                            f'<span class="sp"></span><span class="sz tag img">image · {fmt_size(sz)}</span> '
                            f'<a class="btn ghost small" href="{raw_url}" target="_blank">Open original ↗</a></div>'
                            f'<div class="bd" style="text-align:center;background:#181b22;padding:14px;border-radius:0 0 10px 10px">'
                            f'<a href="{raw_url}" target="_blank"><img class="ev-img" src="{raw_url}" alt="{esc(rp)}" style="display:inline-block"></a>'
                            f'</div></div>'
                        )
                    elif looks_text(fp):
                        content = read_file(fp)
                        if len(content) > 100000:
                            content = content[:100000] + "\n…(truncated)…"
                        rendered = render_markdown(content) if ext in (".md", ".markdown") else f'<pre class="ev-body">{esc(content)}</pre>'
                        files_html.append(
                            f'<div class="card" style="margin-bottom:14px"><div class="hd">{icon("file-text", 15)} {esc(rp)} '
                            f'<span class="sp"></span><span class="sz tag">{fmt_size(sz)}</span> '
                            f'<a class="btn ghost small" href="{raw_url}" target="_blank">Raw ↗</a></div>'
                            f'<div class="bd">{rendered}</div></div>'
                        )
                    else:
                        files_html.append(
                            f'<div class="card" style="margin-bottom:14px"><div class="hd">{icon("archive", 15)} {esc(rp)} '
                            f'<span class="sp"></span><span class="sz tag">binary · {fmt_size(sz)}</span> '
                            f'<a class="btn ghost small" href="{raw_url}" target="_blank">Raw ↗</a></div></div>'
                        )
            body = (f'<div class="breadcrumb"><span>Hunt / <a href="/evidence/{esc(safe)}">Evidence</a> / <b>{esc(pack)}</b></span></div>'
                    f'<div class="card" style="margin-bottom:14px"><div class="hd">Pack: {esc(pack)} <span class="sp"></span>'
                    f'<a class="btn ghost small" href="/evidence/{esc(safe)}">{icon("arrow-left", 13)} All packs</a></div></div>'
                    + "".join(files_html))
            return page("report", hero("Evidence", f"Pack {esc(pack)} for {esc(safe)}", back=f"/evidence/{esc(safe)}"), body).encode()

        rows = ""
        for f in sorted(os.listdir(ep)):
            fp = os.path.join(ep, f)
            pack_url = f"/evidence/{safe}/{urllib.parse.quote(f)}"
            rows += f'<tr><td>{icon("archive", 16)}</td><td class="mono"><a href="{pack_url}">{esc(f)}</a></td><td class="num">{count_files(fp) if os.path.isdir(fp) else 1}</td><td>{age(fp)}</td></tr>'
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
        if p[1] == "evpack" and len(p) >= 4:
            safe = os.path.basename(os.path.normpath(urllib.parse.unquote(p[2])))
            pack = os.path.basename(os.path.normpath(urllib.parse.unquote(p[3])))
            ep = _evidence_root(safe)
            pd = os.path.join(ep, pack) if ep else ""
            if ep and os.path.isdir(pd):
                out = []
                for root, _dirs, fns in os.walk(pd):
                    for fn in sorted(fns):
                        fp = os.path.join(root, fn)
                        rp = os.path.relpath(fp, pd)
                        sz = os.path.getsize(fp)
                        ext = os.path.splitext(rp)[1].lower()
                        is_img = ext in IMAGE_EXTS
                        is_txt = looks_text(fp)
                        out.append({
                            "name": rp,
                            "rel": rp,
                            "rq": rp.replace("'", "\\'"),
                            "size": sz,
                            "hsize": fmt_size(sz),
                            "age": age(fp),
                            "img": is_img,
                            "bin": not (is_img or is_txt),
                        })
                out.sort(key=lambda f: f["name"].lower())
                return json.dumps({"ok": True, "pack": pack, "files": out}).encode()
            return json.dumps({"ok": False, "reason": "evidence pack not found"}).encode()
        if p[1] == "evfile" and len(p) >= 4:
            safe = os.path.basename(os.path.normpath(urllib.parse.unquote(p[2])))
            pack = os.path.basename(os.path.normpath(urllib.parse.unquote(p[3])))
            relparts = [urllib.parse.unquote(x) for x in p[4:]]
            ep = _evidence_root(safe)
            pd = os.path.realpath(os.path.join(ep, pack)) if ep else ""
            if not ep or not os.path.isdir(pd):
                return json.dumps({"ok": False, "reason": "evidence pack not found"}).encode()
            rp = os.path.realpath(os.path.join(pd, *relparts)) if relparts else ""
            if not rp.startswith(pd + os.sep) or not os.path.isfile(rp):
                return json.dumps({"ok": False, "reason": "file not found"}).encode()
            ext = os.path.splitext(rp)[1].lower()
            raw_url = f"/api/evraw/{urllib.parse.quote(safe)}/{urllib.parse.quote(pack)}/{'/'.join(urllib.parse.quote(x) for x in relparts)}"
            if ext in IMAGE_EXTS:
                return json.dumps({
                    "ok": True,
                    "kind": "image",
                    "name": os.path.basename(rp),
                    "url": raw_url,
                    "hsize": fmt_size(os.path.getsize(rp)),
                    "ext": ext.lstrip("."),
                }).encode()
            if not looks_text(rp):
                return json.dumps({"ok": False, "reason": "binary file", "url": raw_url}).encode()
            data = read_file(rp)
            short = ""
            if len(data) > 524288:
                data = data[:524288]
                short = "…(truncated at 512 KB)…"
            if ext in (".md", ".markdown"):
                return json.dumps({"ok": True, "kind": "md", "name": os.path.basename(rp),
                                   "html": '<div class="md">' + decorate_curls(render_markdown(data + short)) + '</div>'}).encode()
            plain = '<pre class="ev-body">' + html.escape(data + short) + "</pre>"
            decorated = decorate_curls(plain)
            kind = "cv" if decorated != plain else "text"
            return json.dumps({"ok": True, "kind": kind, "name": os.path.basename(rp),
                               "html": decorated if kind == "cv" else None,
                               "text": data + short if kind == "text" else None}).encode()
        if p[1] == "evraw" and len(p) >= 4:
            safe = os.path.basename(os.path.normpath(urllib.parse.unquote(p[2])))
            pack = os.path.basename(os.path.normpath(urllib.parse.unquote(p[3])))
            relparts = [urllib.parse.unquote(x) for x in p[4:]]
            ep = _evidence_root(safe)
            pd = os.path.realpath(os.path.join(ep, pack)) if ep else ""
            if not ep or not os.path.isdir(pd):
                return b"404 evidence pack not found", 404, "text/plain"
            rp = os.path.realpath(os.path.join(pd, *relparts)) if relparts else ""
            if not rp.startswith(pd + os.sep) or not os.path.isfile(rp):
                return b"404 file not found", 404, "text/plain"
            ext = os.path.splitext(rp)[1].lower()
            ctype = MIME_TYPES.get(ext, "application/octet-stream")
            try:
                with open(rp, "rb") as fh:
                    raw_data = fh.read()
                return raw_data, 200, ctype
            except Exception as e:
                return f"500 read error: {e}".encode(), 500, "text/plain"
        if p[1] == "tts":
            # Server-side TTS fallback: synthesize text to WAV via espeak-ng.
            # Used when the browser has no speechSynthesis voices (e.g. Chrome
            # on Linux without speech-dispatcher reachable). Cached by hash.
            if qs.get("probe", [""])[0]:
                # availability probe → {ok: bool}
                try:
                    r = subprocess.run(["espeak-ng", "--version"],
                                       capture_output=True, timeout=5)
                    ok = r.returncode == 0
                except Exception:
                    ok = False
                return json.dumps({"ok": ok}).encode()
            text = qs.get("text", [""])[0]
            if not text or len(text) > 4000:
                return b"400 bad request", 400, "text/plain"
            cache_dir = "/tmp/hackbot-tts"
            os.makedirs(cache_dir, exist_ok=True)
            h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
            wav = os.path.join(cache_dir, h + ".wav")
            if not os.path.isfile(wav):
                txt = os.path.join(cache_dir, h + ".txt")
                with open(txt, "w", encoding="utf-8") as fh:
                    fh.write(text)
                try:
                    r = subprocess.run(
                        ["espeak-ng", "-w", wav, "-f", txt],
                        capture_output=True, timeout=30,
                    )
                except Exception as e:
                    return f"500 tts error: {e}".encode(), 500, "text/plain"
                if r.returncode != 0 or not os.path.isfile(wav):
                    return b"500 tts synthesis failed", 500, "text/plain"
            try:
                with open(wav, "rb") as fh:
                    data = fh.read()
                return data, 200, "audio/wav"
            except Exception as e:
                return f"500 read error: {e}".encode(), 500, "text/plain"
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
        if p[1] == "console" and len(p) >= 3 and p[2] == "save":
            l = qs.get("l", [""])[0]
            w = qs.get("w", [""])[0]
            d = qs.get("d", [""])[0]
            sel = _resolve_log(l, w, d)
            if not sel or not os.path.isfile(sel):
                return b"404 no log", 404, "text/plain"
            try:
                with open(sel, "rb") as fh:
                    data = fh.read()
                fname = os.path.basename(sel)
                return data, 200, "application/octet-stream", {"Content-Disposition": f'attachment; filename="{fname}"'}
            except Exception as e:
                return f"500 read error: {e}".encode(), 500, "text/plain"
        if p[1] == "console":
            w = qs.get("w", [""])[0]
            l = qs.get("l", [""])[0]
            d = qs.get("d", [""])[0]
            lines = int((qs.get("lines", ["300"])[0] or "300") or 300)
            sel = _resolve_log(l, w, d)
            payload = {
                "mtime": mtime(sel) if sel else 0,
                "html": _strip_emoji(render_log_html("\n".join(read_tail(sel, lines)))) if sel else "(no logs yet)",
            }
            # Activity detection
            akind, alabel = _detect_activity(sel)
            if akind:
                color_map = {
                    "thinking": "var(--accent)",
                    "working": "#22c55e",
                    "writing": "#f59e0b",
                    "reading": "#8b5cf6",
                    "searching": "#06b6d4",
                    "requesting": "#f97316",
                    "error": "#ef4444",
                }
                payload["activity"] = akind
                payload["activity_label"] = alabel
                payload["activity_color"] = color_map.get(akind, "var(--muted)")
                payload["activity_html"] = f'{icon("radio", 10)} {esc(alabel)}'
            return json.dumps(payload).encode()

        if p[1] == "stats":
            return json.dumps(api_stats(), default=str).encode()
        if p[1] == "usage":
            return json.dumps(api_usage(qs.get("range", [""])[0] or "all"), default=str).encode()
        return b"{}"

    return b"404"

def route_post(path, qs, body):
    parts = path.split("?")[0].rstrip("/").split("/")
    p = [x for x in parts if x]

    if p[:3] == ["api", "targets", "add"]:
        payload, status = _api_add_target(body)
        return json.dumps(payload).encode(), status
    if p[:3] == ["api", "targets", "start"]:
        payload, status = _api_start_target(body)
        return json.dumps(payload).encode(), status
    if p[:3] == ["api", "targets", "stop"]:
        payload, status = _api_stop_target(body)
        return json.dumps(payload).encode(), status

    if p[:3] == ["api", "console", "tell"]:
        payload, status = _api_console_tell(body)
        return json.dumps(payload).encode(), status

    if p[:3] == ["api", "findings", "add"]:
        payload, status = _api_findings_add(body)
        return json.dumps(payload).encode(), status
    if p[:3] == ["api", "findings", "update"]:
        payload, status = _api_findings_update(body)
        return json.dumps(payload).encode(), status

    if p[:3] == ["api", "queue", "bulk"]:
        payload, status = _api_queue_bulk(body)
        return json.dumps(payload).encode(), status

    if p[:3] == ["api", "skills", "new"]:
        payload, status = _api_skills_new(body)
        return json.dumps(payload).encode(), status
    if p[:3] == ["api", "skills", "import"]:
        payload, status = _api_skills_import(body)
        return json.dumps(payload).encode(), status

    if p[:3] == ["api", "report", "mark"]:
        payload, status = _api_report_mark(body)
        return json.dumps(payload).encode(), status

    if p[:3] == ["api", "telegram", "test"]:
        payload, status = _api_telegram_test(body)
        return json.dumps(payload).encode(), status
    if p[:3] == ["api", "provider", "test"]:
        payload, status = _api_provider_test(body)
        return json.dumps(payload).encode(), status
    if p[:3] == ["api", "mailbox", "test"]:
        payload, status = _api_mailbox_test(body)
        return json.dumps(payload).encode(), status
    if p[:3] == ["api", "config", "update"]:
        payload, status = _api_config_update(body)
        return json.dumps(payload).encode(), status
    if p[:3] == ["api", "pool", "action"]:
        payload, status = _api_pool_action(body)
        return json.dumps(payload).encode(), status

    if p[:2] == ["api", "curlverify"]:
        payload, status = _api_curlverify(body)
        return json.dumps(payload).encode(), status
    if p[:2] == ["api", "rawverify"]:
        payload, status = _api_rawverify(body)
        return json.dumps(payload).encode(), status

    return json.dumps({"ok": False, "message": "not found"}).encode(), 404


def api_stats():
    queue = get_queue()
    workers = get_workers()
    findings = get_findings()
    hs = hunt_stats()
    confirmed = sum(1 for f in findings if str(f.get("status", "")).lower() in ("confirmed", "paid"))
    active_w = [w for w in workers if str(w.get("status", "")).lower() == "running"]
    pending = [t for t in queue if str(t.get("status", "")).lower() in ("pending", "sleeping")]
    return {
        "ok": True,
        "findings": hs["reports"],
        "confirmed": confirmed,
        "workers_running": len(active_w),
        "workers_total": max(len(workers), 1),
        "queue_pending": len(pending),
        "queue_total": max(len(queue), 1),
        "hunts_run": hs["hunts"],
        "runs": hs["runs"],
        "sessions": hs["sessions"],
        "attention": need_attention(),
    }


def _window_start(range_val, now):
    win = {"24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400}.get(range_val)
    return (now - win) if win else 0


def _api_curlverify(body):
    import tempfile
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "reason": "invalid JSON"}, 400
    cmd = str(data.get("cmd") or "").strip()
    if not cmd:
        return {"ok": False, "reason": "no command"}, 400
    if len(cmd) > 4000:
        return {"ok": False, "reason": "command too long"}, 400
    if not re.match(r"^\s*(?:\$\s*)?curl\b", cmd):
        return {"ok": False, "reason": "not a curl command"}, 400
    if re.search(r"[\x00;`$({]|&&|\|\|", cmd):
        return {"ok": False, "reason": "shell metacharacters not allowed"}, 400
    normalized = re.sub(r"^\s*(?:\$\s*)?", "", cmd)
    normalized = re.sub(r"\\\n\s*", " ", normalized)
    normalized = re.sub(r"\bcurl\b", "curl -sS --max-time 9", normalized, count=1)
    if "|" not in normalized and not re.search(r"(^|[\s])-[-]?w([\s]|$)", normalized):
        normalized += ' -w "\n__CV_HTTP__:%{http_code}"'
    t0 = time.time()
    td = tempfile.mkdtemp(prefix="cvverify-")
    try:
        try:
            p = subprocess.run(
                ["bash", "-c", normalized],
                capture_output=True, timeout=12, cwd=td,
            )
            ms = int((time.time() - t0) * 1000)
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "timed out after 12s"}, 200
        out = (p.stdout or b"").decode("utf-8", "replace")
        err = (p.stderr or b"").decode("utf-8", "replace")
        if err:
            out = (out + "\n" + err) if out else err
        code = None
        m = re.search(r"__CV_HTTP__:(\d+)", out)
        if m:
            code = m.group(1)
            out = out[: m.start()]
        if len(out) > 8000:
            out = out[:8000] + "\n…(truncated)"
        return {"ok": True, "exit": p.returncode, "code": code, "ms": ms, "out": out}, 200
    finally:
        shutil.rmtree(td, ignore_errors=True)


def _api_rawverify(body):
    import http.client
    from urllib.parse import urlparse
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "reason": "invalid JSON"}, 400
    raw = str(data.get("raw") or "").strip()
    if not raw:
        return {"ok": False, "reason": "no request"}, 400
    if len(raw) > 20000:
        return {"ok": False, "reason": "request too long"}, 400
    norm = raw.replace("\r\n", "\n")
    head, _bsep, body_text = norm.partition("\n\n")
    lines = head.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return {"ok": False, "reason": "empty request"}, 400
    m = re.match(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE|CONNECT)\s+(\S+)\s+HTTP/\d(?:\.\d)?$",
                 lines[0].strip(), re.I)
    if not m:
        return {"ok": False, "reason": "not an HTTP request line"}, 400
    method, target = m.group(1).upper(), m.group(2)
    headers = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            k, v = k.strip(), v.strip()
            if k.lower() not in ("content-length", "transfer-encoding", "proxy-connection"):
                headers.setdefault(k, v)
    host = None
    scheme = "https"
    port = None
    path = target
    pu = urlparse(target)
    if pu.scheme in ("http", "https"):
        scheme = pu.scheme
        host = pu.netloc
        path = (pu.path or "/") + (("?" + pu.query) if pu.query else "")
    else:
        for k, v in headers.items():
            if k.lower() == "host":
                host = v
                break
    if not host:
        return {"ok": False, "reason": "no Host header or absolute URL"}, 400
    hostname = host
    if ":" in host and not host.startswith("["):
        cand = host.rsplit(":", 1)
        if cand[1].isdigit():
            hostname, port = cand[0], int(cand[1])
    if port is None:
        port = 80 if scheme == "http" else 443
    loopback = re.match(r"^(127\.|0\.0\.0\.0|localhost|::1$|\[::1\]$)", hostname)
    if scheme == "https" and not target.startswith("https://") and (
            port in (80, 8080, 8081, 3128, 8888) or loopback):
        scheme = "http" if port != 443 else "https"
    t0 = time.time()
    try:
        cls = http.client.HTTPConnection if scheme == "http" else http.client.HTTPSConnection
        conn = cls(hostname, port, timeout=9)
        bb = body_text.encode("utf-8", "replace") if body_text else None
        conn.request(method, path, body=bb, headers=headers)
        r = conn.getresponse()
        data = r.read(20000)
        ms = int((time.time() - t0) * 1000)
        resp_headers = "\n".join(f"{k}: {v}" for k, v in r.getheaders()[:16])
        txt = (data or b"").decode("utf-8", "replace")
        out = f"{method} {path} → HTTP {r.status} {r.reason}\n{resp_headers}\n\n{txt}"
        if len(out) > 8000:
            out = out[:8000] + "\n…(truncated)"
        return {"ok": True, "exit": 0, "code": str(r.status), "ms": ms, "out": out}, 200
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {e}",
                "ms": int((time.time() - t0) * 1000)}, 200


def api_usage(range_val):
    now = time.time()
    ws = _window_start(range_val, now)
    queue = get_queue()
    workers = get_workers()
    findings = [f for f in get_findings() if not ws or (float(f.get("ts") or 0) >= ws)]
    sess = [s for s in get_session_dirs() if not ws or float(s.get("mtime") or 0) >= ws]
    runs = [r for r in get_run_dirs() if not ws or float(r.get("mtime") or 0) >= ws]
    hunted = sum(1 for t in queue if t.get("bugs_found", 0) > 0 or t.get("status") == "active")
    total = max(len(queue), 1)
    return {
        "ok": True,
        "range": range_val,
        "hunts_run": len(runs),
        "sessions": len(sess),
        "findings": len(findings),
        "queue_total": total,
        "queue_active": sum(1 for t in queue if t.get("status") == "active"),
        "hunted": hunted,
        "pending": total - hunted,
        "percent": int(hunted / total * 100),
    }

