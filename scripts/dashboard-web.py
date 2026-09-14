#!/usr/bin/env python3
"""Hackbot Web Dashboard — stdlib-only local dashboard server.

Renders findings, worker pool, target queue, hunt-session history and exported
reports from the hackbot runtime data dirs. Serves on 127.0.0.1 by default.

Usage:
  python3 dashboard-web.py [--port 7878] [--host 127.0.0.1]
"""
import argparse
import datetime
import html
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REF: float = 15.0  # seconds between auto-refreshes


def cfg_path():
    p = Path.home() / ".hackbot" / "config.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


CFG = cfg_path()
MISC = Path(CFG.get("hackbot_misc_dir") or str(Path.home() / "Projects/hackbot-misc")).expanduser()
SESSIONS = Path(CFG.get("sessions_dir") or str(MISC / "sessions")).expanduser()
HUNTS = SESSIONS.parent
FINDINGS = MISC / "findings.jsonl"
POOL = MISC / "worker-pool" / "pool.json"
QUEUE = MISC / "target-queue.json"
REPORTS = MISC / "reports"

NOW = datetime.datetime.utcnow()

SEV_COLORS = {
    "Critical": "#ff4d4f",
    "High": "#ff9c3f",
    "Medium": "#fadb14",
    "Low": "#52c41a",
}
STATUS_COLORS = {
    "confirmed": "ok",
    "triaged": "info",
    "pending": "warn",
    "duplicate": "dup",
    "informative": "dup",
    "n/a": "dup",
    "running": "ok",
    "done": "info",
    "skipped": "warn",
    "waf_blocked": "warn",
    "auth_blocked": "warn",
}


def esc(s):
    return html.escape(str(s) if s is not None else "")


def ts_fmt(v):
    if not v:
        return "\u2014"
    try:
        dt = datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return esc(v)[:16]


