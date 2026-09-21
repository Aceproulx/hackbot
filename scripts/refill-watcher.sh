#!/usr/bin/env bash
# Refill watcher: when a worker slot frees up (done/killed), start the next
# pending target from the queue in that slot. Runs until the queue is empty
# or all slots are busy. Designed for overnight autonomous hunts.
#
# Usage: refill-watcher.sh [--interval 1800] [--max-slots 3]
#        refill-watcher.sh stop       # gracefully stop the running watcher
# Logs to: {{HACKBOT_MISC_DIR}}/worker-pool/refill-watcher.log
# (spawned by watchdog.sh — the 30-minute orchestrator)
#
# NOTE: default --interval is 1800 s (30 min) to match watchdog.sh. It is NOT
# meant to run every 60 s. When the queue is paused (hackbot-queue pause), the
# watcher idles and hands out nothing until resumed.

INTERVAL=1800
MAX_SLOTS=3
POOL_STATE={{HACKBOT_MISC_DIR}}/worker-pool/pool.json
QUEUE={{HACKBOT_MISC_DIR}}/target-queue.json
LOG={{HACKBOT_MISC_DIR}}/worker-pool/refill-watcher.log
PID_FILE={{HACKBOT_MISC_DIR}}/worker-pool/refill-watcher.pid
STOP_FILE={{HACKBOT_MISC_DIR}}/worker-pool/refill-watcher.stop

# `stop` subcommand → gracefully stop a running watcher.
if [[ "${1:-}" == "stop" ]]; then
  # 1) Prefer the recorded PID (new-style watcher writes one on launch).
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    kill -TERM "$(cat "$PID_FILE")" 2>/dev/null
    echo "Refill watcher stop requested (PID $(cat "$PID_FILE"))."
  fi
  # 2) Fallback: kill any stale daemon instance by its launch args. Guarded so
  #    the pattern cannot match THIS `stop` invocation (we pass `stop`, not `--interval`).
  pkill -f "refill-watcher\.sh --interval" 2>/dev/null || true
  sleep 1
  # 3) If the PID-file watcher is still up after TERM, force it.
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    kill -9 "$(cat "$PID_FILE")" 2>/dev/null || true
  fi
  touch "$STOP_FILE"
  # Confirm nothing matches anymore (warn if a stale one survived).
  if pgrep -f "refill-watcher\.sh --interval" >/dev/null 2>&1; then
    echo "⚠ Watcher process still present — check worker-pool/refill-watcher.log."
  else
    echo "✓ Refill watcher stopped."
  fi
  exit 0
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval) INTERVAL="$2"; shift 2 ;;
    --max-slots) MAX_SLOTS="$2"; shift 2 ;;
    *) shift ;;
  esac
done

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

cleanup() {
  rm -f "$PID_FILE" "$STOP_FILE"
  log "Refill watcher stopped (graceful)."
  exit 0
}
trap cleanup TERM INT

# Single instance guard — reuse PID file if the daemon is still alive.
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Refill watcher already running (PID $(cat "$PID_FILE")). Stop first." | tee -a "$LOG"
  exit 1
fi

echo $$ > "$PID_FILE"
rm -f "$STOP_FILE"
log "Refill watcher started (interval=${INTERVAL}s, max_slots=${MAX_SLOTS}, pid=$$)"

while true; do
  # Honor the stop marker (set by `stop` or watchdog.sh cmd_stop).
  if [[ -f "$STOP_FILE" ]]; then
    cleanup
  fi

  # When the queue is paused, idle until resumed — hand out nothing.
  if [[ -f "${QUEUE}.paused" ]]; then
    log "Queue PAUSED — watcher idle (waiting for resume)"
    sleep "$INTERVAL"
    continue
  fi

  # Reconcile first: a worker that finished (queue item already "done") but is
  # still marked "running" in pool.json holds its slot forever, so the scan
  # below would never see it as free. Release any such slot before scanning,
  # and fire the completion alert (covers workers that never ran cmd_done).
  jq -r --slurpfile q "$QUEUE" '
    .workers[] | select(.status == "running") | .handle as $h
    | select([$q[0][] | select(.handle == $h and .status == "done")] | length > 0)
    | [$q[0][] | select(.handle == $h)][0] as $qi
    | "\($h)\t\($qi.bugs_found // 0)\t\($qi.last_verdict // "UNKNOWN")"
  ' "$POOL_STATE" 2>/dev/null | while IFS=$'\t' read -r RH RB RV; do
    [[ -n "$RH" ]] || continue
    log "Reconcile: '${RH}' finished (queue=done) but pool slot still running → releasing"
    hackbot-queue release "$RH" >> "$LOG" 2>&1 || true
    hackbot-notify done "$RH" "$RB" "$RV" >> "$LOG" 2>&1 || true
  done

  # Find free slots: slots 1..MAX_SLOTS with no running worker
  FREE_SLOT=""
  for slot in $(seq 1 "$MAX_SLOTS"); do
    RUNNING=$(jq -r --argjson s "$slot" '[.workers[] | select(.slot == $s and .status == "running")] | length' "$POOL_STATE" 2>/dev/null || echo 0)
    if [[ "$RUNNING" == "0" ]]; then
      FREE_SLOT="$slot"
      break
    fi
  done

  if [[ -n "$FREE_SLOT" ]]; then
    NEXT=$(hackbot-queue next 2>/dev/null || echo "NO_TARGETS_AVAILABLE")
    if [[ "$NEXT" == "NO_TARGETS_AVAILABLE" || -z "$NEXT" ]]; then
      log "No pending targets — watcher idle"
    else
      HANDLE=$(echo "$NEXT" | jq -r '.handle')
      log "Slot ${FREE_SLOT} free → starting ${HANDLE}"
      hackbot-workers start-target "$HANDLE" >> "$LOG" 2>&1
    fi
  fi

  sleep "$INTERVAL"
done
