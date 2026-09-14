"""ui.py — design system, layout components, and page() shell."""
from .config import MAX_SLOTS, PLATFORM
from .helpers import esc
from .icons import icon
from .state import get_queue, need_attention

# ── NAV definition ─────────────────────────────────────────────────────────────

NAV = [
    ("WORKSPACE", [
        ("overview",   "Overview",      "dashboard"),
        ("hunts",      "Hunts",         "target"),
        ("findings",   "Findings",      "flag"),
        ("history",    "History",       "clock"),
        ("monitors",   "Monitors",      "activity"),
        ("topology",   "Topology",      "git-branch"),
    ]),
    ("LIBRARY", [
        ("knowledge",  "Knowledge",     "book-open"),
        ("memory",     "Memory",        "database"),
        ("assets",     "Assets",        "package"),
        ("skills",     "Skills",        "star"),
    ]),
    ("MANAGE", [
        ("workspaces", "Workspaces",    "folder"),
        ("desktops",   "Desktops",      "monitor"),
        ("registrations", "Registrations", "mail"),
        ("usage",      "Usage",         "bar-chart-2"),
        ("settings",   "Settings",      "sliders"),
    ]),
]

NAV_TITLES = {k: lbl for _, items in NAV for k, lbl, _ in items}
NAV_TITLES.update({
    "hunt":    "Hunt",
    "console": "Console",
    "report":  "Report",
})

# ── CSS ────────────────────────────────────────────────────────────────────────

