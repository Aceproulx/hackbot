"""config.py — all paths and runtime config for the Hackbot dashboard."""
import json
import os
import shutil

HOME = os.path.expanduser("~")
MISC = os.environ.get("HACKBOT_MISC", "/home/aceos/Projects/hackbot-misc")
MISC = os.path.expanduser(MISC)
HUNTS_ROOT = os.path.expanduser("~/Projects/hunts")
SESSIONS_ROOT = os.path.join(HUNTS_ROOT, "sessions")
CONFIG_PATH = os.path.expanduser("~/.hackbot/config.json")

QUEUE_FILE     = os.path.join(MISC, "target-queue.json")
POOL_FILE      = os.path.join(MISC, "worker-pool", "pool.json")
FINDINGS_FILE  = os.path.join(MISC, "findings.jsonl")
REPORTS_DIR    = os.path.join(MISC, "reports")
SKILL_DIRS = [
    os.path.expanduser("~/.config/opencode/skill"),
    os.path.expanduser("~/.agents/skills"),
    os.path.expanduser("~/.gemini/skills"),
]

_QUEUE_MANAGER_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "queue-manager.sh"),
    os.path.expanduser("~/.local/bin/hackbot-queue"),
    shutil.which("hackbot-queue") or "",
]
QUEUE_MANAGER = next((p for p in _QUEUE_MANAGER_CANDIDATES if p and os.path.isfile(p)), None)

_WORKER_POOL_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "worker-pool.sh"),
    os.path.expanduser("~/.local/bin/hackbot-workers"),
    shutil.which("hackbot-workers") or "",
]
WORKER_POOL = next((p for p in _WORKER_POOL_CANDIDATES if p and os.path.isfile(p)), None)


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
MAX_SLOTS      = CONFIG.get("max_worker_slots",     2)
PORT_HTTP      = CONFIG.get("port_http",            8080)
PORT_HTTPS     = CONFIG.get("port_https",           8081)

_NOTIFY_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notify", "notify-telegram.sh"),
    os.path.expanduser("~/.local/bin/hackbot-notify"),
    shutil.which("hackbot-notify") or "",
]
NOTIFY = next((p for p in _NOTIFY_CANDIDATES if p and os.path.isfile(p)), None)
