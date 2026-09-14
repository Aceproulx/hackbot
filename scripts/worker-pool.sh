#!/usr/bin/env bash
# worker-pool.sh — Hackbot Parallel Worker Pool Manager
#
# Manages a pool of N simultaneous bug-hunting workers, each hunting a
# different target. Designed to run overnight autonomously.
#
# Usage:
#   hackbot-workers start [--slots 2] [--budget 15]
#   hackbot-workers status
#   hackbot-workers stop
#   hackbot-workers logs [worker_id]
#
# Each "worker" is a tmux window running an opencode/agy session
# pointed at a specific target from the queue.
#
# Slots: how many parallel workers to run (default: 2)
# Budget: total USD budget across ALL workers combined (default: $15)

set -euo pipefail

POOL_DIR={{HACKBOT_MISC_DIR}}/worker-pool
POOL_STATE="$POOL_DIR/pool.json"
QUEUE={{HACKBOT_MISC_DIR}}/target-queue.json
FINDINGS={{HACKBOT_MISC_DIR}}/findings.jsonl
SESSION_NAME="hackbot"       # tmux session name
MAX_SLOTS="${HACKBOT_SLOTS:-2}"
TOTAL_BUDGET="${HACKBOT_BUDGET:-15}"
LOG="$POOL_DIR/pool.log"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

require_tmux() {
  command -v tmux &>/dev/null || {
    echo -e "${RED}ERROR: tmux is required. Install with: sudo apt install tmux${RESET}" >&2
    exit 1
  }
}

require_queue() {
  [[ -f "$QUEUE" ]] || {
    echo -e "${YELLOW}Queue not initialized. Running: hackbot-queue init${RESET}"
    hackbot-queue init
  }
}

# ── init pool state ────────────────────────────────────────────────────────────

init_pool() {
  mkdir -p "$POOL_DIR"
  touch "$LOG" "$FINDINGS"
  cat > "$POOL_STATE" << EOF
{
  "started_at": "$(ts)",
  "max_slots": $MAX_SLOTS,
  "budget_usd": $TOTAL_BUDGET,
  "budget_per_worker": $(echo "$TOTAL_BUDGET $MAX_SLOTS" | awk '{printf "%.2f", $1/$2}'),
  "workers": []
}
EOF
}

# ── spawn one worker into a tmux window ───────────────────────────────────────