CSS = """
:root {
  --canvas:#f7f4ee; --sidebar:#efe8dd; --card:#ffffff; --border:#e1d9cc;
  --ink:#242019; --muted:#8c8579; --accent:#8f1618; --accent-hi:#a4161a;
  --deep:#160d0c; --green:#1a7a43; --amber:#b96b00; --grey:#9a938a;
  --blue:#2f5cb0; --reportable:#1a7a43; --unreportable:#8f1618;
  --shadow:0 1px 2px rgba(40,25,10,.05), 0 4px 16px rgba(40,25,10,.05);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--canvas);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,system-ui,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.mono,pre,code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}

/* layout */
.layout{display:flex;min-height:100vh}
.main{flex:1;margin-left:244px;min-width:0;transition:margin-left .18s ease}
.sidebar{position:fixed;left:0;top:0;bottom:0;width:244px;background:var(--sidebar);border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:50;transition:width .18s ease}
.layout.collapsed .sidebar{width:56px}
.layout.collapsed .main{margin-left:56px}
.layout.collapsed .logo{justify-content:center;padding:18px 6px 14px}
.layout.collapsed .logo>div:last-child{display:none}
.layout.collapsed .nav{padding:12px 6px 40px}
.layout.collapsed .nav .sec{height:0;margin:0;overflow:hidden;opacity:0}
.layout.collapsed .nav a{justify-content:center;gap:0;padding:8px 0}
.layout.collapsed .nav a .ic{display:block;margin:0}
.layout.collapsed .nav a>span:not(.ic):not(.badge){display:none}
.layout.collapsed .nav a .badge{position:absolute;right:5px;top:0;margin:0;min-width:14px;height:14px;padding:0 3px;border-radius:7px;font-size:9px}
.layout.collapsed .nav a.active::before{left:-4px;width:2px}
.layout.collapsed .console-tab{left:32px}
.collapse-btn{display:flex;align-items:center;justify-content:center;width:32px;height:28px;margin:10px 10px 14px;padding:0;border:1px solid var(--border);border-radius:8px;background:#fff;color:var(--muted);cursor:pointer;align-self:flex-start}
.collapse-btn:hover{color:var(--accent);border-color:var(--accent)}
.layout.collapsed .collapse-btn{align-self:center;margin:12px auto 14px}
.collapse-btn .ci{display:inline-flex}
.layout.collapsed .ci-open{display:none}
.layout:not(.collapsed) .ci-close{display:none}

/* logo */
.logo{display:flex;align-items:center;gap:10px;padding:18px 16px 14px;border-bottom:1px solid var(--border)}
.logo .mark{width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,#1a0f0e,#4a1d16);display:flex;align-items:center;justify-content:center;font-size:18px;color:#f4e9dc;box-shadow:inset 0 0 0 1px rgba(255,255,255,.12)}
.logo .brand{font-weight:800;letter-spacing:.14em;font-size:15px;color:#2c231c}
.logo .sub{font-size:10px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;font-weight:600}

/* sidebar nav */
.nav{flex:1;overflow-y:auto;padding:12px 8px 120px}
.nav .sec{margin:16px 4px 6px;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.nav a{display:flex;align-items:center;gap:9px;padding:7px 10px;margin:1px 0;border-radius:8px;color:#3d352b;font-weight:500;font-size:13.5px;position:relative}
.nav a:hover{background:rgba(255,255,255,.65);text-decoration:none}
.nav a.active{background:rgba(143,22,24,.07);font-weight:700;color:var(--accent)}
.nav a.active::before{content:"";position:absolute;left:-8px;top:4px;bottom:4px;width:3px;border-radius:2px;background:var(--accent)}
.nav a .ic{width:16px;text-align:center;opacity:.85}
.ic-svg{vertical-align:-3px;display:inline-block;flex:none}
.badge{display:inline-flex;margin-left:auto;min-width:18px;height:18px;padding:0 5px;border-radius:9px;background:var(--accent);color:#fff;font-size:10.5px;font-weight:700;align-items:center;justify-content:center}
.badge.neutral{background:#d8d0c2;color:#6c6455}

/* console tab */
.console-tab{position:fixed;left:216px;top:47%;transform:rotate(180deg);writing-mode:vertical-rl;background:#111;color:#7ee787;font:600 11px/1 ui-monospace,monospace;letter-spacing:.22em;padding:12px 7px;border-radius:0 10px 10px 0;border:1px solid #000;cursor:pointer;z-index:60;box-shadow:0 2px 10px rgba(0,0,0,.35)}
.console-tab:hover{background:#1a1a1a;color:#a5f3b0}

/* top bar */
.topbar{position:sticky;top:0;z-index:40;display:flex;align-items:center;gap:10px;padding:10px 22px;background:rgba(247,244,238,.95);backdrop-filter:blur(6px);border-bottom:1px solid var(--border)}
.searchbox{flex:1;max-width:420px;position:relative}
.searchbox input{width:100%;padding:8px 12px 8px 34px;border:1px solid var(--border);border-radius:9px;background:#fff;font-size:13px;color:var(--ink);outline:none}
.searchbox input:focus{border-color:var(--accent)}
.searchbox .glass{position:absolute;left:11px;top:8px;color:var(--muted)}
.topbar .grow{flex:1}
.gridicon{background:#fff;border:1px solid var(--border);border-radius:8px;width:34px;height:34px;display:grid;place-items:center;color:#6c6455;cursor:pointer}
.gridicon:hover{color:var(--accent)}
.attention{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:20px;background:rgba(143,22,24,.08);color:var(--accent);font-size:12.5px;font-weight:600;border:1px solid rgba(143,22,24,.18)}
.attention .n{background:var(--accent);color:#fff;border-radius:9px;min-width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;padding:0 5px;font-size:11px;font-weight:800}

/* buttons */
.btn{background:var(--accent);color:#fff;border:none;border-radius:8px;padding:8px 15px;font:600 13px -apple-system,sans-serif;cursor:pointer;display:inline-flex;align-items:center;gap:7px;box-shadow:0 1px 3px rgba(143,22,24,.35);white-space:nowrap}
.btn:hover{background:var(--accent-hi);text-decoration:none}
.btn.ghost{background:#fff;color:#3d352b;border:1px solid var(--border);box-shadow:none}
.btn.ghost:hover{color:var(--accent);border-color:#d8c4b8}
.btn.small{padding:4px 10px;font-size:12px;border-radius:7px}
.btn.green{background:var(--green);box-shadow:0 1px 3px rgba(26,122,67,.35)}
.btn.green:hover{background:#155e33}
.btn:disabled{opacity:.4;cursor:not-allowed}

/* hero banner */
.hero{position:relative;padding:38px 34px 32px;color:#f6efe4;background:
  radial-gradient(1200px 500px at 85% -20%, rgba(176,58,46,.42), transparent 60%),
  radial-gradient(900px 420px at 0% 120%, rgba(60,20,20,.55), transparent 55%),
  linear-gradient(135deg,#170d0c 0%,#2a1310 48%,#3b1c12 100%);
  border-bottom:1px solid #0d0807;box-shadow:inset 0 -40px 60px -60px rgba(0,0,0,.5)}
.hero h1{font-size:30px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}
.hero .sub{color:#d9c9b8;font-size:13px;margin-top:6px;max-width:720px}
.hero .topline{display:flex;align-items:center;gap:14px;margin-bottom:14px;flex-wrap:wrap}
.back{display:inline-flex;align-items:center;gap:6px;color:#e8d9c8;font-size:12.5px;font-weight:600;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);padding:5px 12px;border-radius:7px}
.back:hover{background:rgba(255,255,255,.16);color:#fff;text-decoration:none}

/* content */
.content{padding:22px 26px 60px}
.row{display:flex;gap:16px;flex-wrap:wrap}
.col{flex:1;min-width:340px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);margin-bottom:18px;overflow:hidden}
.card .hd{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid #eee8dd;font-weight:700;font-size:13px;letter-spacing:.02em}
.card .hd .sp{flex:1}
.card .hd .hint{font-size:11.5px;color:var(--muted);font-weight:500}
.card .bd{padding:14px 16px}
.nw{white-space:nowrap}

/* stat cards */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-bottom:20px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 18px;box-shadow:var(--shadow)}
.stat .lab{font-size:11px;font-weight:700;letter-spacing:.1em;color:var(--muted);text-transform:uppercase}
.stat .val{font-size:26px;font-weight:800;margin-top:6px}
.stat .sub{font-size:11.5px;color:var(--muted);margin-top:4px}

/* tables */
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:8px 12px;color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:8px 12px;border-bottom:1px solid #f0eadf;vertical-align:middle}
tr:last-child td{border-bottom:none}
tbody tr:hover{background:#fbf8f3}
td.num{text-align:right;font-variant-numeric:tabular-nums}
th.num{text-align:right}

/* pills */
.pill{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:11.5px;font-weight:600;white-space:nowrap}
.pill .dot{width:7px;height:7px;border-radius:50%;background:currentColor;flex:none}
.pill.green{background:#e5f4ea;color:var(--green)}
.pill.grey{background:#efebe4;color:#7a7266}
.pill.red{background:#fae7e5;color:var(--accent)}
.pill.amber{background:#fcf0dc;color:var(--amber)}
.pill.blue{background:#e7eefb;color:var(--blue)}
.pill.gold{background:#faf0d9;color:#8a6a14}
.pill.mono{font-family:ui-monospace,monospace}

/* hunt cards */
.hgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}
.hcard{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:8px}
.hcard .t{font-weight:700;font-size:14px;display:flex;align-items:center;gap:8px;word-break:break-all}
.hcard .m{font-size:12px;color:var(--muted)}
.hcard .foot{display:flex;align-items:center;gap:8px;margin-top:2px}
.filter-item{transition:opacity .15s}

/* tabs */
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--border);margin-bottom:16px;flex-wrap:wrap}
.tabs .t{padding:8px 14px;border-radius:9px 9px 0 0;font-weight:600;font-size:13px;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;user-select:none}
.tabs .t.active{color:var(--accent);border-bottom-color:var(--accent);background:rgba(143,22,24,.04)}
.tabs .t .cnt{font-size:10.5px;background:#e9e2d5;border-radius:8px;padding:1px 6px;margin-left:5px;color:#6c6455}

/* donut */
.donut-wrap{display:flex;align-items:center;gap:26px;padding:18px 22px;flex-wrap:wrap}
.donut{position:relative;width:168px;height:168px;border-radius:50%;flex:none}
.donut .core{position:absolute;inset:24px;background:#fff;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:inset 0 0 0 1px var(--border)}
.donut .core .big{font-size:22px;font-weight:800}
.donut .core .sm{font-size:10px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
.legend{display:flex;flex-direction:column;gap:7px;min-width:200px}
.legend .lg{display:flex;align-items:center;gap:9px;font-size:12.5px}
.legend .sw{width:10px;height:10px;border-radius:3px;flex:none}
.legend .name{flex:1}
.legend .pct{font-weight:700;font-variant-numeric:tabular-nums}

/* console terminal */
.terminal{background:#0d0f12;color:#d8dee4;font:12.5px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;padding:16px 18px;border-radius:0 0 12px 12px;overflow-x:auto;white-space:pre-wrap;word-break:break-word}
.console-bar{display:flex;align-items:center;gap:12px;padding:10px 16px;background:#0a0c0f;border-bottom:1px solid #23272d;color:#9aa4b0;font-size:12px;flex-wrap:wrap}
.console-bar .title{font-weight:700;color:#e5eaf0;display:flex;align-items:center;gap:8px}
.console-bar select{background:#16191e;color:#d8dee4;border:1px solid #2c3138;border-radius:6px;padding:4px 8px;font-size:12px;font-family:inherit}
.console-bar .btn.ghost{background:#16191e;color:#d8dee4;border-color:#2c3138;box-shadow:none}
.console-bar .btn.ghost:hover{color:#fff;border-color:#3a414c;background:#1e222a}

/* modal */
.modal-bg{position:fixed;inset:0;background:rgba(20,12,10,.5);z-index:200;display:none;align-items:flex-start;justify-content:center;padding-top:7vh;overflow-y:auto}
.modal{background:#fff;border-radius:14px;width:560px;max-width:96vw;box-shadow:0 20px 60px rgba(0,0,0,.35);overflow:hidden;margin:auto}
.modal .hd{padding:14px 18px;background:var(--sidebar);border-bottom:1px solid var(--border);font-weight:700;display:flex;align-items:center;gap:10px}
.modal .hd .sp{flex:1}
.modal .bd{padding:16px 18px;max-height:72vh;overflow-y:auto}
.modal label{display:block;font-size:12px;font-weight:600;color:var(--muted);margin-bottom:4px;margin-top:12px;text-transform:uppercase;letter-spacing:.06em}
.modal input,.modal textarea,.modal select{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:13px;font-family:inherit;margin-bottom:4px;background:#fff;color:var(--ink)}
.modal input:focus,.modal textarea:focus,.modal select:focus{border-color:var(--accent);outline:none}
.modal textarea{min-height:80px;resize:vertical}

/* finding detail panel */
.finding-card{background:var(--card);border:1px solid var(--border);border-radius:12px;margin-bottom:14px;overflow:hidden;box-shadow:var(--shadow)}
.finding-card .fc-head{display:flex;align-items:center;gap:10px;padding:12px 16px;cursor:pointer;user-select:none}
.finding-card .fc-head:hover{background:#faf7f2}
.finding-card .fc-body{border-top:1px solid #eee8dd;padding:16px}
.finding-card .fc-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 16px;background:#f9f6f0;border-top:1px solid #eee8dd}
.verdict-btn{padding:6px 16px;border-radius:8px;font-size:12.5px;font-weight:700;border:2px solid transparent;cursor:pointer;display:inline-flex;align-items:center;gap:6px;transition:all .15s}
.verdict-btn.reportable{background:#e5f4ea;color:var(--green);border-color:var(--green)}
.verdict-btn.reportable.active,.verdict-btn.reportable:hover{background:var(--green);color:#fff}
.verdict-btn.unreportable{background:#fae7e5;color:var(--accent);border-color:var(--accent)}
.verdict-btn.unreportable.active,.verdict-btn.unreportable:hover{background:var(--accent);color:#fff}
.verdict-btn.needs-review{background:#fcf0dc;color:var(--amber);border-color:var(--amber)}
.verdict-btn.needs-review.active,.verdict-btn.needs-review:hover{background:var(--amber);color:#fff}

/* severity badges */
.sev-critical{background:#3d0a0a;color:#ff9999;font-weight:800}
.sev-high{background:#fae7e5;color:#8f1618;font-weight:700}
.sev-medium{background:#fcf0dc;color:#b96b00;font-weight:700}
.sev-low{background:#efebe4;color:#6c6455;font-weight:600}
.sev-info{background:#e7eefb;color:#2f5cb0;font-weight:600}

/* filter bar */
.fbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.fbar .f{padding:5px 12px;border:1px solid var(--border);border-radius:8px;background:#fff;font-size:12px;color:#555;cursor:pointer;white-space:nowrap}
.fbar .f.active{color:var(--accent);border-color:var(--accent);background:rgba(143,22,24,.05);font-weight:600}
.fbar select,.fbar input[type=text]{padding:6px 10px;border:1px solid var(--border);border-radius:8px;font-size:12.5px;background:#fff;color:var(--ink);font-family:inherit}

/* empty */
.empty{text-align:center;color:var(--muted);padding:46px 20px}
.empty .ic{font-size:34px;opacity:.5;margin-bottom:10px}
.empty .t{font-weight:600;color:#7a7266;margin-bottom:8px}

/* misc */
.mt{margin-top:14px} .right{text-align:right}
.muted{color:var(--muted)} .small{font-size:12px}
code.inline{background:#efe9dd;border-radius:5px;padding:1px 6px;font-size:12px}
.pread{white-space:pre-wrap;word-break:break-word;font-size:12.5px;line-height:1.5}
.statline{display:flex;gap:8px;flex-wrap:wrap;font-size:12px;color:var(--muted)}
.breadcrumb{font-size:12px;color:var(--muted);margin-bottom:10px}
 .node-link{color:#3d352b;font-weight:600}
 .dot-u{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--accent);vertical-align:middle}
 .unread-tag{color:var(--accent);font-weight:700;font-size:11px;letter-spacing:.07em}
 tbody tr.unread td{background:rgba(143,22,24,.03)}
 .md{font-size:13.5px;line-height:1.6;color:var(--ink)}
 .md h1,.md h2,.md h3,.md h4{margin:18px 0 8px;font-weight:700;line-height:1.3}
 .md h1{font-size:19px;border-bottom:1px solid var(--border);padding-bottom:6px}
 .md h2{font-size:16px} .md h3{font-size:14.5px} .md h4{font-size:13.5px}
 .md h1:first-child{margin-top:0}
 .md p{margin:8px 0}
 .md ul,.md ol{margin:8px 0;padding-left:22px}
 .md li{margin:3px 0}
 .md li.task-list-item{list-style:none;margin-left:-20px}
 .md a{color:#155e8f;text-decoration:none;border-bottom:1px solid rgba(21,94,143,.3)}
 .md strong{font-weight:700}
 .md blockquote{margin:10px 0;padding:2px 14px;border-left:3px solid var(--border);color:var(--muted);background:#faf7f0}
 .md code{background:#efe9dd;border-radius:5px;padding:1px 6px;font-size:12px}
 .md pre{background:#0d0f12;color:#d8dee4;padding:12px 14px;border-radius:10px;overflow-x:auto;margin:10px 0}
 .md pre code{background:none;color:inherit;padding:0;font-size:12.5px;line-height:1.5}
 .md table{border-collapse:collapse;margin:12px 0;width:100%}
 .md th,.md td{border:1px solid var(--border);padding:7px 10px;text-align:left;font-size:12.5px}
 .md th{background:#faf7f0;font-weight:700}
 .md hr{border:none;border-top:1px solid var(--border);margin:16px 0}
 .md img{max-width:100%;border-radius:8px}
 .cmdhelp{list-style:none}
.cmdhelp li{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px dashed #eee8dd;font-size:12.5px}
.cmdhelp li:last-child{border-bottom:none}
.cmdhelp .cc{font-family:ui-monospace,monospace;color:var(--accent);font-weight:600}
"""

