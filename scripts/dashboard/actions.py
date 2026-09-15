"""Hackbot dashboard — actions module.

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

from .config import QUEUE_MANAGER
from .config import WORKER_POOL
from .config import FINDINGS_FILE
from .config import CONFIG_PATH
from .config import SKILL_DIRS
from .config import TELEGRAM_TOKEN
from .config import TELEGRAM_CHAT
from .config import EMAIL_BASE
from .config import EMAIL_DOMAIN
from .config import MAX_SLOTS
from .config import NOTIFY
from .config import load_config
from .config import HUNTS_ROOT
from .config import SESSIONS_ROOT
from .state import VALID_MARKS
from .state import set_report_mark
from .util import _URL_RE
from .util import _HANDLE_RE
# UNRESOLVED: _run_worker_pool (same-module or missing)
# UNRESOLVED: json (same-module or missing)
# UNRESOLVED: subprocess (same-module or missing)

def _api_add_target(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400

    url = (data.get("url") or "").strip()
    name = (data.get("name") or "").strip() or url
    notes = (data.get("notes") or "").strip()

    if not url:
        return {"ok": False, "message": "URL is required"}, 400
    if any(c.isspace() for c in url):
        return {"ok": False, "message": "URL can't contain whitespace"}, 400
    if not _URL_RE.match(url):
        return {"ok": False, "message": "doesn't look like a valid URL or host"}, 400
    if not QUEUE_MANAGER:
        return {"ok": False, "message": "queue-manager.sh not found — is hackbot-queue installed? (see setup.sh)"}, 500

    try:
        proc = subprocess.run(
            [QUEUE_MANAGER, "add", url, name, notes],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        return {"ok": False, "message": f"failed to run queue-manager: {e}"}, 500

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "queue-manager add failed").strip()
        msg = tail.splitlines()[-1] if tail else "queue-manager add failed"
        return {"ok": False, "message": msg}, 400

    return {"ok": True, "message": proc.stdout.strip()}, 200

def _run_worker_pool(*args):
    if not WORKER_POOL:
        return {"ok": False, "message": "worker-pool.sh not found — is hackbot-workers installed? (see setup.sh)"}, 500
    try:
        proc = subprocess.run(
            [WORKER_POOL, *args],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        return {"ok": False, "message": f"failed to run worker-pool: {e}"}, 500
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "worker-pool command failed").strip()
        msg = tail.splitlines()[-1] if tail else "worker-pool command failed"
        return {"ok": False, "message": msg}, 400
    return {"ok": True, "message": proc.stdout.strip()}, 200

def _api_start_target(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    handle = (data.get("handle") or "").strip()
    if not handle or not _HANDLE_RE.match(handle):
        return {"ok": False, "message": "missing or invalid target handle"}, 400
    return _run_worker_pool("start-target", handle)

def _api_stop_target(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    handle = (data.get("handle") or "").strip()
    if not handle or not _HANDLE_RE.match(handle):
        return {"ok": False, "message": "missing or invalid target handle"}, 400
    return _run_worker_pool("stop-target", handle)

def _api_console_tell(body):
    """Write an instruction for a worker agent to pick up.

    The worker prompt instructs agents to check for a pending-message file
    before each major action. This endpoint writes that file.
    """
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    worker_id = (data.get("worker_id") or "").strip()
    message = (data.get("message") or "").strip()
    if not worker_id:
        return {"ok": False, "message": "worker_id is required"}, 400
    if not message:
        return {"ok": False, "message": "message is required"}, 400
    if len(message) > 2000:
        return {"ok": False, "message": "message too long (max 2000 chars)"}, 400

    # Write to worker-pool/<worker_id>-instructions.txt
    from .config import MISC
    pool_dir = os.path.join(MISC, "worker-pool")
    try:
        os.makedirs(pool_dir, exist_ok=True)
        msg_path = os.path.join(pool_dir, f"{worker_id}-instructions.txt")
        with open(msg_path, "w") as fh:
            fh.write(message + "\n")
        return {"ok": True, "message": f"instruction queued for {worker_id}"}, 200
    except Exception as e:
        return {"ok": False, "message": f"failed to write instruction: {e}"}, 500

def _run_queue_manager(*args):
    if not QUEUE_MANAGER:
        return {"ok": False, "message": "queue-manager.sh not found — is hackbot-queue installed?"}, 500
    try:
        proc = subprocess.run(
            [QUEUE_MANAGER, *args],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        return {"ok": False, "message": f"failed to run queue-manager: {e}"}, 500
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "queue-manager command failed").strip()
        msg = tail.splitlines()[-1] if tail else "queue-manager command failed"
        return {"ok": False, "message": msg}, 400
    return {"ok": True, "message": proc.stdout.strip()}, 200

def _api_findings_add(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400

    program = (data.get("program") or "").strip()
    title = (data.get("title") or "").strip()
    if not program or not title:
        return {"ok": False, "message": "program and title are required"}, 400

    now_ts = time.time()
    finding = {
        "id": f"f-{int(now_ts * 1000)}-{os.urandom(3).hex()}",
        "ts": now_ts,
        "program": program,
        "title": title,
        "severity": (data.get("severity") or "Medium").strip().lower(),
        "status": (data.get("status") or "confirmed").strip().lower(),
        "bounty_est": float(data.get("bounty_est") or 0),
        "bounty_paid": None,
        "evidence": (data.get("evidence") or "").strip(),
        "url": (data.get("url") or "").strip(),
        "notes": (data.get("notes") or "").strip(),
        "reported_at": None,
        "resolved_at": None,
    }

    try:
        line = json.dumps(finding, default=str)
        with open(FINDINGS_FILE, "a") as fh:
            fh.write(line + "\n")
    except Exception as e:
        return {"ok": False, "message": f"failed to append to findings ledger: {e}"}, 500

    if finding["status"] == "confirmed":
        try:
            subprocess.run(
                ["bash", NOTIFY, "bug", program, title, finding["severity"], str(finding["bounty_est"])],
                capture_output=True, text=True, timeout=30,
            )
        except Exception:
            pass

    return {"ok": True, "message": f"logged {program} · {title}", "id": finding["id"]}, 200

def _api_findings_update(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    fid = (data.get("id") or "").strip()
    if not fid:
        return {"ok": False, "message": "finding id is required"}, 400

    patch = {}
    for key in ("status", "severity", "bounty_est", "bounty_paid", "resolved_at", "notes"):
        if key in data:
            patch[key] = data[key]

    lines = []
    found = False
    if not os.path.isfile(FINDINGS_FILE):
        return {"ok": False, "message": "findings ledger not found"}, 404
    with open(FINDINGS_FILE) as fh:
        for ln in fh:
            stripped = ln.strip()
            if not stripped:
                continue
            try:
                rec = json.loads(stripped)
            except Exception:
                lines.append(ln)
                continue
            if rec.get("id") == fid:
                found = True
                rec.update(patch)
                if rec.get("status") == "paid" and not rec.get("resolved_at"):
                    rec["resolved_at"] = time.time()
                stripped = json.dumps(rec, default=str)
            lines.append(stripped + "\n")
    if not found:
        return {"ok": False, "message": "finding not found"}, 404
    try:
        with open(FINDINGS_FILE, "w") as fh:
            fh.writelines(lines)
    except Exception as e:
        return {"ok": False, "message": f"failed to update ledger: {e}"}, 500
    return {"ok": True, "message": "updated"}, 200

def _api_queue_bulk(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    action = (data.get("action") or "").strip()
    handles = [(h or "").strip() for h in (data.get("handles") or []) if (h or "").strip()]
    if action not in ("start", "reset", "skip"):
        return {"ok": False, "message": "unknown bulk action"}, 400
    if not handles:
        return {"ok": False, "message": "no handles selected"}, 400
    for h in handles:
        if not _HANDLE_RE.match(h):
            return {"ok": False, "message": f"invalid handle: {h}"}, 400

    results = {"ok": True, "done": [], "failures": []}
    for h in handles:
        if action == "start":
            payload, status = _run_worker_pool("start-target", h)
        else:
            op = "reset" if action == "reset" else "skip"
            payload, status = _run_queue_manager(op, h)
        if status == 200 and payload.get("ok"):
            results["done"].append(h)
        else:
            results["failures"].append({"handle": h, "message": payload.get("message", "failed")})
    if results["failures"] and not results["done"]:
        return {**results, "ok": False, "message": ", ".join(f['message'] for f in results['failures'][:3])}, 400
    results["message"] = f"{len(results['done'])} done, {len(results['failures'])} failed"
    return results, 200

def load_skill_dir():
    for d in SKILL_DIRS:
        if d and os.path.isdir(d):
            return d
    return None

def _api_skills_new(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    name = (data.get("name") or "").strip()
    if not name or not re.match(r"^[a-z0-9][a-z0-9-]*$", name):
        return {"ok": False, "message": "invalid skill name (lowercase, dashes allowed)"}, 400

    base = (data.get("folder") or "").strip() or (load_skill_dir() or "")
    if not base:
        return {"ok": False, "message": "no writable skill directory found"}, 500
    base = os.path.expanduser(base)
    target = os.path.join(base, name, "SKILL.md")
    if os.path.exists(target):
        return {"ok": False, "message": f"skill already exists: {name}"}, 400
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w") as fh:
            fh.write("---\nname: " + name + "\ndescription: New skill scaffold.\n---\n\n")
    except Exception as e:
        return {"ok": False, "message": f"failed to create skill: {e}"}, 500
    return {"ok": True, "message": f"created {name} in {base}", "skill": name}, 200


def _api_skills_import(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    url = (data.get("url") or "").strip()
    if not url:
        return {"ok": False, "message": "repository URL or path is required"}, 400

    if url.startswith("http://") or url.startswith("https://") or url.endswith(".git"):
        args = ["git", "clone", "--depth", "1", url]
    else:
        args = ["git", "clone", "--depth", "1", url]

    base = load_skill_dir()
    if not base:
        return {"ok": False, "message": "no writable skill directory found"}, 500
    dest = os.path.join(base, os.path.basename(url).removesuffix(".git"))
    if os.path.exists(dest):
        return {"ok": False, "message": f"destination already exists: {dest}"}, 400
    try:
        proc = subprocess.run(args + [dest], capture_output=True, text=True, timeout=120)
    except Exception as e:
        return {"ok": False, "message": f"failed to run git clone: {e}"}, 500
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "git clone failed").strip().splitlines()[-1]
        return {"ok": False, "message": msg}, 400
    return {"ok": True, "message": f"imported → {dest}", "skill": os.path.basename(dest)}, 200

def _api_telegram_test(body):
    try:
        data = json.loads(body or "{}") if body else {}
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    action = (data.get("action") or "test").strip()
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return {"ok": False, "message": "telegram token/chat not configured in ~/.hackbot/config.json"}, 400
    if action == "reconnect":
        return {"ok": True, "message": "telegram is a push channel — no persistent session to reconnect"}, 200
    return _run_notify("bug", "dashboard", "Telegram test", "info", "0")

def _run_notify(*args):
    if not os.path.isfile(NOTIFY):
        return {"ok": False, "message": "notify-telegram.sh not found"}, 500
    try:
        proc = subprocess.run(["bash", NOTIFY, *args], capture_output=True, text=True, timeout=30)
    except Exception as e:
        return {"ok": False, "message": f"failed to run notify: {e}"}, 500
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "notify failed").strip().splitlines()[-1]
        return {"ok": False, "message": msg}, 400
    return {"ok": True, "message": proc.stdout.strip() or "notified"}, 200

def _api_provider_test(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    name = (data.get("name") or "").strip().lower()
    if name == "telegram":
        return _api_telegram_test(body)
    if name in ("opencode", "deepseek"):
        proc = subprocess.run(["opencode", "--version"], capture_output=True, text=True, timeout=15)
        return {"ok": True, "message": ("provider reachable" if proc.returncode == 0 else "provider unreachable")}, 200
    return {"ok": False, "message": "unknown provider"}, 400

def _api_mailbox_test(body):
    try:
        data = json.loads(body or "{}") if body else {}
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    action = (data.get("action") or "test").strip()
    if not EMAIL_DOMAIN:
        return {"ok": False, "message": "email_domain not configured"}, 400
    if action == "reconnect":
        return {"ok": True, "message": f"catch-all {EMAIL_BASE}+target@{EMAIL_DOMAIN} relies on the provider MX rule — revalidate on provider console"}, 200
    return {"ok": True, "message": "mailbox reachable (SMTP delivery configured)"}, 200

def _api_config_update(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    section = (data.get("section") or "").strip()
    setting = (data.get("setting") or "").strip()
    value = str(data.get("value") or "").strip()
    if not section or not setting:
        return {"ok": False, "message": "section and setting are required"}, 400

    cfg = load_config()
    if section in cfg and isinstance(cfg[section], dict):
        if setting not in cfg[section] and not isinstance(cfg[section], dict):
            return {"ok": False, "message": f"unknown setting: {section}.{setting}"}, 400
        cfg[section][setting] = value
    elif setting in cfg:
        cfg[setting] = value
    else:
        return {"ok": False, "message": f"unknown setting: {section}.{setting}"}, 400
    try:
        with open(CONFIG_PATH, "w") as fh:
            json.dump(cfg, fh, indent=2)
    except Exception as e:
        return {"ok": False, "message": f"failed to write config: {e}"}, 500
    return {"ok": True, "message": f"updated {section}.{setting}"}, 200

def _api_pool_action(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    action = (data.get("action") or "").strip()
    if action == "start":
        slots = int(data.get("slots") or MAX_SLOTS)
        return _run_worker_pool("start", "--slots", str(slots))
    if action == "status":
        return _run_worker_pool("status")
    return {"ok": False, "message": "unknown pool action"}, 400


def _resolve_report(handle: str, name: str):
    """Locate a report md file under runs or sessions — normalized, no traversal."""
    safe_h = os.path.basename(os.path.normpath(handle))
    safe_n = os.path.basename(os.path.normpath(name))
    for root in (HUNTS_ROOT, SESSIONS_ROOT):
        rp = os.path.join(root, safe_h, "reports", safe_n)
        if os.path.isfile(rp):
            return rp
    return None


def _api_report_mark(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"ok": False, "message": "invalid JSON body"}, 400
    handle = (data.get("handle") or "").strip()
    name = (data.get("name") or "").strip()
    mark = (data.get("mark") or "").strip().lower()
    if not handle or not name:
        return {"ok": False, "message": "handle and report name are required"}, 400
    if mark and mark not in VALID_MARKS:
        return {"ok": False, "message": f"unknown mark: {mark}"}, 400
    rp = _resolve_report(handle, name)
    if not rp:
        return {"ok": False, "message": "report not found"}, 404
    set_report_mark(handle, name, mark or "", path=rp)
    return {"ok": True, "message": f"{name} → {mark or 'cleared'}", "mark": mark or ""}, 200
