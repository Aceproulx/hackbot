#!/usr/bin/env bash
# Refill watcher: when a worker slot frees up (done/killed), start the next
# pending target from the queue in that slot. Runs until the queue is empty
# or all slots are busy. Designed for overnight autonomous hunts.
#
# Usage: refill-watcher.sh [--interval 60] [--max-slots 4]
# Logs to: {{HACKBOT_MISC_DIR}}/worker-pool/refill-watcher.log

INTERVAL=60
MAX_SLOTS=4
POOL_STATE={{HACKBOT_MISC_DIR}}/worker-pool/pool.json
QUEUE={{HACKBOT_MISC_DIR}}/target-queue.json
LOG={{HACKBOT_MISC_DIR}}/worker-pool/refill-watcher.log

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval) INTERVAL="$2"; shift 2 ;;
    --max-slots) MAX_SLOTS="$2"; shift 2 ;;
    *) shift ;;
  esac
done

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

log "Refill watcher started (interval=${INTERVAL}s, max_slots=${MAX_SLOTS})"

while true; do
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