# ── pill / severity helpers ────────────────────────────────────────────────────

def pill(state: str, label: str = "") -> str:
    s = str(state).lower()
    lbl = esc(label or state)
    dot = '<span class="dot"></span>'
    if s in ("running","active","connected","enabled","open","ready","paid","confirmed","hunting","reportable"):
        return f'<span class="pill green">{dot}{lbl}</span>'
    if s in ("idle","pending","history","drained","stopped","disabled","sleep"):
        return f'<span class="pill grey">{dot}{lbl}</span>'
    if s in ("cancelled","failed","dismissed","closed","attention","vuln","unreportable"):
        return f'<span class="pill red">{dot}{lbl}</span>'
    if s in ("starting","draining","review","needs-work","needs-review","investigation"):
        return f'<span class="pill amber">{dot}{lbl}</span>'
    if s in ("hackerone","private-program","submissions-open","intigriti","blue"):
        return f'<span class="pill blue">{dot}{lbl}</span>'
    return f'<span class="pill grey">{lbl}</span>'


def severity_pill(sev: str) -> str:
    sev = (sev or "").lower()
    cls_map = {
        "critical": "sev-critical", "high": "sev-high",
        "medium": "sev-medium", "low": "sev-low",
        "p0": "sev-critical", "p1": "sev-high",
        "p2": "sev-medium", "p3": "sev-low", "p4": "sev-low",
        "info": "sev-info", "informational": "sev-info",
    }
    cls = cls_map.get(sev, "sev-low")
    label = sev.upper() or "—"
    return f'<span class="pill {cls}">{esc(label)}</span>'