spawn_worker() {
  local HANDLE="$1"
  local PROGRAM_ID="$2"
  local MAX_BOUNTY="$3"
  local SLOT="$4"
  local BUDGET_PER=$(jq -r '.budget_per_worker' "$POOL_STATE")
  local HUNT_DIR=~/Projects/hunts/${HANDLE}-$(date +%Y%m%d)
  local WORKER_ID="worker-${SLOT}-${HANDLE}"
  local WORKER_LOG="$POOL_DIR/${WORKER_ID}.log"

  mkdir -p "$HUNT_DIR"

  # Get scope from intigriti MCP (best-effort, continue if unavailable)
  SCOPE_NOTE="Run: intigriti get_program_scope $PROGRAM_ID for full scope"

  # Build the prompt file for this worker
  local PROMPT_FILE="$POOL_DIR/${WORKER_ID}.prompt"
  cat > "$PROMPT_FILE" << PROMPT
You are an autonomous bug hunter. Load the @bug-hunting skill (Antigravity) or @web-hacking skill (OpenCode) immediately.

TARGET HANDLE: ${HANDLE}
PROGRAM ID: ${PROGRAM_ID}
MAX BOUNTY: \$${MAX_BOUNTY}
HUNT DIRECTORY: ${HUNT_DIR}/
WORKER ID: ${WORKER_ID}
SLOT: ${SLOT} of ${MAX_SLOTS}

FIRST ACTION: Run intigriti get_program_scope ${PROGRAM_ID} to get exact in-scope/out-of-scope assets.

BUDGET: \$${BUDGET_PER} USD for this worker session. Stop gracefully when you approach this limit.

REGISTRATION EMAILS:
{{EMAIL_BASE}}+${HANDLE}-a@{{EMAIL_DOMAIN}}  (userA)
{{EMAIL_BASE}}+${HANDLE}-b@{{EMAIL_DOMAIN}}  (userB)

DENY LIST (never call these endpoint verbs on other users):
refund, settle, payout, transfer, adjust, disburse,
delete (other users), rotate (keys/tokens), reset (other users' passwords)

ON CONFIRMED FINDING: run this command:
hackbot-dashboard add --program "${HANDLE}" --title "<title>" --severity "<sev>" --status "confirmed" --bounty <est> --evidence "<caido_ids>" --url "<url>"

WHEN DONE: run this command and then exit:
hackbot-queue done "${HANDLE}" <bugs_found> <RICH_TARGET|MODERATE|THIN_TARGET|WAF_BLOCKED|AUTH_BLOCKED>
PROMPT

  # Launch tmux window with the worker
  local WINDOW="${SESSION_NAME}:${SLOT}"

  # Create session if it doesn't exist
  tmux has-session -t "$SESSION_NAME" 2>/dev/null || \
    tmux new-session -d -s "$SESSION_NAME" -x 220 -y 50

  # Create or reuse window for this slot
  tmux list-windows -t "$SESSION_NAME" | grep -q "^${SLOT}:" 2>/dev/null || \
    tmux new-window -t "${SESSION_NAME}:${SLOT}" -n "${HANDLE}"

  tmux rename-window -t "${SESSION_NAME}:${SLOT}" "${HANDLE}" 2>/dev/null || true

  # Detect AI tool (prefer opencode, fall back to agy)
  local AI_CMD
  if command -v opencode &>/dev/null; then
    # Run non-interactively via `opencode run`. The prompt is read at runtime
    # ($(cat ...) output inside double quotes is never re-expanded), the hunt
    # dir is chdir'd into, and output is teed to the worker log. A runner
    # script avoids tmux/shell quoting issues with the multi-line prompt.
    local RUNNER="$POOL_DIR/${WORKER_ID}.sh"
    cat > "$RUNNER" << EOF
#!/usr/bin/env bash
cd '${HUNT_DIR}'
exec opencode run --agent hunter "\$(cat '${PROMPT_FILE}')" 2>&1 | tee '${WORKER_LOG}'
EOF
    chmod +x "$RUNNER"
    AI_CMD="bash '${RUNNER}'"
  elif command -v agy &>/dev/null; then
    AI_CMD="agy --no-input < '${PROMPT_FILE}' 2>&1 | tee '${WORKER_LOG}'"
  else
    # Manual mode — just open the prompt for copy-paste
    AI_CMD="echo 'Paste this prompt into your AI tool:' && cat '${PROMPT_FILE}' && bash"
  fi

  tmux send-keys -t "${SESSION_NAME}:${SLOT}" \
    "echo '=== WORKER ${SLOT}: ${HANDLE} ===' && ${AI_CMD}" Enter

  # Update pool state
  local NOW=$(ts)
  jq --arg id "$WORKER_ID" --arg handle "$HANDLE" \
     --arg slot "$SLOT" --arg ts "$NOW" --arg log "$WORKER_LOG" \
     --argjson bounty "$MAX_BOUNTY" \
     '.workers += [{
       id: $id, handle: $handle, slot: ($slot|tonumber),
       status: "running", started_at: $ts, log: $log,
       max_bounty: $bounty, bugs_found: 0
     }]' "$POOL_STATE" > /tmp/pool-tmp.json && mv /tmp/pool-tmp.json "$POOL_STATE"

  # Mark active in queue
  jq --arg h "$HANDLE" --arg ts "$NOW" --arg wid "$WORKER_ID" '
    map(if .handle == $h then .status = "active" | .started_at = $ts | .active_worker = $wid else . end)
  ' "$QUEUE" > /tmp/queue-tmp.json && mv /tmp/queue-tmp.json "$QUEUE"

  log "Spawned worker slot=${SLOT} handle=${HANDLE} window=${SESSION_NAME}:${SLOT}"
  hackbot-notify "🚀 *WORKER STARTED*
