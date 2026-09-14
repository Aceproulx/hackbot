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
from .actions import _api_skills_import
from .actions import _api_skills_new
from .actions import _api_telegram_test
from .console import _console_for
from .console import _resolve_log
from .util import age
from .ansi import ansi_to_html
from .util import count_files
from .util import esc
from .state import get_findings
from .state import get_pool
from .state import get_queue
from .state import get_run_dirs
from .state import get_session_dirs
from .state import get_workers
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
from .views import v_desktops
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

    return json.dumps({"ok": False, "message": "not found"}).encode(), 404


def api_stats():
    queue = get_queue()
    workers = get_workers()
    findings = get_findings()
    runs = get_run_dirs()
    sess = get_session_dirs()
    confirmed = sum(1 for f in findings if str(f.get("status", "")).lower() == "confirmed")
    est = sum(float(f.get("bounty_est") or 0) for f in findings)
    paid = sum(float(f.get("bounty_paid") or 0) for f in findings if f.get("bounty_paid"))
    active_w = [w for w in workers if str(w.get("status", "")).lower() == "running"]
    pending = [t for t in queue if str(t.get("status", "")).lower() in ("pending", "sleeping")]
    return {
        "ok": True,
        "findings": len(findings),
        "confirmed": confirmed,
        "est_bounty": est,
        "paid_bounty": paid,
        "workers_running": len(active_w),
        "workers_total": max(len(workers), 1),
        "queue_pending": len(pending),
        "queue_total": max(len(queue), 1),
        "hunts_run": len(runs),
        "sessions": len(sess),
        "attention": need_attention(),
    }


def _window_start(range_val, now):
    win = {"24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400}.get(range_val)
    return (now - win) if win else 0


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
    est = sum(float(f.get("bounty_est") or 0) for f in findings)
    paid = sum(float(f.get("bounty_paid") or 0) for f in findings if f.get("bounty_paid"))
    return {
        "ok": True,
        "range": range_val,
        "hunts_run": len(runs),
        "sessions": len(sess),
        "findings": len(findings),
        "queue_total": total,
        "queue_active": sum(1 for t in queue if t.get("status") == "active"),
        "est_bounty": est,
        "paid_bounty": paid,
        "hunted": hunted,
        "pending": total - hunted,
        "percent": int(hunted / total * 100),
    }

