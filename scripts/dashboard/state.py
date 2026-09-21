"""state.py — read live hackbot state from disk."""
import json
import os
import re
from datetime import datetime
from time import time

from .config import (
    FINDINGS_FILE, HUNTS_ROOT, POOL_FILE, QUEUE_FILE,
    SESSIONS_ROOT, SKILL_DIRS, README_FILE, MARKS_FILE,
    WATCHDOG, WATCHDOG_LOG, WATCHDOG_PID, WATCHDOG_REPORTS_DIR,
    YWH_TRIAGER_FILE, YWH_VERDICTS_FILE,
)
from .helpers import mtime, read_json, read_jsonl, read_lines, read_file, count_files, short_ts


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
    return read_jsonl(FINDINGS_FILE)


def get_hunted_handles() -> set:
    """Return the set of handles that have at least one logged finding."""
    return {str(f.get("program", "")).lower() for f in get_findings()}


# ── ywh-reporter triage log ───────────────────────────────────────────────────

def get_ywh_triage() -> list:
    """Newest-first entries from the ywh-reporter triage log."""
    return list(reversed(read_jsonl(YWH_TRIAGER_FILE)))


def need_attention() -> int:
    skip = {"paid", "dismissed", "informational", "closed", "n/a", "unreportable"}
    return sum(1 for f in get_findings() if str(f.get("status", "")).lower() not in skip)


# ── report read-state ─────────────────────────────────────────────────────────

def get_read_state() -> dict:
    data = read_json(README_FILE, {})
    return data if isinstance(data, dict) else {}


def mark_report_read(handle: str, name: str) -> None:
    state = get_read_state()
    kid = f"{handle}|{name}"
    state[kid] = int(time())
    try:
        with open(README_FILE, "w") as fh:
            json.dump(state, fh)
    except Exception:
        pass


# ── report marks ─────────────────────────────────────────────────────────────

MARK_LABELS = {
    "valid": "Valid",
    "duplicate": "Duplicate",
    "unreportable": "Not reportable",
    "underreview": "Under review",
}

VALID_MARKS = set(MARK_LABELS)

MARK_BANNERS = {
    "valid": "# [THIS REPORT IS VALID]",
    "duplicate": "# [THIS IS A DUPLICATE REPORT]",
    "unreportable": "# [THIS HAS BEEN MARKED AS NOT REPORTABLE]",
    "underreview": "# [THIS REPORT IS UNDER REVIEW]",
}


def get_report_marks() -> dict:
    data = read_json(MARKS_FILE, {})
    return data if isinstance(data, dict) else {}


def report_mark(handle: str, name: str) -> str:
    """Current mark key for a report, or '' when unmarked."""
    return get_report_marks().get(f"{handle}|{name}", "")


def set_report_mark(handle: str, name: str, mark: str = "", path: str = "") -> None:
    """Persist a report mark to the sidecar and stamp/clear its md banner."""
    kid = f"{handle}|{name}"
    marks = get_report_marks()
    if mark in VALID_MARKS:
        marks[kid] = mark
    else:
        marks.pop(kid, None)
    try:
        with open(MARKS_FILE, "w") as fh:
            json.dump(marks, fh)
    except Exception:
        pass
    if path:
        # A manual mark supersedes any ywh-triage verdict: drop its banner
        # and blocking-issues section so the report reflects the operator's
        # decision, then stamp the manual banner.
        if mark in VALID_MARKS:
            clear_ywh_verdict(handle, name, path=path)
        _stamp_report(path, marks.get(kid, ""))


def _stamp_report(path: str, mark: str) -> None:
    """Banner header is a side effect — the marks sidecar stays authoritative."""
    banner = MARK_BANNERS.get(mark, "")
    try:
        with open(path, errors="replace") as fh:
            lines = fh.read().split("\n")
    except Exception:
        return
    keep = [ln for ln in lines if ln.strip() not in set(MARK_BANNERS.values())]
    while keep and not keep[0].strip():
        keep.pop(0)
    if banner:
        keep.insert(0, banner)
        keep.insert(1, "")
    try:
        with open(path, "w") as fh:
            fh.write("\n".join(keep))
    except Exception:
        pass


# ── ywh-triage verdicts ───────────────────────────────────────────────────────

YWH_VERDICTS = ("READY TO SUBMIT", "NEEDS FIXES", "DO NOT SUBMIT")

YWH_BANNER_RE = re.compile(r"^#\s*\[YWH TRIAGE:.*?\]\s*$", re.I | re.M)
YWH_BLOCKING_HEAD = "## YWH Triage — Blocking issues"


def get_ywh_verdicts() -> dict:
    data = read_json(YWH_VERDICTS_FILE, {})
    return data if isinstance(data, dict) else {}


def ywh_verdict(handle: str, name: str) -> dict:
    """Current ywh-triage verdict entry for a report, or None."""
    return get_ywh_verdicts().get(f"{handle}|{name}")


