"""Hackbot dashboard — style module.

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

CSS = """
:root {
  --canvas:#f7f4ee; --sidebar:#efe8dd; --card:#ffffff; --border:#e1d9cc;
  --ink:#242019; --muted:#8c8579; --accent:#8f1618; --accent-hi:#a4161a;
  --deep:#160d0c; --green:#1a7a43; --amber:#b96b00; --grey:#9a938a;
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

/* collapsed sidebar */
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
.nav a .ic{width:16px;text-align:center;font-size:14px;opacity:.85}
.ic-svg{vertical-align:-3px;display:inline-block;flex:none}
.nav a .ct{position:relative}
.badge{display:inline-flex;margin-left:auto;min-width:18px;height:18px;padding:0 5px;border-radius:9px;background:var(--accent);color:#fff;font-size:10.5px;font-weight:700;align-items:center;justify-content:center}
.badge.neutral{background:#d8d0c2;color:#6c6455}

/* console tab on sidebar right edge */
.console-tab{position:fixed;left:216px;top:47%;transform:rotate(180deg);writing-mode:vertical-rl;background:#111;color:#7ee787;font:600 11px/1 ui-monospace,monospace;letter-spacing:.22em;padding:12px 7px;border-radius:0 10px 10px 0;border:1px solid #000;cursor:pointer;z-index:60;box-shadow:0 2px 10px rgba(0,0,0,.35)}
.console-tab:hover{background:#1a1a1a;color:#a5f3b0}

/* top bar */
.topbar{position:sticky;top:0;z-index:40;display:flex;align-items:center;gap:14px;padding:12px 26px;background:rgba(247,244,238,.92);backdrop-filter:blur(6px);border-bottom:1px solid var(--border)}
.searchbox{flex:1;max-width:420px;position:relative}
.searchbox input{width:100%;padding:8px 12px 8px 34px;border:1px solid var(--border);border-radius:9px;background:#fff;font-size:13px;color:var(--ink);outline:none}
.searchbox input:focus{border-color:var(--accent)}
.searchbox .glass{position:absolute;left:11px;top:8px;color:var(--muted);font-size:13px}
.topbar .grow{flex:1}
.gridicon{background:#fff;border:1px solid var(--border);border-radius:8px;width:34px;height:34px;display:grid;place-items:center;color:#6c6455;font-size:14px;cursor:pointer}
.gridicon:hover{color:var(--accent)}
.attention{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:20px;background:rgba(143,22,24,.08);color:var(--accent);font-size:12.5px;font-weight:600;border:1px solid rgba(143,22,24,.18)}
.attention .n{background:var(--accent);color:#fff;border-radius:9px;min-width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;padding:0 5px;font-size:11px;font-weight:800}
.btn{background:var(--accent);color:#fff;border:none;border-radius:8px;padding:8px 16px;font:600 13px -apple-system,sans-serif;cursor:pointer;display:inline-flex;align-items:center;gap:7px;box-shadow:0 1px 3px rgba(143,22,24,.35);white-space:nowrap}
.btn:hover{background:var(--accent-hi);text-decoration:none}
.btn.ghost{background:#fff;color:#3d352b;border:1px solid var(--border);box-shadow:none}
.btn.ghost:hover{color:var(--accent);border-color:#d8c4b8}

.btn.danger{color:#b3261e;border-color:#e6b8b4;background:#fff}
.btn.danger:hover{color:#fff;background:#b3261e;border-color:#b3261e;box-shadow:0 1px 3px rgba(179,38,30,.4)}
.btn.small{padding:4px 10px;font-size:12px;border-radius:7px}

/* hero banner */
.hero{position:relative;padding:38px 34px 32px;color:#f6efe4;background:
  radial-gradient(1200px 500px at 85% -20%, rgba(176,58,46,.42), transparent 60%),
  radial-gradient(900px 420px at 0% 120%, rgba(60,20,20,.55), transparent 55%),
  linear-gradient(135deg,#170d0c 0%,#2a1310 48%,#3b1c12 100%);
  border-bottom:1px solid #0d0807;box-shadow:inset 0 -40px 60px -60px rgba(0,0,0,.5)}
.hero h1{font-size:30px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}
.hero .sub{color:#d9c9b8;font-size:13px;margin-top:6px;max-width:720px}
.hero .topline{display:flex;align-items:center;gap:14px;margin-bottom:14px}
.back{display:inline-flex;align-items:center;gap:6px;color:#e8d9c8;font-size:12.5px;font-weight:600;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);padding:5px 12px;border-radius:7px}
.back:hover{background:rgba(255,255,255,.16);color:#fff;text-decoration:none}

/* content */
.content{padding:22px 26px 60px}
.row{display:flex;gap:16px;flex-wrap:wrap}
.col{flex:1;min-width:0}
.col > .card{min-width:0}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);margin-bottom:18px;overflow:hidden}
.card .hd{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid #eee8dd;font-weight:700;font-size:13px;letter-spacing:.02em}
.card .hd .sp{flex:1}
.card .hd .hint{font-size:11.5px;color:var(--muted);font-weight:500}
.card .bd{padding:14px 16px}
.card.narrow{min-width:0}
.nw{white-space:nowrap}

/* stat cards */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-bottom:20px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 18px;box-shadow:var(--shadow);position:relative}
.stat .lab{font-size:11px;font-weight:700;letter-spacing:.1em;color:var(--muted);text-transform:uppercase}
.stat .val{font-size:26px;font-weight:800;margin-top:6px;letter-spacing:.01em}
.stat .sub{font-size:11.5px;color:var(--muted);margin-top:4px}

/* tables */
table{width:100%;min-width:0;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:8px 12px;color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:8px 12px;border-bottom:1px solid #f0eadf;vertical-align:top;overflow-wrap:anywhere}
tr:last-child td{border-bottom:none}
tbody tr:hover{background:#fbf8f3}
td.num{text-align:right;font-variant-numeric:tabular-nums}
th.num{text-align:right}

/* assets page: program name ellipsis, badges wrap to their own line */
.as-row td:first-child{white-space:normal}
.as-row td:first-child b{display:inline-block;max-width:min(260px,100%);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom}

/* findings tables: program column ellipsis on desktop (full value in title attr) */
#repcard td.mono,#evcard td.mono{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* dual timestamps: full shown on desktop, relative on mobile */
.ts-rel{display:none}

/* pills */
.pill{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:20px;font-size:11.5px;font-weight:600;white-space:nowrap}
.pill .dot{width:7px;height:7px;border-radius:50%;background:currentColor;flex:none}
.pill.green{background:#e5f4ea;color:var(--green)}
.pill.grey{background:#efebe4;color:#7a7266}
.pill.red{background:#fae7e5;color:var(--accent)}
.pill.amber{background:#fcf0dc;color:var(--amber)}
.pill.blue{background:#e7eefb;color:#2f5cb0}
.pill.gold{background:#faf0d9;color:#8a6a14}
.pill.mono{font-family:ui-monospace,monospace}

/* hunt cards */
.hgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}
.hcard{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:8px}
.hcard .t{font-weight:700;font-size:14px;display:flex;align-items:center;gap:8px;word-break:break-all}
.hcard .m{font-size:12px;color:var(--muted)}
.hcard .foot{display:flex;align-items:center;gap:8px;margin-top:2px}
.filter-item{transition:opacity .15s}
.hide-js{display:none !important}

/* tabs */
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--border);margin-bottom:16px;flex-wrap:wrap}
.tabs .t{padding:8px 14px;border-radius:9px 9px 0 0;font-weight:600;font-size:13px;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent}
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
.range-pills{display:flex;gap:6px;margin:10px 16px 0;flex-wrap:wrap}
.range-pills .r{padding:4px 12px;border-radius:14px;border:1px solid var(--border);font-size:11.5px;font-weight:600;color:var(--muted);cursor:pointer}
.range-pills .r.active{background:var(--accent);border-color:var(--accent);color:#fff}

/* console terminal */
.terminal{background:#0d0f12;color:#d8dee4;font:12.5px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;padding:16px 18px;border-radius:0 0 12px 12px;overflow-x:auto;white-space:pre-wrap;word-break:break-word}
.terminal .k{color:#e06c75}.terminal .g{color:#98c379}.terminal .c{color:#5c6370}.terminal .y{color:#e5c07b}.terminal .b{color:#61afef}
.console-bar{display:flex;align-items:center;gap:12px;padding:10px 16px;background:#0a0c0f;border-bottom:1px solid #23272d;color:#9aa4b0;font-size:12px}
.console-bar .title{font-weight:700;color:#e5eaf0;display:flex;align-items:center;gap:8px}
.console-bar select{background:#16191e;color:#d8dee4;border:1px solid #2c3138;border-radius:6px;padding:4px 8px;font-size:12px;font-family:inherit}
/* custom log dropdown */
.dd{position:relative;min-width:240px;max-width:340px}
.dd-btn{display:flex;align-items:center;gap:8px;width:100%;background:#16191e;color:#d8dee4;border:1px solid #2c3138;border-radius:6px;padding:4px 8px;font-size:12px;font-family:inherit;cursor:pointer;text-align:left}
.dd-btn:hover{border-color:#3a414c;background:#1e222a}
.dd-btn .dd-label{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dd-caret{color:#9aa4b0;display:flex}
.dd-menu{position:absolute;top:calc(100% + 4px);left:0;right:0;background:#16191e;border:1px solid #2c3138;border-radius:8px;max-height:340px;overflow-y:auto;z-index:60;display:none;box-shadow:0 10px 30px rgba(0,0,0,.5)}
.dd.open .dd-menu{display:block}
.dd-item{display:flex;align-items:center;gap:8px;padding:6px 10px;font-size:12px;color:#d8dee4;text-decoration:none;cursor:pointer;border-bottom:1px solid #1d2127}
.dd-item:last-child{border-bottom:none}
.dd-item:hover{background:#1e222a}
.dd-item.sel{background:#23282f}
.dd-item .dd-label{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:ui-monospace,monospace}
.dd-item .dd-ic{color:#9aa4b0;display:flex;flex-shrink:0}
.dd-item.watchdog .dd-ic{color:#e5c07b}
.dd-item.running{background:rgba(34,197,94,.08)}
.dd-item.running .dd-label{color:#4ade80;font-weight:600}
.dd-badge{display:inline-flex;align-items:center;gap:4px;font-size:9px;font-weight:800;letter-spacing:.06em;padding:2px 6px;border-radius:8px;background:rgba(34,197,94,.16);color:#4ade80;border:1px solid rgba(34,197,94,.35);flex-shrink:0}
.dd-dot{width:6px;height:6px;border-radius:50%;background:#22c55e;flex-shrink:0}
.console-bar .btn.ghost{background:#16191e;color:#d8dee4;border-color:#2c3138;box-shadow:none}
.console-bar .btn.ghost:hover{color:#fff;border-color:#3a414c;background:#1e222a}
.console-bar .btn.ghost:disabled{opacity:.35;cursor:not-allowed;background:#16191e;color:#555b66}
/* console page shell: fixed viewport height (dvh for mobile URL bar), no page scroll */
.console-page{height:100vh;height:100dvh;overflow:hidden;display:flex;flex-direction:column}
/* console page: standalone dark shell (unified neutral-900/950 palette) */
body.console-page{--bg:#0a0a0b;--fg:#d4d4d8;--border:#27272a;--muted:#71717a;background:#0a0a0b;color:#d4d4d8}
body.console-page .con-hdr{position:sticky;top:0;z-index:60;display:flex;align-items:center;gap:8px;height:52px;padding:0 12px;background:#09090b;border-bottom:1px solid #27272a;flex-shrink:0}
body.console-page .con-brand{display:inline-flex;align-items:center;gap:7px;color:#e4e4e7;font-weight:800;letter-spacing:.12em;font-size:12px;white-space:nowrap;flex-shrink:0}
body.console-page .con-brand .ic-svg{color:#22c55e}
body.console-page .con-hdr .dd{min-width:0;max-width:min(44vw,340px);flex:0 1 auto}
body.console-page .con-hdr .dd-btn{height:28px;padding:0 8px;border-radius:6px;background:#18181b;border-color:#3f3f46;font-size:12px;gap:6px}
body.console-page .con-hdr .dd-btn:hover{border-color:#52525b;background:#27272a}
body.console-page .con-hdr .dd-btn .dd-ic{color:#9ca3af}
body.console-page .con-ctl{display:flex;align-items:center;gap:6px;flex-shrink:0}
body.console-page .con-ctl select{background:#18181b;color:#d4d4d8;border:1px solid #3f3f46;border-radius:6px;padding:0 6px;height:28px;font-size:12px;font-family:inherit}
body.console-page .con-ctl .btn.ghost{height:28px;padding:0 8px;border-radius:6px;background:#18181b;color:#d4d4d8;border-color:#3f3f46;box-shadow:none;font-size:12px;gap:5px}
body.console-page .con-ctl .btn.ghost:hover{color:#fff;border-color:#52525b;background:#27272a}
body.console-page .con-ctl .pill{height:28px;padding:0 10px;font-size:11px;background:rgba(34,197,94,.12);color:#4ade80;border:1px solid rgba(34,197,94,.3)}
body.console-page .con-ctl .pill.amber{background:rgba(245,158,11,.12);color:#fbbf24;border-color:rgba(245,158,11,.3)}
body.console-page .activity-indicator{font-size:11px;font-weight:600;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
body.console-page .console-body{flex:1;min-height:0;display:flex;flex-direction:column;padding:0;overflow:hidden}
body.console-page .terminal{flex:1;min-height:0;border-radius:0;padding:12px 14px}
body.console-page .console-bar.input-bar{padding:8px 12px;border-top:1px solid #27272a;border-bottom:none}

/* modal + toasts */
.modal-bg{position:fixed;inset:0;background:rgba(20,12,10,.45);z-index:100;display:none;align-items:flex-start;justify-content:center;padding-top:9vh}
.modal{background:#fff;border-radius:14px;width:520px;max-width:94vw;box-shadow:0 20px 60px rgba(0,0,0,.35);overflow:hidden}
.modal .hd{padding:14px 18px;background:var(--sidebar);border-bottom:1px solid var(--border);font-weight:700;display:flex;align-items:center}
.modal .bd{padding:16px 18px;max-height:60vh;overflow-y:auto}
.modal .bd code{display:block;background:#0d0f12;color:#d8dee4;padding:9px 12px;border-radius:8px;font-size:12px;margin:6px 0 14px;white-space:pre-wrap}
.cmdhelp{list-style:none}
.cmdhelp li{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px dashed #eee8dd;font-size:12.5px}
.cmdhelp li:last-child{border-bottom:none}
.cmdhelp .cc{font-family:ui-monospace,monospace;color:var(--accent);font-weight:600}

/* modal form fields */
.lbl{display:block;font-size:10px;font-weight:700;letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin:10px 0 4px}
.fld{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:13px;font-family:inherit;background:#fff;box-sizing:border-box}
.fld:focus{outline:none;border-color:var(--accent)}

/* topology relationship graph */
.graph{margin-bottom:16px;overflow:hidden;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px}
.graph svg{display:block;width:100%;height:auto}
.g-worker rect{fill:#eef0f1}.g-worker text{fill:#3d352b}
.g-run rect{fill:rgba(143,22,24,.08);stroke:var(--accent);stroke-width:1}.g-run text{fill:#3d352b}
.g-find rect{fill:var(--sidebar);stroke:var(--border);stroke-width:1}.g-find text{fill:#3d352b}
.graph line{stroke:var(--border);stroke-width:1.4}
.graph .role{font:700 10px ui-monospace,monospace;letter-spacing:.08em;fill:#8c8579}

/* bulk queue ops */
.qsel{accent-color:var(--accent);width:15px;height:15px;cursor:pointer}

/* empty state */
.empty{text-align:center;color:var(--muted);padding:46px 20px}
.empty .ic{font-size:34px;opacity:.5;margin-bottom:10px}
.empty .t{font-weight:600;color:#7a7266}

/* filters row */
.fbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.fbar .f{padding:5px 12px;border:1px solid var(--border);border-radius:8px;background:#fff;font-size:12px;color:#555;cursor:pointer}
.fbar .f.active{color:var(--accent);border-color:var(--accent);background:rgba(143,22,24,.05);font-weight:600}

/* misc */
.mt{margin-top:14px}.right{text-align:right}
.muted{color:var(--muted)}.small{font-size:12px}
.dot-u{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--accent);vertical-align:middle}
.unread-tag{color:var(--accent);font-weight:700;font-size:11px;letter-spacing:.07em}
tbody tr.unread td{background:rgba(143,22,24,.03)}
code.inline{background:#efe9dd;border-radius:5px;padding:1px 6px;font-size:12px}
.pread{white-space:pre-wrap;word-break:break-word;font-size:12.5px;line-height:1.5}
.statline{display:flex;gap:8px;flex-wrap:wrap;font-size:12px;color:var(--muted)}
.breadcrumb{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-bottom:10px}
.breadcrumb a{color:var(--muted)}
.breadcrumb .sp{flex:1}
.breadcrumb .bcsep{font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:10.5px;color:#9a9186;display:inline-flex;align-items:center;gap:4px}
.bc-btn{display:inline-flex;align-items:center;padding:3px 10px;border-radius:7px;border:1px solid var(--border);background:#fff;font:600 11.5px -apple-system,sans-serif;color:#555;cursor:pointer;white-space:nowrap}
.bc-btn:hover{border-color:#c9bfae;color:var(--accent)}
.bc-btn:disabled{opacity:.4;cursor:not-allowed}
.bc-btn.active{font-weight:700}
.bc-btn.mk-valid.active{background:#ECFDF5;border-color:#10B981;color:#047857}
.bc-btn.mk-duplicate.active{background:#EEF2FF;border-color:#6366F1;color:#4338CA}
.bc-btn.mk-unreportable.active{background:#F1F5F9;border-color:#94a3b8;color:#475569}
.bc-btn.mk-underreview.active{background:#FFFBEB;border-color:#F59E0B;color:#B45309}
.mk{display:inline-flex;align-items:center;gap:6px;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap}
.mk-valid{background:#ECFDF5;color:#047857;border:1px solid #a7f3d0}
.mk-duplicate{background:#EEF2FF;color:#4338CA;border:1px solid #c7d2fe}
.mk-unreportable{background:#F1F5F9;color:#475569;border:1px solid #cbd5e1}
.mk-underreview{background:#FFFBEB;color:#B45309;border:1px solid #fde68a}
.card.mk-bg-valid{background:#ECFDF5;border-color:#a7f3d0}
.card.mk-bg-duplicate{background:#EEF2FF;border-color:#c7d2fe}
.card.mk-bg-unreportable{background:#F1F5F9;border-color:#cbd5e1}
.card.mk-bg-underreview{background:#FFFBEB;border-color:#fde68a}
.fbar.fbar-card{padding:10px 16px;border-bottom:1px solid #eee8dd;margin:0}
.fbar .flbl{font-size:10.5px;font-weight:700;letter-spacing:.08em;color:var(--muted);text-transform:uppercase}
.fbar .sp{flex:1}
.pager{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:10px 16px;border-top:1px solid #eee8dd}
.pager .pg-info{font-size:12px;color:var(--muted);margin-right:auto}
.pager .pg-btn{padding:4px 10px;border:1px solid var(--border);border-radius:7px;background:#fff;font-size:12px;color:#555;cursor:pointer;min-width:30px;text-align:center;font-family:inherit}
.pager .pg-btn:hover:not(:disabled){border-color:var(--accent);color:var(--accent)}
.pager .pg-btn.active{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
.pager .pg-btn:disabled{opacity:.4;cursor:not-allowed}
.pager .pg-ell{color:var(--muted);padding:0 2px;font-size:12px}
.node-link{color:#3d352b;font-weight:600}

/* rendered markdown (.md blocks — reports, features, session-state) */
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
.md a:hover{border-bottom-color:#155e8f}
.md strong{font-weight:700}
.md blockquote{margin:10px 0;padding:2px 14px;border-left:3px solid var(--border);color:var(--muted);background:#faf7f0}
.md code{background:#efe9dd;border-radius:5px;padding:1px 6px;font-size:12px;word-break:break-word}
.md pre{background:#0d0f12;color:#d8dee4;padding:12px 14px;border-radius:10px;overflow-x:auto;margin:10px 0}
.md pre code{background:none;color:inherit;padding:0;font-size:12.5px;line-height:1.5;word-break:normal}
.md li>ul,.md li>ol{margin:4px 0}
.md li>ul>li,.md li>ol>li{margin:2px 0}
.md table{border-collapse:collapse;margin:12px 0;width:100%}
.md th,.md td{border:1px solid var(--border);padding:7px 10px;text-align:left;font-size:12.5px}
.md th{background:#faf7f0;font-weight:700}
.md hr{border:none;border-top:1px solid var(--border);margin:16px 0}
.md img{max-width:100%;border-radius:8px}

/* evidence popup + side panel */
.ev-hero-btn{position:absolute;top:20px;right:22px;display:inline-flex;align-items:center;gap:7px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.28);color:#f6efe4;border-radius:9px;padding:8px 14px;font-size:13px;font-weight:600;cursor:pointer}
.cv-toggle{position:fixed;right:22px;bottom:24px;z-index:200;display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;background:#fff;border:1px solid #d8d3c9;color:#4c5664;border-radius:50%;padding:0;cursor:pointer;box-shadow:0 4px 16px rgba(30,34,45,.18);transition:transform .12s linear,box-shadow .12s linear,background .12s linear,color .12s linear,border-color .12s linear}
.cv-toggle:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(30,34,45,.24);color:#1e2430;border-color:#b8c0cc}
.cv-toggle:active{transform:translateY(0)}
.cv-toggle.on{background:#e9f5ee;border-color:#7cc59a;color:#1a7a43;box-shadow:0 4px 16px rgba(26,122,67,.22)}
.cv-toggle.on:hover{background:#def0e5;border-color:#63b885;color:#136235;box-shadow:0 6px 20px rgba(26,122,67,.3)}
.cv-wrap{position:relative}
body:not(.cv-on) .cv-ctl{display:none}
body:not(.cv-on) .cv-out{display:none}
body.cv-on .cv-wrap{background:#e6e8ec;border:2px solid var(--green);border-radius:10px;padding:10px 12px 12px;margin:10px 0;box-shadow:0 1px 4px rgba(20,25,35,.06)}
body.cv-on .cv-wrap>pre{background:#23272e;color:#dbe1e9;border-radius:8px;padding:12px;overflow-x:auto}
.cv-ctl{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;padding-bottom:10px;border-bottom:1px dashed rgba(30,35,45,.18)}
.cv-chip{display:inline-flex;align-items:center;gap:8px;background:#fff;border:1px solid #c8cdd6;border-radius:8px;padding:4px 9px 4px 5px;font-size:12px;color:#2a3039;cursor:pointer;font-family:inherit}
.cv-chip:hover{border-color:#71849e}
.cv-chip .tri{color:#fff;background:#3a4861;border-radius:6px;width:19px;height:19px;display:inline-grid;place-items:center;font-size:9px}
.cv-chip.ok .tri{background:var(--green)}
.cv-chip.bad .tri{background:#b3261e}
.cv-chip.warn .tri{background:var(--amber)}
.cv-ctl .cv-hint{margin-left:auto;align-self:center;font-size:11px;color:#7d8796}
.cv-out{margin-top:10px}
.cv-out .cv-st{font-size:11.5px;font-weight:600;margin-bottom:7px;color:#66707c}
.cv-out .cv-st.ok{color:var(--green)}
.cv-out .cv-st.bad{color:#b3261e}
.cv-out .cv-st.warn{color:var(--amber)}
.cv-out pre{background:#23272e;color:#dbe1e9;border:2px solid transparent;border-radius:8px;padding:12px;font-size:12px;line-height:1.5;max-height:380px;overflow:auto;white-space:pre-wrap;word-break:break-word}
body.cv-on .cv-out pre{border-color:var(--green)}
.ev-hero-btn:hover{background:rgba(255,255,255,.22)}
.ev-hero-btn .evn{font-size:10.5px;font-weight:700;background:rgba(255,255,255,.22);border-radius:9px;padding:1px 7px}
.ev-backdrop{position:fixed;inset:0;background:rgba(30,22,15,.48);z-index:80;display:none;align-items:center;justify-content:center}
.ev-backdrop.open{display:flex}
.ev-modal{background:#fff;border-radius:14px;width:800px;max-width:95vw;max-height:82vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,.35)}
.ev-modal .hd,.ev-panel .hd{display:flex;align-items:center;gap:12px;padding:16px 20px;border-bottom:1px solid #eee8dd;font-weight:700;font-size:13px;letter-spacing:.02em}
.ev-modal .hd .ev-title,.ev-panel .hd .ev-title{display:inline-flex;align-items:center;gap:8px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ev-modal .hd .ev-x,.ev-panel .hd .ev-x{margin-left:auto}
.ev-x{background:none;border:none;font-size:22px;line-height:1;color:var(--muted);cursor:pointer;padding:0 4px}
.ev-x:hover{color:var(--accent)}
.ev-scroll{overflow-y:auto;padding:6px 20px 22px}
.ev-load{padding:40px 0;text-align:center;color:var(--muted);font-size:12.5px}
.ev-subhead{display:flex;align-items:center;gap:10px;margin:4px 0 12px;font-size:12.5px}
.ev-subhead b{margin-right:auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ev-subhead .btn{padding:5px 10px;font-size:12px}
.ev-pack{position:relative;border:1px solid var(--border);border-radius:10px;background:#fff;overflow:hidden}
.ev-pack:hover{border-color:var(--accent);box-shadow:0 2px 10px rgba(143,22,24,.08)}
.ev-pack .ev-open{display:block;width:100%;text-align:left;background:none;border:none;padding:13px 14px;cursor:pointer;color:var(--ink)}
.ev-pack .ev-open:hover{background:#faf7f0}
.ev-pack .pkg{display:block;font-size:13px;font-weight:700;color:#2c231c;word-break:break-word;padding-right:22px}
.ev-pack .meta{display:block;font-size:11.5px;color:var(--muted);margin-top:4px}
.ev-pg{position:absolute;top:12px;right:12px;color:var(--muted);text-decoration:none;font-size:13px;z-index:2}
.ev-pg:hover{color:var(--accent)}
.ev-file{display:flex;align-items:center;gap:10px;width:100%;text-align:left;border:1px solid var(--border);border-radius:8px;background:#fff;padding:10px 12px;margin-bottom:8px;cursor:pointer;color:var(--ink);font-size:12.5px}
.ev-file:hover{border-color:var(--accent)}
.ev-file .nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:ui-monospace,monospace;font-size:12px}
.ev-file .sz{color:var(--muted);font-size:11px;white-space:nowrap}
.ev-file .sz.tag{background:#efe9dd;border-radius:4px;padding:2px 6px}
.ev-file .sz.tag.img{background:#e8f0fe;color:#1a73e8;border:1px solid #c2d7fa}
.ev-body{font-size:12.5px;line-height:1.55;white-space:pre-wrap;word-break:break-word;background:#faf7f0;border:1px solid var(--border);border-radius:10px;padding:14px;margin-top:4px;font-family:ui-monospace,monospace}
.ev-img-wrap{display:flex;flex-direction:column;gap:10px;margin-top:8px}
.ev-img-bar{display:flex;align-items:center;gap:8px;padding:7px 10px;background:#f7f4ee;border:1px solid #e5dfd5;border-radius:8px;font-size:12px}
.ev-img-box{background:#181b22;border:1px solid #282d38;border-radius:8px;padding:14px;display:flex;align-items:center;justify-content:center;overflow:auto;max-height:75vh}
.ev-img{max-width:100%;height:auto;border-radius:4px;box-shadow:0 4px 16px rgba(0,0,0,.45);cursor:zoom-in;display:block}
.ev-panel{position:fixed;top:0;right:0;bottom:0;width:440px;background:#fff;border-left:1px solid var(--border);box-shadow:-12px 0 40px rgba(0,0,0,.18);z-index:90;display:flex;flex-direction:column;transform:translateX(100%);transition:transform .22s ease}
.ev-panel.open{transform:translateX(0)}
.ev-panel .grid{grid-template-columns:1fr}
.layout.ev-side .main{margin-right:440px;transition:margin-right .22s ease}
@keyframes evfade{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.ev-backdrop.open .ev-modal{animation:evfade .16s ease}
@media (max-width:900px){.ev-panel{width:92vw}.layout.ev-side .main{margin-right:0}}

/* per-command collapsible blocks in terminal output */
details.clp-cmd{margin:1px 0}
details.clp-cmd>summary{display:flex;align-items:flex-start;gap:7px;padding:2px 6px;cursor:pointer;list-style:none;user-select:none;font-size:12px;line-height:1.5;border-radius:5px;color:#9ba6b4;font-family:ui-monospace,monospace}
details.clp-cmd>summary::-webkit-details-marker{display:none}
details.clp-cmd>summary:hover{background:rgba(255,255,255,.07);color:#d8dee4}
details.clp-cmd>summary .chev{transition:transform .15s ease;flex-shrink:0;color:#5c6370;margin-top:3px}
details.clp-cmd[open]>summary .chev{transform:rotate(90deg)}
details.clp-cmd>summary .cmd{flex:1;min-width:0;word-break:break-word;white-space:pre-wrap}
details.clp-cmd>summary .hint{font-size:10.5px;opacity:.5;flex-shrink:0;margin-left:8px}
details.clp-cmd .clp-out{padding:4px 8px 8px 26px;border-left:1px solid rgba(255,255,255,.09);margin-left:9px;white-space:pre-wrap;word-break:break-word;display:-webkit-box;-webkit-line-clamp:5;-webkit-box-orient:vertical;overflow:hidden;cursor:pointer}
details.clp-cmd.expanded .clp-out{-webkit-line-clamp:unset;display:block;overflow:visible}
details.clp-cmd .clp-more{display:block;margin:2px 0 6px 26px;padding:2px 8px;border:none;background:none;color:#5c6370;font:italic 11px/1.4 ui-monospace,monospace;cursor:pointer;border-radius:4px}
details.clp-cmd .clp-more:hover{color:#9ba6b4;background:rgba(255,255,255,.06)}
details.clp-cmd.expanded .clp-more{display:none}

/* ---------- responsive / mobile ---------- */
.menu-btn{display:none}
.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
.side-overlay{display:none}

@media (max-width:768px){
  /* hamburger */
  .menu-btn{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;flex-shrink:0;border:1px solid var(--border);border-radius:9px;background:#fff;color:#3d352b;cursor:pointer;padding:0}
  .menu-btn:hover{color:var(--accent);border-color:#d8c4b8}

  /* sidebar -> off-canvas drawer */
  .sidebar{width:264px !important;transform:translateX(-100%);transition:transform .22s ease;z-index:70;box-shadow:12px 0 40px rgba(20,12,10,.25)}
  .layout.mobile-open .sidebar{transform:translateX(0)}
  .layout.collapsed .sidebar{width:264px !important}
  .layout.collapsed.mobile-open .sidebar{transform:translateX(0)}
  .layout.collapsed .logo{justify-content:flex-start;padding:18px 16px 14px}
  .layout.collapsed .logo>div:last-child{display:block}
  .layout.collapsed .nav{padding:12px 8px 120px}
  .layout.collapsed .nav .sec{height:auto;margin:16px 4px 6px;overflow:visible;opacity:1}
  .layout.collapsed .nav a{justify-content:flex-start;gap:9px;padding:7px 10px}
  .layout.collapsed .nav a .ic{display:block;margin:0}
  .layout.collapsed .nav a>span:not(.ic):not(.badge){display:inline}
  .layout.collapsed .nav a .badge{position:static;margin-left:auto;min-width:18px;height:18px;padding:0 5px;border-radius:9px;font-size:10.5px}
  .layout.collapsed .nav a.active::before{left:-8px;width:3px}
  .collapse-btn{display:none}

  /* main full width */
  .main{margin-left:0 !important}
  .layout.collapsed .main{margin-left:0 !important}

  /* drawer backdrop */
  .side-overlay{position:fixed;inset:0;background:rgba(20,12,10,.42);z-index:65;display:none}
  .layout.mobile-open .side-overlay{display:block}

  /* console tab hidden on phones */
  .console-tab{display:none}

  /* topbar */
  .topbar{flex-wrap:wrap;gap:8px;padding:10px 12px}
  .searchbox{flex:1 1 100%;max-width:none;order:-1}
  .topbar .grow{display:none}
  .gridicon{display:none}
  .attention{font-size:11px;padding:4px 9px}
  .btn{padding:6px 12px;font-size:12px;gap:6px}

  /* hero */
  .hero{padding:24px 16px 20px}
  .hero h1{font-size:21px}
  .hero .sub{font-size:12px}
  .ev-hero-btn{position:static;display:inline-flex;margin-top:12px}

  /* content */
  .content{padding:16px 12px 44px}

  /* columns stack */
  .row{gap:12px}
  .col{flex:1 1 100%}

  /* stat cards */
  .stats{grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}
  .stat{padding:12px 14px}
  .stat .val{font-size:22px}

  /* hunt grid -> single column */
  .hgrid{grid-template-columns:1fr;gap:10px}

  /* tables scroll horizontally inside cards */
  .card{overflow-x:auto}
  .card .hd{position:sticky;left:0;background:var(--card)}
  table{font-size:12px}
  th,td{padding:6px 8px}

  /* modal form stacks */
  .modal .row{gap:0}
  .modal .col{flex:1 1 100%}
  .modal .bd{padding:14px}

  /* donut */
  .donut{width:120px;height:120px}
  .donut .core{inset:18px}
  .donut .core .big{font-size:18px}
  .legend{min-width:0}

  /* tabs scroll instead of wrap */
  .tabs{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch}
  .tabs .t{white-space:nowrap;flex-shrink:0}

  /* evidence panel full width */
  .ev-panel{width:100vw}

  /* terminal */
  .terminal{padding:12px 14px;font-size:12px}

  /* fbar -> horizontally scrollable chip row (no wrap) */
  .fbar{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;gap:8px}
  .fbar::-webkit-scrollbar{display:none}
  .fbar .f{flex:0 0 auto;white-space:nowrap;min-height:40px;padding:4px 12px;font-size:11.5px}
  .fbar .flbl{flex:0 0 auto}
  .fbar .sp{display:none}

  /* consistent touch targets for action buttons */
  .btn{min-height:44px}

  /* dual timestamps: relative on mobile */
  .ts-full{display:none}
  .ts-rel{display:inline}

  /* findings: reports table -> cards */
  #repcard thead{display:none}
  #repcard tbody tr{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;padding:12px 14px;margin:10px 12px;border:1px solid var(--border);border-radius:12px;background:var(--card);box-shadow:0 1px 2px rgba(20,12,10,.05)}
  #repcard tbody tr.unread{border-left:3px solid var(--accent)}
  #repcard tbody tr:hover{background:var(--card)}
  #repcard tbody tr td{border:none;padding:0}
  #repcard tbody td:nth-child(1){order:0;flex:0 0 auto}
  #repcard tbody td:nth-child(3){order:1;flex:1 1 auto;min-width:0}
  #repcard tbody td:nth-child(3) a{font-size:14px;font-weight:600;line-height:1.35;word-break:break-word;display:block}
  #repcard tbody td:nth-child(6){order:2;flex:0 0 auto}
  #repcard tbody td:nth-child(2){order:3;flex:1 1 100%;white-space:normal;overflow:visible;text-overflow:clip;max-width:none}
  #repcard tbody td:nth-child(5){order:4;flex:0 0 auto}
  #repcard tbody td:nth-child(4){order:5;flex:0 0 auto}
  #repcard tbody td[data-label]:not(:nth-child(3)):not(:nth-child(6))::before{content:attr(data-label);display:block;font-size:9.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:2px}

  /* findings: evidence table -> cards */
  #evcard thead{display:none}
  #evcard tbody tr{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;padding:12px 14px;margin:10px 12px;border:1px solid var(--border);border-radius:12px;background:var(--card)}
  #evcard tbody tr:hover{background:var(--card)}
  #evcard tbody tr td{border:none;padding:0}
  #evcard tbody td:nth-child(2){order:1;flex:1 1 auto;min-width:0;word-break:break-word;font-size:13px;font-weight:600}
  #evcard tbody td:nth-child(1){order:2;flex:1 1 100%;white-space:normal;overflow:visible;text-overflow:clip;max-width:none}
  #evcard tbody td:nth-child(3){order:3;flex:0 0 auto}
  #evcard tbody td[data-label]:not(:nth-child(2))::before{content:attr(data-label);display:block;font-size:9.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:2px}

  /* console page: single-row header, controls scroll horizontally */
  body.console-page .con-hdr{height:52px;padding:0 8px;gap:6px}
  body.console-page .con-brand span{display:none}
  body.console-page .con-hdr>span[style]{display:none}
  body.console-page .con-hdr .dd{flex:1 1 auto;min-width:110px;max-width:none}
  body.console-page .con-ctl{flex:0 1 auto;min-width:0;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
  body.console-page .con-ctl::-webkit-scrollbar{display:none}
  body.console-page .con-ctl>*{flex:0 0 auto}
  body.console-page .con-ctl select,body.console-page .con-ctl .btn.ghost,body.console-page .con-ctl .pill{height:32px;min-height:0}
  /* terminal fills remaining height, wraps wide lines, scrolls internally */
  #termlog{height:auto !important;flex:1 1 auto;min-height:140px;font-size:12px;line-height:1.45;padding:8px 10px}
  /* input bar pinned to bottom, safe-area inset for mobile browsers */
  body.console-page .console-bar.input-bar{padding:6px 8px calc(6px + env(safe-area-inset-bottom))}
  body.console-page .console-bar.input-bar input{min-width:0}
  body.console-page .console-bar.input-bar .btn.ghost{min-height:44px}
}
"""