def self_hosted_badge(t: dict) -> str:
    return ' <span class="pill blue"><span class="dot"></span>SELF-HOSTED</span>' if t.get("self_hosted") else ""


def hunt_action_btn(t: dict) -> str:
    h = esc(t.get("handle", ""))
    stop = f'<button class="btn ghost small" onclick="hunterAction(\'stop\',\'{h}\',this)">{icon("pause", 12)} Stop</button>'
    start = f'<button class="btn small" onclick="hunterAction(\'start\',\'{h}\',this)">{icon("play", 12)} Start</button>'
    remove = f'<button class="btn ghost small" style="color:var(--accent);border-color:rgba(143,22,24,.3)" onclick="removeTarget(\'{h}\',this)" title="Remove from queue">{icon("trash", 12)}</button>'
    base = stop if t.get("status") == "active" else start
    return f'{base} {remove}'


# ── structural components ──────────────────────────────────────────────────────

def sidebar(active: str) -> str:
    att = need_attention()
    rows = []
    for sec, items in NAV:
        rows.append(f'<div class="sec">{esc(sec)}</div>')
        for key, label, ic in items:
            cls = " active" if key == active else ""
            badge = ""
            if key == "findings" and att > 0:
                badge = f'<span class="badge">{att}</span>'
            rows.append(
                f'<a class="{cls.strip()}" href="/v/{key}">'
                f'<span class="ic">{icon(ic)}</span>'
                f'<span>{esc(label)}</span>{badge}</a>'
            )
    return "".join(rows)


