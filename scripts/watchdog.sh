#!/usr/bin/env bash
# watchdog.sh — Hackbot Worker Watchdog Scheduler
#
# Spawns the worker-monitor agent every INTERVAL seconds (default 30 min),
# waits for it to finish (or kills it after TIMEOUT), then sleeps and repeats.
# The monitor agent checks running workers, diagnoses failures, fixes them,
# writes a report, and exits — so each cycle is a fresh, self-terminating agent.
#
# Usage:
#   hackbot-watchdog start [--interval 1800] [--timeout 900]   foreground loop
#   hackbot-watchdog daemon [--interval 1800] [--timeout 900]  background (nohup)
#   hackbot-watchdog once                                       single run
#   hackbot-watchdog stop                                       kill daemon + monitor
#   hackbot-watchdog status                                     show state
#   hackbot-watchdog logs                                       tail watchdog log
#   hackbot-watchdog clean                                      dedup pool.json
#
# Logs to: {{HACKBOT_MISC_DIR}}/worker-pool/watchdog.log
# Reports: {{HACKBOT_MISC_DIR}}/worker-pool/watchdog-reports/
# Monitor runs in tmux session 'hackbot-watchdog' (window 'monitor') so it is
# visible but never collides with worker slots (hackbot:1..N).

set -euo pipefail

POOL_DIR={{HACKBOT_MISC_DIR}}/worker-pool
POOL_STATE="$POOL_DIR/pool.json"
LOG="$POOL_DIR/watchdog.log"
REPORTS_DIR="$POOL_DIR/watchdog-reports"
STATE_FILE="$POOL_DIR/watchdog-state.json"
PID_FILE="$POOL_DIR/watchdog.pid"
SESSION_NAME="hackbot-watchdog"
INTERVAL=1800          # 30 min between monitor runs
TIMEOUT=900            # hard cap on one monitor run (15 min)
AGENT="worker-monitor"

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

require_agent() {
  # The monitor agent must be installed for `opencode run --agent` to find it.
  if [[ ! -f "$HOME/.config/opencode/agent/${AGENT}.md" ]]; then
    echo -e "${YELLOW}WARN: agent '${AGENT}' not installed at ~/.config/opencode/agent/${AGENT}.md${RESET}" >&2
    echo -e "${YELLOW}      Run: bash scripts/install-skills.sh --platform opencode --config ~/.hackbot/config.json${RESET}" >&2
    return 1
  fi
}

init() {
  mkdir -p "$POOL_DIR" "$REPORTS_DIR"
  touch "$LOG"
  [[ -f "$STATE_FILE" ]] || echo '{}' > "$STATE_FILE"
}

# ── pool dedup: keep only latest entry per slot, remove fully dead ────────────

