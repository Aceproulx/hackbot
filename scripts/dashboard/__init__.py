"""Hackbot web dashboard — package split of scripts/dashboard-web.py.

Dependency order (import-safe, no cycles):

    config < util < {ansi, icons, style, state}
    layout < views < {console, router}
    actions < router < server
"""

__version__ = "1.0.0"