def _finding_modal_html() -> str:
    queue = get_queue()
    opts = "".join(
        f'<option value="{esc(t.get("handle",""))}">'
        f'{esc(t.get("name", t.get("handle","")))}</option>'
        for t in queue
    )
    if not opts:
        opts = '<option value="">— no programs queued —</option>'
    return (
        '<div class="modal-bg" id="findingmodal" onclick="if(event.target===this)this.style.display=\'none\'">'
        '<div class="modal">'
        '<div class="hd">' + icon("flag", 16) + ' Log Finding'
        '<span class="sp"></span>'
        '<button class="btn ghost small" onclick="document.getElementById(\'findingmodal\').style.display=\'none\'">✕</button>'
        '</div>'
        '<div class="bd">'
        '<div id="fi-err" class="small" style="color:var(--accent);display:none;margin-bottom:8px;padding:8px;background:#fae7e5;border-radius:6px"></div>'
        '<label>Program</label>'
        f'<select id="fi-prog"><option value="">— select program —</option>{opts}</select>'
        '<label>Title</label>'
        '<input id="fi-title" placeholder="e.g. Stored XSS in comment field">'
        '<label>Severity</label>'
        '<select id="fi-sev">'
        '<option value="critical">🔴 Critical</option>'
        '<option value="high">🟠 High</option>'
        '<option value="medium" selected>🟡 Medium</option>'
        '<option value="low">🟢 Low</option>'
        '<option value="info">🔵 Info</option>'
        '</select>'
        '<label>Endpoint / URL</label>'
        '<input id="fi-url" placeholder="https://target.com/api/comments">'
        '<label>Estimated Bounty ($)</label>'
        '<input id="fi-bounty" type="number" min="0" placeholder="e.g. 500">'
        '<label>Description / PoC</label>'
        '<textarea id="fi-desc" style="min-height:120px" placeholder="Steps to reproduce, impact, evidence…"></textarea>'
        '<div style="margin-top:12px;display:flex;gap:8px">'
        '<button class="btn" id="fi-submit" onclick="logFinding()">' + icon("send", 13) + ' Log Finding</button>'
        '<button class="btn ghost" onclick="document.getElementById(\'findingmodal\').style.display=\'none\'">Cancel</button>'
        '</div>'
        '</div></div></div>'
    )