pool_dedup() {
  [[ -f "$POOL_STATE" ]] || return 0
  local BEFORE
  BEFORE=$(jq '.workers | length' "$POOL_STATE" 2>/dev/null || echo 0)

  # Keep the most recently started worker per slot (running workers win ties).
  # Drop workers that are "killed" or "done" older than 24h.
  jq '
    .workers |= (
      group_by(.slot) |
      map(
        # Prefer running workers; among same status, most recent started_at wins
        sort_by(.status == "running", .started_at // "1970-01-01T00:00:00Z") | last
      ) |
      map(select(
        .status == "running" or .status == "failed" or
        (.status != "running" and .status != "failed" and
         ((now - (.started_at // now | fromdateiso8601)) < 86400))
      ))
    )
  ' "$POOL_STATE" > /tmp/pool-dedup.json && mv /tmp/pool-dedup.json "$POOL_STATE"

  local AFTER
  AFTER=$(jq '.workers | length' "$POOL_STATE" 2>/dev/null || echo 0)
  if [[ "$BEFORE" -ne "$AFTER" ]]; then
    log "Pool dedup: $BEFORE → $AFTER workers"
  fi
}

# ── stale queue reset: deterministic, runs before every cycle ─────────────────
# Queue items marked "active" whose active_worker no longer exists as a running
# worker in pool.json are orphaned. Reset them to "pending" so they can be
# re-picked. This is deterministic — the agent reports on it but doesn't own it.

reset_stale_queue() {
  [[ -f "$POOL_STATE" ]] || return 0
  local QUEUE={{HACKBOT_MISC_DIR}}/target-queue.json
  [[ -f "$QUEUE" ]] || return 0

  # Build the set of running worker IDs from pool.json
  local RUNNING_IDS
  RUNNING_IDS=$(jq -c '[.workers[] | select(.status == "running") | .id]' "$POOL_STATE" 2>/dev/null || echo "[]")

  # Find queue items that are active but whose worker isn't running
  local STALE
  STALE=$(jq -c --argjson running "$RUNNING_IDS" \
    '[.[] | select(.status == "active" and .active_worker != null and
       (.active_worker as $aw | ($running | index($aw)) | not))]' \
    "$QUEUE" 2>/dev/null || echo "[]")

  local N
  N=$(jq 'length' <<< "$STALE" 2>/dev/null || echo 0)
  if [[ "$N" -gt 0 ]]; then
    local HANDLES
    HANDLES=$(jq -r '.[].handle' <<< "$STALE")
    for H in $HANDLES; do
      jq --arg h "$H" \
        'map(if .handle == $h then .status = "pending" | .active_worker = null else . end)' \
        "$QUEUE" > /tmp/queue-tmp.json && mv /tmp/queue-tmp.json "$QUEUE"
    done
    log "Stale queue reset: $N items → pending ($(echo "$HANDLES" | tr '\n' ' '))"
  fi
}

# ── run one monitor cycle ─────────────────────────────────────────────────────

run_cycle() {
  require_tmux
  require_agent || true

  # Pre-cycle: clean up pool.json + reset orphaned queue items
  pool_dedup
  reset_stale_queue

  local CYCLE_LOG="$POOL_DIR/watchdog-cycle.log"
  local BRIEF="$POOL_DIR/watchdog-brief.txt"
  local RUNNER="$POOL_DIR/watchdog-runner.sh"
  local RUNNER_PID="$POOL_DIR/watchdog-runner.pid"

  # Brief handed to the monitor agent (it reads the helper itself).
  cat > "$BRIEF" << 'BRIEF'
You are the hackbot worker watchdog. Run your full workflow now:
1. {{HACKBOT_MISC_DIR}}/watchdog-helper.sh --stale-min 15  (read the JSON)
2. Dedup pool.json (remove stale workers, keep latest per slot).
3. Clean stale queue items (active with no running worker → reset to pending).
4. Classify each running worker, fix what's broken, refill free slots.
5. Clean watchdog-state.json (remove entries for dead workers).
6. Write the report, notify Telegram, then exit.
Full instructions are in your agent definition. Execute them now.
BRIEF

  cat > "$RUNNER" << EOF
#!/usr/bin/env bash
cd ~
# Write our PID so the watchdog can track us
echo \$\$ > '${RUNNER_PID}'
exec opencode run --agent ${AGENT} "\$(cat '${BRIEF}')" 2>&1 | tee '${CYCLE_LOG}'
EOF
  chmod +x "$RUNNER"

  # Fresh tmux session for the monitor (separate from worker slots).
  # Pass the command directly to new-session — send-keys races the shell
  # startup and can drop the command entirely.
  tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
  tmux new-session -d -s "$SESSION_NAME" -x 220 -y 50 -n monitor "bash '${RUNNER}'"

  log "Monitor cycle started (agent=${AGENT}, timeout=${TIMEOUT}s)"

  # Wait for the runner to finish, polling by PID file + process check.
  local ELAPSED=0
  sleep 3  # give the runner a moment to spawn and write PID

  while true; do
    # Check if the runner is still alive
    local RUNNING=false
    if [[ -f "$RUNNER_PID" ]]; then
      local RPID
      RPID=$(cat "$RUNNER_PID" 2>/dev/null || echo "")
      if [[ -n "$RPID" ]] && kill -0 "$RPID" 2>/dev/null; then
        RUNNING=true
      fi
    fi
    # Fallback: check if any opencode process for the agent is alive
    if [[ "$RUNNING" == "false" ]]; then
      if pgrep -f "opencode run --agent ${AGENT}" >/dev/null 2>&1; then
        RUNNING=true
      fi
    fi

    if [[ "$RUNNING" == "false" ]]; then
      break
    fi

    sleep 10
    ELAPSED=$((ELAPSED + 10))
    if [[ $ELAPSED -ge $TIMEOUT ]]; then
      log "Monitor cycle TIMEOUT after ${TIMEOUT}s — killing"
      tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
      # Kill by PID file first, then fallback to pattern
      if [[ -f "$RUNNER_PID" ]]; then
        local RPID
        RPID=$(cat "$RUNNER_PID" 2>/dev/null || echo "")
        [[ -n "$RPID" ]] && kill -9 "$RPID" 2>/dev/null || true
      fi
      pkill -9 -f "opencode run --agent ${AGENT}" 2>/dev/null || true
      rm -f "$RUNNER_PID"
      hackbot-notify "⚠️ *WATCHDOG TIMEOUT* — monitor killed after ${TIMEOUT}s" 2>/dev/null || true
      return 1
    fi
  done

  rm -f "$RUNNER_PID"
  log "Monitor cycle finished in ${ELAPSED}s"
  # Clean up the monitor session so the next cycle starts fresh.
  tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
  return 0
}

# ── commands ──────────────────────────────────────────────────────────────────

cmd_start() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --interval) INTERVAL="$2"; shift 2 ;;
      --timeout)  TIMEOUT="$2";  shift 2 ;;
      *) shift ;;
    esac
  done

  init
  # Check if already running
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo -e "${YELLOW}Watchdog already running (PID $(cat "$PID_FILE")). Stop first.${RESET}"
    exit 1
  fi

  log "=== Watchdog started (foreground): interval=${INTERVAL}s timeout=${TIMEOUT}s ==="
  echo -e "${GREEN}${BOLD}✓ Watchdog started (foreground)${RESET}"
  echo -e "  Interval: ${CYAN}${INTERVAL}s${RESET} (${INTERVAL} sec = $((INTERVAL / 60)) min)"
  echo -e "  Timeout:  ${CYAN}${TIMEOUT}s${RESET}"
  echo -e "  Log:      ${CYAN}${LOG}${RESET}"
  echo -e "  Reports:  ${CYAN}${REPORTS_DIR}/${RESET}"
  echo -e "  Stop:     ${CYAN}hackbot-watchdog stop${RESET}"
  echo ""

  echo $$ > "$PID_FILE"
  trap 'rm -f "$PID_FILE"; exit 0' INT TERM

  while true; do
    run_cycle || true
    log "Sleeping ${INTERVAL}s until next cycle"
    sleep "$INTERVAL"
  done
}