*Slot:* ${SLOT}/${MAX_SLOTS}
*Target:* \`${HANDLE}\`
*Budget:* \$${BUDGET_PER}
_$(ts)_" 2>/dev/null || true
}

# ── start pool ─────────────────────────────────────────────────────────────────

cmd_start() {
  require_tmux
  require_queue

  # Parse args
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --slots)  MAX_SLOTS="$2";  shift 2 ;;
      --budget) TOTAL_BUDGET="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  init_pool
  log "=== Worker pool starting: slots=${MAX_SLOTS} budget=\$${TOTAL_BUDGET} ==="
  hackbot-notify session-start "$POOL_DIR" 2>/dev/null || true

  # Fill all slots at startup
  local SLOT=1
  while [[ $SLOT -le $MAX_SLOTS ]]; do
    local NEXT
    NEXT=$(hackbot-queue next 2>/dev/null || echo "NO_TARGETS_AVAILABLE")

    if [[ "$NEXT" == "NO_TARGETS_AVAILABLE" || -z "$NEXT" ]]; then
      log "No more targets available for slot ${SLOT}"
      break
    fi

    local HANDLE=$(echo "$NEXT" | jq -r '.handle')
    local PROGRAM_ID=$(echo "$NEXT" | jq -r '.program_id')
    local MAX_BOUNTY=$(echo "$NEXT" | jq -r '.max_bounty // 0')

    spawn_worker "$HANDLE" "$PROGRAM_ID" "$MAX_BOUNTY" "$SLOT"
    SLOT=$((SLOT + 1))
    sleep 2  # stagger launches slightly
  done

  echo ""
  echo -e "${GREEN}${BOLD}✓ Worker pool started${RESET}"
  echo -e "  Attach to monitor: ${CYAN}tmux attach -t ${SESSION_NAME}${RESET}"
  echo -e "  Status:            ${CYAN}hackbot-workers status${RESET}"
  echo -e "  Stop all:          ${CYAN}hackbot-workers stop${RESET}"
  echo ""
}

# ── status ─────────────────────────────────────────────────────────────────────

cmd_status() {
  echo ""
  echo -e "${BOLD}╔══════════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}║         HACKBOT WORKER POOL STATUS           ║${RESET}"
  echo -e "${BOLD}╚══════════════════════════════════════════════╝${RESET}"
  echo ""

  if [[ ! -f "$POOL_STATE" ]]; then
    echo -e "  ${YELLOW}No active pool. Run: hackbot-workers start${RESET}"
    echo ""
    return
  fi

  local STARTED=$(jq -r '.started_at' "$POOL_STATE")
  local SLOTS=$(jq -r '.max_slots' "$POOL_STATE")
  local BUDGET=$(jq -r '.budget_usd' "$POOL_STATE")
  local PER=$(jq -r '.budget_per_worker' "$POOL_STATE")

  printf "  %-22s %s\n" "Session started:" "${STARTED:0:19}Z"
  printf "  %-22s %s\n" "Slots:" "$SLOTS"
  printf "  %-22s \$%s (\\$%s/worker)\n" "Budget:" "$BUDGET" "$PER"
  echo ""

  # tmux windows
  local TMUX_ACTIVE=0
  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    TMUX_ACTIVE=1
    echo -e "  ${GREEN}tmux session '${SESSION_NAME}' is running${RESET}"
    echo -e "  Windows:"
    tmux list-windows -t "$SESSION_NAME" 2>/dev/null | while read -r win; do
      echo "    $win"
    done
  else
    echo -e "  ${YELLOW}tmux session '${SESSION_NAME}' is NOT running${RESET}"
  fi
  echo ""

  echo -e "  ${BOLD}WORKERS${RESET}"
  echo -e "  ─────────────────────────────────────────────"
  printf "  %-5s %-22s %-10s %-8s %s\n" "SLOT" "HANDLE" "STATUS" "BUGS" "STARTED"
  echo "  ─────────────────────────────────────────────"

  jq -r '.workers[] | [
    (.slot|tostring), .handle, .status,
    (.bugs_found|tostring),
    .started_at[0:16]
  ] | @tsv' "$POOL_STATE" 2>/dev/null | \
  while IFS=$'\t' read -r slot handle status bugs started; do
    case "$status" in
      running) COLOR="${GREEN}" ;;
      done)    COLOR="${CYAN}"  ;;
      killed)  COLOR="${RED}"   ;;
      *)       COLOR="${RESET}" ;;
    esac
    printf "  ${COLOR}%-5s %-22s %-10s %-8s %s${RESET}\n" \
      "$slot" "$handle" "$status" "$bugs" "$started"
  done

  echo ""
  local TOTAL_BUGS=$(jq '[.workers[].bugs_found] | add // 0' "$POOL_STATE")
  echo -e "  ${BOLD}Total bugs found: ${GREEN}${TOTAL_BUGS}${RESET}"
  echo ""
}

# ── stop ───────────────────────────────────────────────────────────────────────

cmd_stop() {
  log "Stopping worker pool..."
  hackbot-notify "🛑 *WORKER POOL STOPPED*
_$(ts)_" 2>/dev/null || true

  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "$SESSION_NAME"
    echo -e "${GREEN}✓ tmux session '${SESSION_NAME}' killed${RESET}"
  else
    echo -e "${YELLOW}No active tmux session '${SESSION_NAME}'${RESET}"
  fi

  # Mark all running workers as killed in pool state
  [[ -f "$POOL_STATE" ]] && \
    jq '.workers |= map(if .status == "running" then .status = "killed" else . end)' \
    "$POOL_STATE" > /tmp/pool-tmp.json && mv /tmp/pool-tmp.json "$POOL_STATE"

  hackbot-dashboard stats 2>/dev/null || true
}

# ── logs ───────────────────────────────────────────────────────────────────────

cmd_logs() {
  local WORKER="${2:-}"
  if [[ -z "$WORKER" ]]; then
    echo "Pool log: $LOG"
    tail -50 "$LOG" 2>/dev/null || echo "No pool log yet."
  else
    local WORKER_LOG="$POOL_DIR/worker-${WORKER}.log"
    echo "Worker log: $WORKER_LOG"
    tail -100 "$WORKER_LOG" 2>/dev/null || echo "No log for worker: $WORKER"
  fi
}

# ── attach ─────────────────────────────────────────────────────────────────────

cmd_attach() {
  require_tmux
  tmux has-session -t "$SESSION_NAME" 2>/dev/null || {
    echo -e "${YELLOW}No active session '${SESSION_NAME}'. Run: hackbot-workers start${RESET}"
    exit 1
  }
  tmux attach -t "$SESSION_NAME"
}

# ── dispatch ───────────────────────────────────────────────────────────────────

CMD="${1:-status}"
case "$CMD" in
  start)   cmd_start "${@:2}" ;;
  status)  cmd_status ;;
  stop)    cmd_stop ;;
  logs)    cmd_logs "$@" ;;
  attach)  cmd_attach ;;
  *)       echo "Commands: start [--slots N] [--budget N] | status | stop | logs | attach"; exit 1 ;;
esac