def _msg_modal_html() -> str:
    return (
        '<div class="modal-bg" id="msgmodal" onclick="if(event.target===this)closeMsg()">'
        '<div class="modal" style="width:440px;max-width:90vw">'
        '<div class="hd">' + icon("info", 16) + ' <span id="msg-title">Notice</span>'
        '<span class="sp"></span>'
        '<button class="btn ghost small" onclick="closeMsg()">✕</button>'
        '</div>'
        '<div class="bd">'
        '<p id="msg-text" class="pread" style="margin:4px 0 16px"></p>'
        '<div style="text-align:right">'
        '<button class="btn" id="msg-ok" onclick="closeMsg()">OK</button>'
        '</div>'
        '</div></div></div>'
    )


def _confirm_modal_html() -> str:
    return (
        '<div class="modal-bg" id="confmodal" onclick="if(event.target===this)closeConfirm()">'
        '<div class="modal" style="width:400px;max-width:90vw">'
        '<div class="hd">' + icon("alert-triangle", 16) + ' <span id="conf-title">Confirm</span>'
        '<span class="sp"></span>'
        '<button class="btn ghost small" onclick="closeConfirm()">✕</button>'
        '</div>'
        '<div class="bd">'
        '<p id="conf-text" class="pread" style="margin:4px 0 16px"></p>'
        '<div style="text-align:right">'
        '<button class="btn ghost small" onclick="closeConfirm()">Cancel</button>'
        '<button class="btn" style="margin-left:8px" id="conf-ok" onclick="runConfirm()">OK</button>'
        '</div>'
        '</div></div></div>'
    )


def _task_modal_html() -> str:
    return (
        '<div class="modal-bg" id="taskmodal" onclick="if(event.target===this)this.style.display=\'none\'">'
        '<div class="modal">'
        '<div class="hd">' + icon("plus", 16) + ' New Task'
        '<span class="sp"></span>'
        '<button class="btn ghost small" onclick="document.getElementById(\'taskmodal\').style.display=\'none\'">✕</button>'
        '</div>'
        '<div class="bd">'
        '<div style="margin-bottom:16px">'
        '<div style="font-weight:700;font-size:13px;margin-bottom:6px">Add a self-hosted target</div>'
        '<p class="small muted" style="margin-bottom:10px">Not a bug bounty platform program — your own infra, a staging box, anything self-hosted. Adding it here means you are authorized to test it.</p>'
        '<div id="at-err" class="small" style="color:var(--accent);display:none;margin-bottom:8px;padding:8px;background:#fae7e5;border-radius:6px"></div>'
        '<label style="font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:4px">URL</label>'
        '<input id="at-url" placeholder="https://staging.example.internal" style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:13px;margin-bottom:8px;font-family:inherit">'
        '<label style="font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:4px">Display name (optional)</label>'
        '<input id="at-name" placeholder="My staging server" style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:13px;margin-bottom:8px;font-family:inherit">'
        '<label style="font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:4px">Notes (optional)</label>'
        '<textarea id="at-notes" placeholder="Notes for the hunter" style="width:100%;min-height:52px;padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:13px;margin-bottom:8px;font-family:inherit"></textarea>'
        '<button class="btn small" id="at-submit" onclick="addSelfHostedTarget()">' + icon("plus", 13) + ' Add target</button>'
        '</div>'
        '<p class="small muted" style="margin-bottom:10px;border-top:1px solid #eee8dd;padding-top:12px">Everything else is orchestrated from the terminal:</p>'
        '<ul class="cmdhelp">'
        f'<li><span class="cc">hackbot-workers start --slots {MAX_SLOTS}</span> <span class="muted">Launch worker pool</span></li>'
        '<li><span class="cc">hackbot-queue next</span> <span class="muted">Pick next ranked target</span></li>'
        '<li><span class="cc">hackbot-dashboard serve</span> <span class="muted">This dashboard</span></li>'
        '</ul>'
        '</div></div></div>'
    )


def topbar(active_q: str = "") -> str:
    att = need_attention()
    if att > 0:
        att_html = f'<span class="attention"><span class="n">{att}</span>{"need" if att != 1 else "needs"} attention</span>'
    else:
        att_html = '<span class="attention" style="background:#efebe4;color:#7a7266;border-color:#e6dfd2"><span class="n" style="background:#b9b0a2">0</span>all clear</span>'
    q = f' value="{esc(active_q)}"' if active_q else ""
    return f"""
<div class="topbar">
  <div class="searchbox">{icon('search', 16, 'glass')}
    <input id="globalsearch" placeholder="Search this view…"{q}></div>
  <div class="grow"></div>
  <div class="gridicon" title="Refresh" onclick="location.reload()">{icon('refresh-cw', 15)}</div>
  {att_html}
  <button class="btn ghost" onclick="document.getElementById('findingmodal').style.display='flex'">{icon('flag', 14)} Log Finding</button>
  <button class="btn" onclick="document.getElementById('taskmodal').style.display='flex'">{icon('plus', 14)} New Task</button>
</div>"""