cmd_daemon() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --interval) INTERVAL="$2"; shift 2 ;;
      --timeout)  TIMEOUT="$2";  shift 2 ;;
      *) shift ;;
    esac
  done

  init
  # Check if already running
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo -e "${YELLOW}Watchdog already running (PID $(cat "$PID_FILE")). Stop first.${RESET}"
    exit 1
  fi

  log "=== Watchdog started (daemon): interval=${INTERVAL}s timeout=${TIMEOUT}s ==="
  echo -e "${GREEN}${BOLD}✓ Watchdog daemon started${RESET}"
  echo -e "  PID file: ${CYAN}${PID_FILE}${RESET}"
  echo -e "  Log:      ${CYAN}${LOG}${RESET}"
  echo -e "  Reports:  ${CYAN}${REPORTS_DIR}/${RESET}"
  echo ""

  # Launch self in background with nohup
  # NOTE: no tee here — `watchdog.sh once` already logs everything via log()
  nohup bash -c "
    echo \$\$ > '$PID_FILE'
    while true; do
      '$0' once > /dev/null 2>&1
      echo \"[\$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Sleeping ${INTERVAL}s until next cycle\" >> '$LOG'
      sleep $INTERVAL
    done
  " >> "$LOG" 2>&1 & disown

  local DAEMON_PID=$!
  echo "$DAEMON_PID" > "$PID_FILE"
  log "Daemon PID: $DAEMON_PID"
  echo -e "  Daemon running: ${GREEN}PID $DAEMON_PID${RESET}"
  echo ""
}

