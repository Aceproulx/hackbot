"""state.py — read live hackbot state from disk."""
import json
import os
import re

from .config import (
    FINDINGS_FILE, HUNTS_ROOT, POOL_FILE, QUEUE_FILE,
    SESSIONS_ROOT, SKILL_DIRS,
)
from .helpers import mtime, read_json, read_lines, read_file, count_files


# ── queue / workers ────────────────────────────────────────────────────────────

def get_queue() -> list:
    data = read_json(QUEUE_FILE, [])
    return data if isinstance(data, list) else []


def get_pool() -> dict:
    return read_json(POOL_FILE, {})


def get_workers() -> list:
    return get_pool().get("workers", [])


def workers_by_handle() -> dict:
    return {w.get("handle"): w for w in get_workers()}


# ── findings ──────────────────────────────────────────────────────────────────

def get_findings() -> list:
    lines = read_lines(FINDINGS_FILE, 100_000)
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


def need_attention() -> int:
    skip = {"paid", "dismissed", "informational", "closed", "n/a", "unreportable"}
    return sum(1 for f in get_findings() if str(f.get("status", "")).lower() not in skip)


# ── hunt dirs ─────────────────────────────────────────────────────────────────

def get_run_dirs() -> list:
    out = []
    if os.path.isdir(HUNTS_ROOT):
        for d in sorted(os.listdir(HUNTS_ROOT)):
            p = os.path.join(HUNTS_ROOT, d)
            if d == "sessions" or not os.path.isdir(p):
                continue
            m = re.match(r"(.+)-(\d{8})$", d)
            out.append({
                "name": d,
                "handle": m.group(1) if m else d,
                "path": p,
                "kind": "RUN",
                "mtime": mtime(p),
            })
    return out


def get_session_dirs() -> list:
    out = []
    if os.path.isdir(SESSIONS_ROOT):
        for d in sorted(os.listdir(SESSIONS_ROOT)):
            p = os.path.join(SESSIONS_ROOT, d)
            if not os.path.isdir(p):
                continue
            out.append({
                "name": d,
                "handle": d,
                "path": p,
                "kind": "SESSION",
                "mtime": mtime(p),
            })
    return out


# ── hunt detail ───────────────────────────────────────────────────────────────

def run_meta(path: str) -> dict:
    files = {}
    if os.path.isdir(path):
        for f in os.listdir(path):
            p = os.path.join(path, f)
            if os.path.isfile(p):
                files[f] = (mtime(p), os.path.getsize(p))
    return files


def get_reading(hpath: str) -> dict:
    d: dict = {}
    if not hpath:
        return d
    d["path"] = hpath
    d["name"] = os.path.basename(hpath.rstrip("/"))
    d["mtime"] = mtime(hpath)
    d["files"] = run_meta(hpath) if os.path.isdir(hpath) else {}
    d["log"] = read_file(os.path.join(hpath, "session.log"))
    d["interesting"] = read_file(os.path.join(hpath, "interesting.md"))
    d["creds"] = []
    for f in (os.listdir(hpath) if os.path.isdir(hpath) else []):
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


# ── skills ────────────────────────────────────────────────────────────────────

def skill_dirs() -> list[tuple[str, str]]:
    out = []
    for base in SKILL_DIRS:
        if os.path.isdir(base):
            for d in sorted(os.listdir(base)):
                p = os.path.join(base, d)
                if os.path.isdir(p) and os.path.isfile(os.path.join(p, "SKILL.md")):
                    out.append((d, p))
    return out


# ── log index ─────────────────────────────────────────────────────────────────

def log_index(misc_dir: str) -> list[tuple[str, str]]:
    """Return [(rel_key, abspath)] for every available console log."""
    logs = []
    pool_logdir = os.path.join(misc_dir, "worker-pool")
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