def hero(title: str, sub: str = "", back: str = "", crown: str = "", raw: bool = False) -> str:
    t = f'<h1>{title if raw else esc(title)}</h1>'
    s = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    bl = f'<a class="back" href="{back}">{icon("arrow-left", 14)} Back</a>' if back else ""
    cr = crown or ""
    return f'<div class="hero"><div class="topline">{bl}{cr}</div>{t}{s}</div>'


_BASE_JS = """
/* ── global search filter ── */
(function(){
  var sb = document.getElementById('globalsearch');
  function doFilter() {
    var q = sb ? sb.value.toLowerCase() : '';
    document.querySelectorAll('[data-filter]').forEach(function(el) {
      if (el === sb) return;
      var hay = ((el.getAttribute('data-search') || '') + ' ' + (el.textContent || '')).toLowerCase();
      el.style.display = (q && hay.indexOf(q) === -1) ? 'none' : '';
    });
  }
  if (sb) sb.addEventListener('input', doFilter);
})();

/* ── tab switcher ── */
function showTab(group, id) {
  document.querySelectorAll('[data-tabgroup="' + group + '"]').forEach(function(t) {
    t.style.display = (t.id === id) ? '' : 'none';
  });
  document.querySelectorAll('[data-tabbtn="' + group + '"]').forEach(function(b) {
    b.classList.toggle('active', b.getAttribute('data-target') === id);
  });
}

/* ── message modal (replaces showMsg()) ── */
function closeMsg() {
  var m = document.getElementById('msgmodal');
  if (m) m.style.display = 'none';
}
function showMsg(msg, title) {
  var m = document.getElementById('msgmodal');
  if (!m) return;
  document.getElementById('msg-text').textContent = msg || '';
  var t = document.getElementById('msg-title');
  if (t) t.textContent = title || 'Notice';
  m.style.display = 'flex';
  var ok = document.getElementById('msg-ok');
  if (ok) ok.focus();
}
var __confirmCb = null;
function openConfirm(msg, title, cb) {
  var m = document.getElementById('confmodal');
  if (!m) return;
  document.getElementById('conf-text').textContent = msg || '';
  var t = document.getElementById('conf-title');
  if (t) t.textContent = title || 'Confirm';
  __confirmCb = (typeof cb === 'function') ? cb : null;
  m.style.display = 'flex';
  var ok = document.getElementById('conf-ok');
  if (ok) ok.focus();
}
function closeConfirm() {
  var m = document.getElementById('confmodal');
  if (m) m.style.display = 'none';
  __confirmCb = null;
}
function runConfirm() {
  var cb = __confirmCb;
  closeConfirm();
  if (cb) cb();
}

/* ── add self-hosted target ── */
async function addSelfHostedTarget() {
  var url   = document.getElementById('at-url').value.trim();
  var name  = document.getElementById('at-name').value.trim();
  var notes = document.getElementById('at-notes').value.trim();
  var err   = document.getElementById('at-err');
  var btn   = document.getElementById('at-submit');
  err.style.display = 'none';
  if (!url) { err.textContent = 'URL is required.'; err.style.display = ''; return; }
  btn.disabled = true; var orig = btn.textContent; btn.textContent = 'Adding…';
  try {
    var res  = await fetch('/api/targets/add', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,name,notes})});
    var data = await res.json();
    if (!res.ok || !data.ok) { err.textContent = data.message || 'Failed.'; err.style.display = ''; btn.disabled = false; btn.textContent = orig; return; }
    location.href = '/v/assets';
  } catch(e) { err.textContent = 'Request failed: ' + e; err.style.display = ''; btn.disabled = false; btn.textContent = orig; }
}

/* ── hunt start / stop ── */
async function hunterAction(action, handle, btn) {
  openConfirm((action === 'start' ? 'Start a hunt on ' : 'Stop the hunt on ') + handle + '?', 'Confirm', function() {
    doHunterAction(action, handle, btn);
  });
}
async function doHunterAction(action, handle, btn) {
  var orig = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = action === 'start' ? 'Starting…' : 'Stopping…'; }
  try {
    var res  = await fetch('/api/targets/' + action, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({handle})});
    var data = await res.json();
    if (!res.ok || !data.ok) { showMsg(data.message || ('Failed to ' + action + '.')); if(btn){btn.disabled=false;btn.textContent=orig;} return; }
    location.reload();
  } catch(e) { showMsg('Request failed: ' + e); if(btn){btn.disabled=false;btn.textContent=orig;} }
}

/* ── remove target from queue ── */
function removeTarget(handle, btn) {
  openConfirm('Remove ' + handle + ' from queue?', 'Remove Target', function() {
    doRemoveTarget(handle, btn);
  });
}
async function doRemoveTarget(handle, btn) {
  var orig = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Removing…'; }
  try {
    var res  = await fetch('/api/targets/remove', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({handle})});
    var data = await res.json();
    if (!res.ok || !data.ok) { showMsg(data.message || 'Failed to remove.'); if(btn){btn.disabled=false;btn.textContent=orig;} return; }
    location.reload();
  } catch(e) { showMsg('Request failed: ' + e); if(btn){btn.disabled=false;btn.textContent=orig;} }
}

/* ── log finding ── */
async function logFinding() {
  var prog   = document.getElementById('fi-prog').value.trim();
  var title  = document.getElementById('fi-title').value.trim();
  var url    = document.getElementById('fi-url').value.trim();
  var sev    = document.getElementById('fi-sev').value;
  var bounty = document.getElementById('fi-bounty').value;
  var desc   = document.getElementById('fi-desc').value.trim();
  var err    = document.getElementById('fi-err');
  var btn    = document.getElementById('fi-submit');
  err.style.display = 'none';
  if (!prog)  { err.textContent = 'Program is required.'; err.style.display = ''; return; }
  if (!title) { err.textContent = 'Title is required.';   err.style.display = ''; return; }
  btn.disabled = true; var orig = btn.textContent; btn.textContent = 'Logging…';
  try {
    var res  = await fetch('/api/findings/add', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({program:prog,title,url,severity:sev,bounty_est:parseFloat(bounty)||0,description:desc})});
    var data = await res.json();
    if (!res.ok || !data.ok) { err.textContent = data.message || 'Failed.'; err.style.display = ''; btn.disabled = false; btn.textContent = orig; return; }
    document.getElementById('findingmodal').style.display = 'none';
    location.href = '/v/findings';
  } catch(e) { err.textContent = 'Request failed: ' + e; err.style.display = ''; btn.disabled = false; btn.textContent = orig; }
}

/* ── set finding verdict ── */
async function setVerdict(idx, verdict, btns) {
  try {
    var res  = await fetch('/api/findings/verdict', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx,verdict})});
    var data = await res.json();
    if (!res.ok || !data.ok) { showMsg(data.message || 'Failed to update verdict.'); return; }
    btns.forEach(function(b) {
      b.classList.toggle('active', b.getAttribute('data-verdict') === verdict);
    });
    var row = document.getElementById('frow-' + idx);
    if (row) row.setAttribute('data-verdict', verdict);
  } catch(e) { showMsg('Request failed: ' + e); }
}

/* ── update finding status ── */
async function updateFindingStatus(idx, status, sel) {
  var orig = sel.value;
  try {
    var res  = await fetch('/api/findings/update', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx,status})});
    var data = await res.json();
    if (!res.ok || !data.ok) { showMsg(data.message || 'Failed.'); sel.value = orig; return; }
    sel.style.borderColor = 'var(--green)';
    setTimeout(function(){ sel.style.borderColor=''; }, 2000);
  } catch(e) { showMsg('Request failed: ' + e); sel.value = orig; }
}

/* ── toggle finding detail ── */
function toggleFinding(id) {
  var body = document.getElementById('fb-' + id);
  var icon = document.getElementById('fi-arr-' + id);
  if (!body) return;
  var open = body.style.display !== 'none';
  body.style.display = open ? 'none' : '';
  if (icon) icon.style.transform = open ? '' : 'rotate(90deg)';
}
"""