def set_ywh_verdict(handle: str, name: str, verdict: str,
                    critical: list = None, major: list = None, minor: list = None,
                    path: str = "") -> None:
    """Persist a ywh-triage verdict to the sidecar and stamp the report file."""
    kid = f"{handle}|{name}"
    entry = {
        "verdict": verdict,
        "critical": critical or [],
        "major": major or [],
        "minor": minor or [],
        "ts": short_ts(),
        "draft": os.path.basename(path) if path else name,
    }
    v = get_ywh_verdicts()
    v[kid] = entry
    try:
        with open(YWH_VERDICTS_FILE, "w") as fh:
            json.dump(v, fh)
    except Exception:
        pass
    if path:
        _stamp_ywh_report(path, entry)


def clear_ywh_verdict(handle: str, name: str, path: str = "") -> None:
    """Remove a ywh-triage verdict: sidecar entry + report file artifacts."""
    kid = f"{handle}|{name}"
    v = get_ywh_verdicts()
    if kid in v:
        v.pop(kid)
        try:
            with open(YWH_VERDICTS_FILE, "w") as fh:
                json.dump(v, fh)
        except Exception:
            pass
    if path:
        _strip_ywh_artifacts(path)


def _strip_ywh_artifacts(path: str) -> None:
    """Remove the ywh banner line and the trailing blocking-issues section."""
    try:
        with open(path, errors="replace") as fh:
            text = fh.read()
    except Exception:
        return
    # drop the banner line
    text = YWH_BANNER_RE.sub("", text)
    # drop the blocking-issues section (from its --- separator to EOF)
    idx = text.find(YWH_BLOCKING_HEAD)
    if idx != -1:
        cut = text.rfind("\n---", 0, idx)
        text = text[:cut] if cut != -1 else text[:idx]
    # tidy leading blank lines
    text = text.lstrip("\n")
    try:
        with open(path, "w") as fh:
            fh.write(text)
    except Exception:
        pass


def _stamp_ywh_report(path: str, entry: dict) -> None:
    """Write the verdict banner at the top and blocking issues at the bottom."""
    verdict = entry.get("verdict", "")
    critical = entry.get("critical") or []
    major = entry.get("major") or []
    try:
        with open(path, errors="replace") as fh:
            text = fh.read()
    except Exception:
        return
    # idempotent: strip any previous ywh artifacts first (re-triage overwrites)
    text = YWH_BANNER_RE.sub("", text)
    idx = text.find(YWH_BLOCKING_HEAD)
    if idx != -1:
        cut = text.rfind("\n---", 0, idx)
        text = text[:cut] if cut != -1 else text[:idx]
    text = text.lstrip("\n")
    banner = f"# [YWH TRIAGE: {verdict}]"
    body = banner + "\n\n" + text
    if critical or major:
        body += "\n\n---\n\n" + YWH_BLOCKING_HEAD + "\n"
        if critical:
            body += "\n### Critical\n" + "".join(f"- {c}\n" for c in critical)
        if major:
            body += "\n### Major\n" + "".join(f"- {m}\n" for m in major)
    try:
        with open(path, "w") as fh:
            fh.write(body)
    except Exception:
        pass


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


def hunt_stats() -> dict:
    """Real filesystem-derived stats across every run and session dir."""
    runs = get_run_dirs()
    sess = get_session_dirs()
    reports = 0
    evidence = 0
    for h in runs + sess:
        rp = os.path.join(h["path"], "reports")
        if os.path.isdir(rp):
            reports += sum(1 for f in os.listdir(rp)
                           if f.endswith(".md") and os.path.isfile(os.path.join(rp, f)))
        ep = os.path.join(h["path"], "evidence")
        if os.path.isdir(ep):
            evidence += len([x for x in os.listdir(ep)])
    return {"hunts": len(runs) + len(sess), "runs": len(runs), "sessions": len(sess),
            "reports": reports, "evidence": evidence}


def recent_reports(limit: int = 8) -> list:
    """Most recently drafted report .md files across all runs and sessions."""
    items = all_reports()
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items[:limit]


def unread_reports() -> int:
    return sum(1 for r in all_reports() if not r["read"])


def all_reports() -> list:
    """Every report .md file across all runs and sessions, with read state."""
    read = get_read_state()
    mks = get_report_marks()
    ywh = get_ywh_verdicts()
    items = []
    for h in get_run_dirs() + get_session_dirs():
        rp = os.path.join(h["path"], "reports")
        if os.path.isdir(rp):
            for f in os.listdir(rp):
                fp = os.path.join(rp, f)
                if f.endswith(".md") and os.path.isfile(fp):
                    items.append({"name": f, "handle": h["handle"], "path": fp,
                                  "mtime": mtime(fp), "read": f"{h['handle']}|{f}" in read,
                                  "mark": mks.get(f"{h['handle']}|{f}", ""),
                                  "ywh": ywh.get(f"{h['handle']}|{f}")})
    return items