def age(v):
    if not v:
        return "\u2014"
    try:
        dt = datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        d = (datetime.datetime.now(dt.tzinfo) - dt)
        mins = int(d.total_seconds() // 60)
        if mins < 60:
            return f"{mins}m ago"
        h = mins // 60
        if h < 48:
            return f"{h}h ago"
        return f"{h // 24}d ago"
    except Exception:
        return esc(str(v))[:12]


def read_jsonl():
    out = []
    if not FINDINGS.exists():
        return out
    with FINDINGS.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def read_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def summary_cards(findings, pool, queue, sessions, reports):
    f_sev = {}
    for f in findings:
        f_sev[f.get("severity") or "Info"] = f_sev.get(f.get("severity") or "Info", 0) + 1
    running = sum(1 for w in (pool or {}).get("workers", []) if w.get("status") == "running")
    pending = [q for q in (queue or []) if q.get("status") == "pending"]
    total_est = sum(int(f.get("bounty_est") or 0) for f in findings)
    paid = sum(int(f.get("bounty_paid") or 0) for f in findings)
    cards = [
        ("Findings", str(len(findings)), "total logged", "#e8eaed"),
        ("Confirmed", str(sum(1 for f in findings if (f.get("status") or "").lower() == "confirmed")), "accepted", "#52c41a"),
        ("Est. bounty", f"${total_est:,}", f"${paid:,} paid", "#52c41a"),
        ("Programs", str(len({f.get("program") for f in findings if f.get("program")})), "distinct", "#e8eaed"),
        ("Active workers", str(running), f"/ {(pool or {}).get('slots', '?')}", "#52c41a" if running else "#9aa0a6"),
        ("Queue pending", str(len(pending)), f"{len(queue or [])} total", "#ffbf00"),
        ("Hunt sessions", str(len(sessions)), "recent", "#e8eaed"),
        ("Reports", str(len(reports)), "exported", "#e8eaed"),
    ]
    rows = "".join(
        f'<div class="card"><div class="card-num">{c[1]}</div>'
        f'<div class="card-label">{c[0]}</div><div class="card-sub" style="color:{c[3]}">{c[2]}</div></div>'
        for c in cards
    )
    return f'<div class="cards">{rows}</div>'


def pill(text, key, palette=STATUS_COLORS):
    color = palette.get(str(key).lower(), "#9aa0a6")
    return f'<span class="pill" style="color:{color};border-color:{color}">{esc(text)}</span>'


def findings_table(findings):
    if not findings:
        return '<div class="empty">No findings logged yet — they appear here as workers confirm bugs.</div>'
    head = ("Time", "Sev", "Status", "Program", "Title", "Est", "Evidence")
    rows = []
    for f in sorted(findings, key=lambda x: x.get("ts") or x.get("reported_at") or "", reverse=True):
        sev = f.get("severity") or "Info"
        sevc = SEV_COLORS.get(sev, "#9aa0a6")
        title = esc(f.get("title"))
        url = f.get("url")
        if url:
            title = f'<a href="{esc(url)}" target="_blank">{title}</a>'
        ev = esc(f.get("evidence") or "")
        rows.append(
            f"<tr>"
            f"<td class='dim'>{ts_fmt(f.get('ts') or f.get('reported_at'))}</td>"
            f"<td><span class='pill' style='color:{sevc};border-color:{sevc}'>{esc(sev)}</span></td>"
            f"<td>{pill(f.get('status'), f.get('status'))}</td>"
            f"<td>{esc(f.get('program'))}</td>"
            f"<td>{title}</td>"
            f"<td class='num'>${int(f.get('bounty_est') or 0):,}</td>"
            f"<td class='dim'>{ev}</td>"
            f"</tr>"
        )
    return _table(head, rows)


def workers_table(pool):
    if not pool:
        return '<div class="empty">Worker pool has not started yet.</div>'
    last_started = max((w.get("started_at", "") for w in pool.get("workers", [])), default="")
    header = f'<div class="subhead">Pool started {age(last_started)} · budget ${pool.get("budget_per_worker", "?")}/worker · slots {pool.get("slots", "?")}</div>'
    head = ("Slot", "Handle", "Status", "Bugs", "Max bounty", "Running for")
    rows = []
    for w in pool.get("workers", []):
        rows.append(
            f"<tr>"
            f"<td>{esc(w.get('slot'))}</td>"
            f"<td><b>{esc(w.get('handle'))}</b></td>"
            f"<td>{pill(w.get('status'), w.get('status'))}</td>"
            f"<td class='num'>{int(w.get('bugs_found') or 0)}</td>"
            f"<td class='num'>${int(w.get('max_bounty') or 0):,}</td>"
            f"<td class='dim'>{age(w.get('started_at'))}</td>"
            f"</tr>"
        )
    return header + _table(head, rows, limit=8)


def queue_table(queue):
    if not queue:
        return '<div class="empty">Queue not initialized — run `hackbot-queue init`.</div>'
    head = ("#", "Handle", "Status", "Score", "Max bounty", "Bugs", "Last hunted", "Verdict")
    rows = []
    for i, q in enumerate(sorted(queue, key=lambda x: -((x.get("score") or 0) + (x.get("boost") or 0))), 1):
        rows.append(
            f"<tr>"
            f"<td class='dim'>{i}</td>"
            f"<td><b>{esc(q.get('handle'))}</b></td>"
            f"<td>{pill(q.get('status'), q.get('status'))}</td>"
            f"<td class='num'>{int(q.get('score') or 0)}</td>"
            f"<td class='num'>${int(q.get('max_bounty') or 0):,}</td>"
            f"<td class='num'>{int(q.get('bugs_found') or 0)}</td>"
            f"<td class='dim'>{age(q.get('last_hunted'))}</td>"
            f"<td class='dim'>{esc(q.get('last_verdict') or '\u2014')}</td>"
            f"</tr>"
        )
    return _table(head, rows, limit=40)


def _dir_sessions():
    out = []
    if HUNTS.is_dir():
        pat = re.compile(r"^(.+)-(\d{8})$")
        for d in sorted(HUNTS.iterdir(), key=lambda x: x.name):
            if not d.is_dir():
                continue
            m = pat.match(d.name)
            if m:
                mtime = datetime.datetime.fromtimestamp(d.stat().st_mtime)
                out.append({"kind": "hunt", "name": m.group(1), "date": m.group(2), "path": d, "mtime": mtime})
    sess = SESSIONS
    if sess.is_dir():
        for d in sorted(sess.iterdir(), key=lambda x: x.name):
            if not d.is_dir():
                continue
            mtime = datetime.datetime.fromtimestamp(d.stat().st_mtime)
            out.append({"kind": "session", "name": d.name, "path": d, "mtime": mtime})
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


def sessions_table(sessions):
    if not sessions:
        return '<div class="empty">No hunt sessions yet.</div>'
    head = ("Session", "Type", "Last activity", "Evidence", "Reports", "Accounts")
    rows = []
    for s in sessions:
        ev = list((s["path"] / "evidence").glob("*")) if (s["path"] / "evidence").is_dir() else []
        reps = list((s["path"] / "reports").glob("*")) if (s["path"] / "reports").is_dir() else []
        has_a = (s["path"] / "userA").exists()
        has_b = (s["path"] / "userB").exists()
        accs = f"{'A' if has_a else ''}{'+' if has_a and has_b else ''}{'B' if has_b else ''}".strip() or "\u2014"
        rows.append(
            f"<tr>"
            f"<td><b>{esc(s['name'])}</b><div class='dim small'>{esc(str(s['path']))}</div></td>"
            f"<td>{pill(s['kind'], 'info' if s['kind'] == 'session' else 'run')}</td>"
            f"<td class='dim'>{s['mtime'].strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td class='num'>{len(ev)}</td>"
            f"<td class='num'>{len(reps)}</td>"
            f"<td class='num'>{accs}</td>"
            f"</tr>"
        )
    return _table(head, rows, limit=30)


def reports_table(reports):
    if not reports:
        return '<div class="empty">No exported reports yet — run `hackbot-dashboard export`.</div>'
    head = ("Report", "Exported", "Size")
    rows = []
    for p in reports:
        mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
        size = p.stat().st_size
        rows.append(
            f"<tr>"
            f"<td><a href='/report/{esc(p.name)}'>{esc(p.name)}</a></td>"
            f"<td class='dim'>{mtime.strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td class='num'>{size:,} B</td>"
            f"</tr>"
        )
    return _table(head, rows)


def _table(head, rows, limit=None):
    body = rows if limit is None else rows[:limit]
    return (
        "<div class='tblwrap'><table><thead><tr>"
        + "".join(f"<th>{h}</th>" for h in head)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def page():
    findings = read_jsonl()
    pool = read_json(POOL)
    queue = read_json(QUEUE)
    sessions = _dir_sessions()
    reports = sorted(REPORTS.glob("*.md")) if REPORTS.is_dir() else []
    updated = datetime.datetime.utcnow().strftime("%H:%M:%S UTC")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{int(REF)}">
<title>Hackbot Dashboard</title>
<style>
:root {{ --bg:#0b0e14; --panel:#11161f; --line:#232b38; --text:#e8eaed; --dim:#9aa0a6; --accent:#4f9cf9; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:14px/1.5 ui-monospace,'SF Mono',Menlo,Consolas,monospace; }}
header {{ padding:14px 22px; border-bottom:1px solid var(--line); display:flex; gap:18px; align-items:baseline; }}
h1 {{ font-size:18px; margin:0; letter-spacing:.5px; }} h1 span {{ color:var(--accent); }}
.sub {{ color:var(--dim); font-size:12px; }} .rel {{ margin-left:auto; color:var(--dim); font-size:12px; }}
main {{ padding:18px 22px 60px; max-width:1400px; margin:0 auto; }}
section {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px 18px; margin-bottom:18px; }}
h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:1.5px; color:var(--dim); margin:0 0 12px; }}
h2 .cnt {{ color:var(--accent); }}
.subhead {{ color:var(--dim); font-size:12px; margin:-6px 0 10px; }}
.cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:18px; }}
@media(max-width:900px){{ .cards {{ grid-template-columns:repeat(2,1fr); }} }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px 18px; }}
.card-num {{ font-size:26px; font-weight:700; }} .card-label {{ font-size:12px; color:var(--dim); margin-top:2px; }}
.card-sub {{ font-size:12px; margin-top:2px; }}
.tblwrap {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ text-align:left; color:var(--dim); font-weight:600; border-bottom:1px solid var(--line); padding:8px 10px; }}
td {{ padding:8px 10px; border-bottom:1px solid #1a212c; vertical-align:top; }}
tr:hover td {{ background:#161d29; }}
.num {{ text-align:right; }} th:has(+ th.num){{ text-align:right; }}
.dim {{ color:var(--dim); }} .small {{ font-size:11px; }} .empty {{ color:var(--dim); padding:14px 4px; }}
.pill {{ border:1px solid; border-radius:999px; padding:1px 9px; font-size:11px; display:inline-block; white-space:nowrap; }}
a {{ color:var(--accent); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
</style></head><body>
<header><h1>Hackbot<span>_</span> Dashboard</h1>
<span class="sub">Intigriti autonomous pipeline</span>
<span class="rel">auto-refresh {int(REF)}s · {updated}</span></header>
<main>
{summary_cards(findings, pool, queue, sessions, reports)}
<section><h2>Findings <span class="cnt">({len(findings)})</span></h2>{findings_table(findings)}</section>
<section><h2>Active Workers <span class="cnt">({len((pool or {}).get('workers', []))})</span></h2>{workers_table(pool)}</section>
<section><h2>Target Queue <span class="cnt">({len(queue or [])})</span></h2>{queue_table(queue)}</section>
<section><h2>Hunt Sessions <span class="cnt">({len(sessions)})</span></h2>{sessions_table(sessions)}</section>
<section><h2>Reports <span class="cnt">({len(reports)})</span></h2>{reports_table(reports)}</section>
</main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(200, page(), "text/html")
        elif path == "/api/findings":
            self._send(200, json.dumps(read_jsonl(), indent=2), "application/json")
        elif path == "/api/pool":
            self._send(200, json.dumps(read_json(POOL) or {}, indent=2), "application/json")
        elif path == "/api/queue":
            self._send(200, json.dumps(read_json(QUEUE) or [], indent=2), "application/json")
        elif path.startswith("/report/"):
            name = path.split("/")[-1]
            p = (REPORTS / name).resolve()
            if REPORTS.resolve() in p.parents and p.is_file():
                self._send(200, p.read_text(errors="replace"), "text/plain")
            else:
                self._send(404, "Not found", "text/plain")
        else:
            self._send(404, "Not found", "text/plain")

    def _send(self, code, body, ctype):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # silence default logging
        pass


def main():
    ap = argparse.ArgumentParser(description="Hackbot web dashboard")
    ap.add_argument("--port", type=int, default=7878)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    print(f"Hackbot dashboard → http://{args.host}:{args.port}/")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()