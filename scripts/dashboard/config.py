"""config.py — all paths and runtime config for the Hackbot dashboard."""
import json
import os
import shutil

HOME = os.path.expanduser("~")
MISC = os.environ.get("HACKBOT_MISC", "/home/aceos/Projects/hackbot-misc")
MISC = os.path.expanduser(MISC)
HUNTS_ROOT = os.path.expanduser("~/Projects/hackbot/hunts")
SESSIONS_ROOT = os.path.join(HUNTS_ROOT, "sessions")
CONFIG_PATH = os.path.expanduser("~/.hackbot/config.json")

QUEUE_FILE     = os.path.join(MISC, "target-queue.json")
POOL_DIR       = os.path.join(MISC, "worker-pool")
POOL_FILE      = os.path.join(POOL_DIR, "pool.json")
WATCHDOG_REPORTS_DIR = os.path.join(POOL_DIR, "watchdog-reports")
WATCHDOG_LOG   = os.path.join(POOL_DIR, "watchdog.log")
WATCHDOG_PID   = os.path.join(POOL_DIR, "watchdog.pid")
FINDINGS_FILE  = os.path.join(MISC, "findings.jsonl")
YWH_TRIAGER_FILE = os.path.join(MISC, "ywh-triager.jsonl")
YWH_VERDICTS_FILE = os.path.join(MISC, "ywh-verdicts.json")
README_FILE    = os.path.join(MISC, "read-reports.json")
MARKS_FILE     = os.path.join(MISC, "report-marks.json")
FAVOURITES_FILE = os.path.join(MISC, "program-favourites.json")
REPORTS_DIR    = os.path.join(MISC, "reports")
SKILL_DIRS = [
    os.path.expanduser("~/.config/opencode/skill"),
    os.path.expanduser("~/.agents/skills"),
    os.path.expanduser("~/.gemini/skills"),
]

def _is_rendered(path: str) -> bool:
    """Skip source templates that still contain unrendered {{...}} placeholders.

    The repo copies of worker-pool.sh / queue-manager.sh are install templates
    ({{HACKBOT_MISC_DIR}}, {{EMAIL_BASE}}, ...). Running them unrendered points
    at literal paths like '{{HACKBOT_MISC_DIR}}/target-queue.json' and breaks
    every Start/Stop action. Prefer the installed, rendered copies.
    """
    try:
        with open(path) as fh:
            return "{{" not in fh.read()
    except Exception:
        return False


_QUEUE_MANAGER_CANDIDATES = [
    os.path.expanduser("~/.local/bin/hackbot-queue"),
    shutil.which("hackbot-queue") or "",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "queue-manager.sh"),
]
QUEUE_MANAGER = next(
    (p for p in _QUEUE_MANAGER_CANDIDATES if p and os.path.isfile(p) and _is_rendered(p)),
    None,
)

_WORKER_POOL_CANDIDATES = [
    os.path.expanduser("~/.local/bin/hackbot-workers"),
    shutil.which("hackbot-workers") or "",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "worker-pool.sh"),
]
WORKER_POOL = next(
    (p for p in _WORKER_POOL_CANDIDATES if p and os.path.isfile(p) and _is_rendered(p)),
    None,
)


def load_config() -> dict:
    try:
        with open(CONFIG_PATH) as fh:
            return json.load(fh)
    except Exception:
        return {}


def cfg_dir(cfg: dict, key: str, default: str) -> str:
    v = cfg.get(key) or default
    return os.path.expanduser(v)


CONFIG        = load_config()
PAYLOADS_DIR  = cfg_dir(CONFIG, "payloads_dir",     "/home/aceos/Projects/payloads/coffinxp-payloads")
HACKBOT_MISC  = cfg_dir(CONFIG, "hackbot_misc_dir",  MISC)
SESSIONS_CFG  = cfg_dir(CONFIG, "sessions_dir",      SESSIONS_ROOT)
PLATFORM      = CONFIG.get("platform",              "opencode")
EMAIL_BASE    = CONFIG.get("email_base",            "aceproulx")
EMAIL_DOMAIN  = CONFIG.get("email_domain",          "intigriti.me")
TELEGRAM_TOKEN = CONFIG.get("telegram_bot_token",   "")
TELEGRAM_CHAT  = CONFIG.get("telegram_chat_id",     "")
INTIGRITI_USER = CONFIG.get("intigriti_username",   "")
MAX_SLOTS      = CONFIG.get("max_worker_slots",     3)


def current_max_slots() -> int:
    """Fresh read of the worker-slot cap from disk.

    MAX_SLOTS is a module-level constant captured at import time; the
    dashboard server does not restart on Settings changes, so anything that
    decides behavior from the slot count (Start Hunt vs queue button, pool
    start, refill-watcher) must read the live value instead.
    """
    try:
        return int(load_config().get("max_worker_slots") or 3)
    except (TypeError, ValueError):
        return 3
PORT_HTTP      = CONFIG.get("port_http",            8080)
PORT_HTTPS     = CONFIG.get("port_https",           8081)

_NOTIFY_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notify", "notify-telegram.sh"),
    os.path.expanduser("~/.local/bin/hackbot-notify"),
    shutil.which("hackbot-notify") or "",
]
NOTIFY = next((p for p in _NOTIFY_CANDIDATES if p and os.path.isfile(p)), None)

_WATCHDOG_CANDIDATES = [
    os.path.expanduser("~/.local/bin/hackbot-watchdog"),
    shutil.which("hackbot-watchdog") or "",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "watchdog.sh"),
]
WATCHDOG = next(
    (p for p in _WATCHDOG_CANDIDATES if p and os.path.isfile(p) and _is_rendered(p)),
    None,
)

_REFILL_WATCHER_CANDIDATES = [
    os.path.join(MISC, "refill-watcher.sh"),
    os.path.expanduser("~/.local/bin/hackbot-refill-watcher"),
]
REFILL_WATCHER = next(
    (p for p in _REFILL_WATCHER_CANDIDATES if p and os.path.isfile(p) and _is_rendered(p)),
    None,
)
