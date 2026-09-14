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
            data = route(path, qs)
        except Exception as e:
            data = (f'<!doctype html><html><body style="font-family:monospace;padding:30px"><h2>Dashboard error</h2>'
                    f'<pre>{esc(e.__class__.__name__)}: {esc(e)}</pre></body></html>').encode()
        if path.startswith("/api/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
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
