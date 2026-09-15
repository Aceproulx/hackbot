#!/usr/bin/env python3
"""Hackbot web dashboard — Wild Hunt-style operator UI.

Thin bootstrap shim for the scripts/dashboard package (single-file module was
split into a package for maintainability). Keeps the original CLI contract so
scripts/dashboard.sh and the test harness keep calling this entry point:

    python3 scripts/dashboard-web.py [--port 7878] [--host 127.0.0.1]

Placeholders below are substituted at deploy time by scripts/deploy-web.sh, so
all functional code lives in dashboard/.py modules (also substituted).
"""
import argparse
import json
import os
import sys
import urllib.parse

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from dashboard.server import main as _main

if __name__ == "__main__":
    _main()