def all_evidence() -> list:
    """Every evidence file across all runs and sessions."""
    items = []
    for h in get_run_dirs() + get_session_dirs():
        ep = os.path.join(h["path"], "evidence")
        if os.path.isdir(ep):
            for f in sorted(os.listdir(ep)):
                fp = os.path.join(ep, f)
                if os.path.isfile(fp):
                    items.append({"name": f, "handle": h["handle"], "path": fp, "mtime": mtime(fp)})
    return items


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


# ── watchdog ──────────────────────────────────────────────────────────────────

_WG_TITLE_RE = re.compile(r"^#\s*Watchdog Report\s*[—\-:]*\s*(\S+)", re.I)
_WG_POOL_RE = re.compile(r"^Pool:\s*(.+)$", re.I | re.M)
_WG_LOG_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$")

# log-prefix → event kind (order matters: most specific first)
_WG_KINDS = (
    ("timeout", "Monitor cycle TIMEOUT"),
    ("cycle-done", "Monitor cycle finished"),
    ("cycle-start", "Monitor cycle started"),
    ("started", "Watchdog started"),
    ("stopped", "Watchdog stopped"),
    ("killed", "Killed daemon"),
    ("daemon", "Daemon PID:"),
    ("sleep", "Sleeping "),
)


def watchdog_daemon() -> dict:
    """Daemon liveness — PID file + kill(0) probe, mirroring watchdog.sh status."""
    pid = read_file(WATCHDOG_PID).strip()
    running = False
    if pid:
        try:
            os.kill(int(pid), 0)
            running = True
        except Exception:
            running = False
    return {"running": running, "pid": pid}


def watchdog_settings() -> dict:
    """Interval / timeout read straight from the installed watchdog script."""
    txt = read_file(WATCHDOG) if WATCHDOG else ""

    def grab(key: str, dflt: int) -> int:
        m = re.search(rf"^{key}=(\d+)", txt, re.M)
        return int(m.group(1)) if m else dflt

    return {"interval": grab("INTERVAL", 1800), "timeout": grab("TIMEOUT", 900)}


def parse_watchdog_report(text: str) -> dict:
    """Turn one cycle report into a notification-shaped dict (summary + actions)."""
    rep = {"ts": "", "slots": 0, "running": 0, "healthy": 0, "fixed": 0, "stuck": 0, "actions": []}
    m = _WG_TITLE_RE.search(text)
    if m:
        rep["ts"] = m.group(1)
    # Pool line has several shapes — e.g. "0 healthy-prior", "0 healthy-untouched",
    # "1 stuck (monitoring)" instead of "N fixed". Match each segment independently.
    m = _WG_POOL_RE.search(text)
    if m:
        seg = m.group(1)

        def num(pat: str) -> int:
            mm = re.search(pat, seg, re.I)
            return int(mm.group(1)) if mm else 0

        rep["slots"] = num(r"(\d+)\s*slots?")
        rep["running"] = num(r"(\d+)\s*running")
        rep["healthy"] = num(r"(\d+)\s*healthy")
        rep["fixed"] = num(r"(\d+)\s*fixed")
        rep["stuck"] = num(r"(\d+)\s*stuck")
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        first = cells[0].lower()
        if first == "worker" or set(cells[0]) <= set("-: "):
            continue  # header row / separator
        rep["actions"].append({
            "worker": cells[0],
            "handle": cells[1],
            "verdict": cells[2],
            "action": cells[3],
            "reason": " | ".join(cells[4:]) if len(cells) > 4 else "",
        })
    return rep


def get_watchdog_reports(limit: int = 40) -> list:
    """Newest-first parsed cycle reports from watchdog-reports/*.md."""
    if not os.path.isdir(WATCHDOG_REPORTS_DIR):
        return []
    files = [f for f in os.listdir(WATCHDOG_REPORTS_DIR) if f.endswith(".md")]
    files.sort(key=lambda f: mtime(os.path.join(WATCHDOG_REPORTS_DIR, f)), reverse=True)
    out = []
    for f in files[:limit]:
        p = os.path.join(WATCHDOG_REPORTS_DIR, f)
        rep = parse_watchdog_report(read_file(p))
        rep["file"] = f
        rep["mtime"] = mtime(p)
        if not rep["ts"]:
            rep["ts"] = datetime.fromtimestamp(mtime(p)).strftime("%Y-%m-%dT%H:%M:%SZ")
        out.append(rep)
    return out


def get_watchdog_events(limit: int = 120) -> list:
    """Newest-first parsed watchdog.log lines: {ts, msg, kind}."""
    out = []
    for line in read_lines(WATCHDOG_LOG, limit=5000)[-limit:]:
        m = _WG_LOG_RE.match(line.strip())
        if not m:
            continue
        ts, msg = m.group(1), m.group(2)
        kind = next((k for k, prefix in _WG_KINDS if msg.startswith(prefix)), "other")
        out.append({"ts": ts, "msg": msg, "kind": kind})
    out.reverse()
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