cmd_once() {
  init
  log "=== Watchdog manual run (once) ==="
  run_cycle
  echo -e "${GREEN}✓ Monitor cycle complete${RESET}"
  local LAST_REPORT
  LAST_REPORT=$(ls -t "$REPORTS_DIR"/*.md 2>/dev/null | head -1)
  if [[ -n "$LAST_REPORT" ]]; then
    echo -e "  Report: ${CYAN}${LAST_REPORT}${RESET}"
  fi
}

cmd_stop() {
  log "Watchdog stopped by operator"
  # Kill daemon by PID file
  if [[ -f "$PID_FILE" ]]; then
    local DPID
    DPID=$(cat "$PID_FILE" 2>/dev/null || echo "")
    if [[ -n "$DPID" ]] && kill -0 "$DPID" 2>/dev/null; then
      kill "$DPID" 2>/dev/null || true
      log "Killed daemon PID $DPID"
    fi
    rm -f "$PID_FILE"
  fi
  # Kill any lingering daemon processes
  pkill -f "hackbot-watchdog.*once" 2>/dev/null || true
  # Kill monitor tmux session + runner
  tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
  if [[ -f "$POOL_DIR/watchdog-runner.pid" ]]; then
    local RPID
    RPID=$(cat "$POOL_DIR/watchdog-runner.pid" 2>/dev/null || echo "")
    [[ -n "$RPID" ]] && kill -9 "$RPID" 2>/dev/null || true
    rm -f "$POOL_DIR/watchdog-runner.pid"
  fi
  pkill -9 -f "opencode run --agent ${AGENT}" 2>/dev/null || true
  echo -e "${GREEN}✓ Watchdog stopped${RESET}"
}

cmd_status() {
  echo ""
  echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}║         HACKBOT WATCHDOG STATUS          ║${RESET}"
  echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"
  echo ""

  # Daemon status
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo -e "  ${GREEN}Watchdog daemon: RUNNING${RESET} (PID $(cat "$PID_FILE"))"
  elif pgrep -f "hackbot-watchdog.*once" >/dev/null 2>&1; then
    echo -e "  ${GREEN}Watchdog daemon: RUNNING${RESET} (detected via process)"
  else
    echo -e "  ${YELLOW}Watchdog daemon: not running${RESET}"
  fi

  # Monitor session status
  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo -e "  ${GREEN}Monitor session '${SESSION_NAME}': running${RESET}"
    tmux list-windows -t "$SESSION_NAME" 2>/dev/null | sed 's/^/    /'
  else
    echo -e "  ${YELLOW}Monitor session: idle${RESET}"
  fi

  # Pool summary
  if [[ -f "$POOL_STATE" ]]; then
    local POOL_SUMMARY
    POOL_SUMMARY=$(jq -c '{
      total: (.workers | length),
      running: [.workers[] | select(.status == "running")] | length,
      done: [.workers[] | select(.status == "done")] | length,
      failed: [.workers[] | select(.status == "failed")] | length,
      killed: [.workers[] | select(.status == "killed")] | length
    }' "$POOL_STATE" 2>/dev/null)
    echo ""
    echo -e "  ${BOLD}POOL STATE${RESET}"
    echo -e "  ─────────────────────────────────────────────"
    echo "  Total: $(echo "$POOL_SUMMARY" | jq '.total')  Running: $(echo "$POOL_SUMMARY" | jq '.running')  Done: $(echo "$POOL_SUMMARY" | jq '.done')  Failed: $(echo "$POOL_SUMMARY" | jq '.failed')  Killed: $(echo "$POOL_SUMMARY" | jq '.killed')"
    echo ""
    echo -e "  ${BOLD}RUNNING WORKERS${RESET}"
    echo -e "  ─────────────────────────────────────────────"
    jq -r '.workers[] | select(.status == "running") | "  \(.id) slot=\(.slot) handle=\(.handle) started=\(.started_at[0:19])Z"' "$POOL_STATE" 2>/dev/null || echo "  (none)"
  fi

  echo ""
  echo -e "  ${BOLD}RECENT CYCLES${RESET}"
  echo -e "  ─────────────────────────────────────────────"
  grep "Monitor cycle" "$LOG" 2>/dev/null | tail -8 | sed 's/^/  /' || echo "  (no cycles yet)"
  echo ""

  local LAST_REPORT
  LAST_REPORT=$(ls -t "$REPORTS_DIR"/*.md 2>/dev/null | head -1)
  if [[ -n "$LAST_REPORT" ]]; then
    echo -e "  ${BOLD}LAST REPORT:${RESET} ${CYAN}${LAST_REPORT}${RESET}"
    echo ""
    sed 's/^/  /' "$LAST_REPORT" | head -30
  else
    echo -e "  ${YELLOW}No reports yet. Run: hackbot-watchdog once${RESET}"
  fi
  echo ""
}

cmd_logs() {
  echo "Watchdog log: $LOG"
  tail -50 "$LOG" 2>/dev/null || echo "No watchdog log yet."
}

cmd_clean() {
  init
  pool_dedup
  echo -e "${GREEN}✓ Pool deduped${RESET}"
  jq -c '.workers | length' "$POOL_STATE" 2>/dev/null | xargs -I{} echo "  Workers remaining: {}"
}

# ── dispatch ──────────────────────────────────────────────────────────────────

CMD="${1:-status}"
case "$CMD" in
  start)   cmd_start "${@:2}" ;;
  daemon)  cmd_daemon "${@:2}" ;;
  once)    cmd_once ;;
  stop)    cmd_stop ;;
  status)  cmd_status ;;
  logs)    cmd_logs ;;
  clean)   cmd_clean ;;
  *)       echo "Commands: start | daemon | once | stop | status | logs | clean"; exit 1 ;;
esac
