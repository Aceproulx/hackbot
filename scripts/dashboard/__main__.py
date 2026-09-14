#!/usr/bin/env python3
"""Run the hackbot dashboard from the package directory:

    python3 scripts/dashboard --port 7878
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from dashboard.server import main

if __name__ == "__main__":
    main()