def page(active: str, hero_html: str, body: str, refresh: int = 0, extra_css: str = "", scripts: str = "") -> str:
    r = (f'<meta http-equiv="refresh" content="{refresh}">') if refresh else ""
    title = NAV_TITLES.get(active, "Operator")
    return (
        '<!doctype html>\n<html lang="en"><head>\n'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>Hackbot · {title}</title>{r}\n'
        f'<style>{CSS}{extra_css}</style></head>\n<body>\n'
        '<div class="layout">\n'
        '  <aside class="sidebar">\n'
        '    <div class="logo"><div class="mark">' + icon('compass', 18) + '</div>\n'
        f'      <div><div class="brand">HACKBOT</div><div class="sub">{esc(PLATFORM)} operator</div></div></div>\n'
        '    <nav class="nav">' + sidebar(active) + '</nav>\n'
        '  </aside>\n'
        '  <div class="console-tab" onclick="location.href=\'/console\'">CONSOLE</div>\n'
        '  <main class="main">\n'
        + topbar() + '\n'
        + hero_html + '\n'
        + '    <div class="content">' + body + '</div>\n'
        '  </main>\n</div>\n'
        + _finding_modal_html() + '\n'
        + _task_modal_html() + '\n'
        + _msg_modal_html() + '\n'
        + _confirm_modal_html() + '\n'
        '<script>\n' + _BASE_JS + '\n' + scripts + '\n</script>\n'
        '</body></html>'
    )
