"""Hackbot dashboard — server module.

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

# UNRESOLVED: BaseHTTPRequestHandler (same-module or missing)
# UNRESOLVED: Handler (same-module or missing)
# UNRESOLVED: ThreadingHTTPServer (same-module or missing)
from .util import esc
# UNRESOLVED: json (same-module or missing)
# UNRESOLVED: parse_qs (same-module or missing)
from .router import route
from .router import route_post

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path, _, qraw = self.path.partition("?")
        from urllib.parse import parse_qs
        qs = parse_qs(qraw)
        try:
            res = route(path, qs)
        except Exception as e:
            res = (f'<!doctype html><html><body style="font-family:monospace;padding:30px"><h2>Dashboard error</h2>'
                    f'<pre>{esc(e.__class__.__name__)}: {esc(e)}</pre></body></html>').encode()
        status = 200
        ctype = "application/json" if path.startswith("/api/") else "text/html; charset=utf-8"
        extra_headers = {}
        if isinstance(res, tuple):
            data = res[0]
            if len(res) > 1 and res[1] is not None:
                status = res[1]
            if len(res) > 2 and res[2] is not None:
                ctype = res[2]
            if len(res) > 3 and res[3] is not None:
                extra_headers = res[3] if isinstance(res[3], dict) else {"Content-Disposition": res[3]}
        else:
            data = res
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for hk, hv in extra_headers.items():
            self.send_header(hk, hv)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path, _, qraw = self.path.partition("?")
        from urllib.parse import parse_qs
        qs = parse_qs(qraw)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            body = raw.decode("utf-8", errors="replace")
            data, status = route_post(path, qs, body)
        except Exception as e:
            data = json.dumps({"ok": False, "message": f"{e.__class__.__name__}: {e}"}).encode()
            status = 500
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

def main():
    ap = argparse.ArgumentParser(description="Hackbot web dashboard")
    ap.add_argument("--port", type=int, default=7878)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"Hackbot dashboard → http://{a.host}:{a.port}/", flush=True)
    srv.serve_forever()
