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
.console-bar .btn.ghost{background:#16191e;color:#d8dee4;border-color:#2c3138;box-shadow:none}
.console-bar .btn.ghost:hover{color:#fff;border-color:#3a414c;background:#1e222a}
.console-bar .btn.ghost:disabled{opacity:.35;cursor:not-allowed;background:#16191e;color:#555b66}

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
.breadcrumb{font-size:12px;color:var(--muted);margin-bottom:10px}
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
.md code{background:#efe9dd;border-radius:5px;padding:1px 6px;font-size:12px}
.md pre{background:#0d0f12;color:#d8dee4;padding:12px 14px;border-radius:10px;overflow-x:auto;margin:10px 0}
.md pre code{background:none;color:inherit;padding:0;font-size:12.5px;line-height:1.5}
.md table{border-collapse:collapse;margin:12px 0;width:100%}
.md th,.md td{border:1px solid var(--border);padding:7px 10px;text-align:left;font-size:12.5px}
.md th{background:#faf7f0;font-weight:700}
.md hr{border:none;border-top:1px solid var(--border);margin:16px 0}
.md img{max-width:100%;border-radius:8px}
"""
