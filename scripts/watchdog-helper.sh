#!/usr/bin/env bash
# watchdog-helper.sh — Deterministic health snapshot of the worker pool.
#
# Emits a single JSON document to stdout describing every worker currently
# marked "running" in pool.json: is its tmux window alive, is its process
# alive, is its log still growing, and what failure signatures appear in the
# recent log tail. No judgment is applied here — the worker-monitor agent
# reads this snapshot and decides what to fix.
#
# Usage: watchdog-helper.sh [--stale-min 15]
#   --stale-min N   minutes of log silence that counts as "stale" (default 15)
#
# Exit code: 0 always (the JSON is the contract; empty pool is valid JSON).

set -euo pipefail

POOL_DIR={{HACKBOT_MISC_DIR}}/worker-pool
POOL_STATE="$POOL_DIR/pool.json"
QUEUE={{HACKBOT_MISC_DIR}}/target-queue.json
SESSION_NAME="hackbot"
STALE_MIN=15

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stale-min) STALE_MIN="$2"; shift 2 ;;
    *) shift ;;
  esac
done

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# ── pool-level facts ──────────────────────────────────────────────────────────

POOL_RUNNING=false
TMUX_ALIVE=false
if [[ -f "$POOL_STATE" ]]; then
  POOL_RUNNING=true
fi
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  TMUX_ALIVE=true
fi

# Free slots: slots 1..max_slots with no running worker
MAX_SLOTS=$(jq -r '.max_slots // 0' "$POOL_STATE" 2>/dev/null || echo 0)
FREE_SLOTS="[]"
if [[ "$MAX_SLOTS" -gt 0 ]]; then
  FREE_SLOTS=$(jq -c --argjson max "$MAX_SLOTS" '
    [range(1; $max + 1) as $s
     | select([.workers[] | select(.slot == $s and .status == "running")] | length == 0)
     | $s]
  ' "$POOL_STATE" 2>/dev/null || echo "[]")
fi

PENDING_TARGETS=$(jq '[.[] | select(.status == "pending")] | length' "$QUEUE" 2>/dev/null || echo 0)

# ── stale queue detection ─────────────────────────────────────────────────────
# Items marked "active" in the queue but with no running worker in pool.json
# need to be reset to "pending" — they're orphaned.
STALE_QUEUE="[]"
if [[ -f "$QUEUE" ]]; then
  STALE_QUEUE=$(jq -c '[.[] | select(.status == "active" and .active_worker != null)]' "$QUEUE" 2>/dev/null || echo "[]")
  # Cross-check: is the active_worker actually running in pool.json?
  if [[ "$POOL_RUNNING" == "true" ]]; then
    STALE_QUEUE=$(jq -c --argjson pool "$(
      jq -c '[.workers[] | select(.status == "running") | .id]' "$POOL_STATE" 2>/dev/null || echo "[]"
    )" '[.[] | select(.active_worker as $aw | ($pool | index($aw)) | not)]' <<< "$STALE_QUEUE" 2>/dev/null || echo "[]")
  fi
  STALE_QUEUE_LEN=$(jq 'length' <<< "$STALE_QUEUE" 2>/dev/null || echo 0)
else
  STALE_QUEUE_LEN=0
fi

# ── orphan tmux windows ───────────────────────────────────────────────────────
# Windows in the hackbot session that have no matching running worker in
# pool.json. These are workers whose pool entry was lost (dedup bug, crash,
# manual edit) but whose tmux window + process are still alive. The monitor
# agent should re-adopt them (re-add to pool.json) rather than kill them.
ORPHAN_WINDOWS="[]"
if [[ "$TMUX_ALIVE" == "true" ]]; then
  ORPHAN_WINDOWS=$(tmux list-windows -t "$SESSION_NAME" -F '#{window_index}:#{window_name}' 2>/dev/null \
    | grep -v '^0:' \
    | while IFS=: read -r WIN WNAME; do
        CLAIMED=$(jq -r --argjson s "$WIN" \
          '[.workers[] | select(.slot == $s and .status == "running")] | length' \
          "$POOL_STATE" 2>/dev/null || echo 0)
        if [[ "$CLAIMED" == "0" ]]; then
          jq -nc --argjson slot "$WIN" --arg handle "$WNAME" \
            '{slot:$slot, handle:$handle}'
        fi
      done | jq -s '.' 2>/dev/null || echo "[]")
fi
ORPHAN_COUNT=$(jq 'length' <<< "$ORPHAN_WINDOWS" 2>/dev/null || echo 0)

# ── pool status summary ──────────────────────────────────────────────────────

POOL_SUMMARY="{}"
if [[ -f "$POOL_STATE" ]]; then
  POOL_SUMMARY=$(jq -c '{
    total: (.workers | length),
    running: [.workers[] | select(.status == "running")] | length,
    done: [.workers[] | select(.status == "done")] | length,
    failed: [.workers[] | select(.status == "failed")] | length,
    killed: [.workers[] | select(.status == "killed")] | length
  }' "$POOL_STATE" 2>/dev/null || echo "{}")
fi

# ── error signature patterns ──────────────────────────────────────────────────
# fatal = the worker process itself died or the environment broke
# warn  = target blocking / external friction (useful signal, not a crash)
FATAL_PATTERNS=(
  'command not found'
  'permission denied'
  'no such file'
  'cannot read'
  'traceback'
  'segmentation fault'
  'connection refused'
  'econnrefused'
  'etimedout'
  'getaddrinfo'
  'rate limit'
  'too many requests'
  'step limit'
  'max steps'
  'steps exhausted'
  'insufficient'
  'no targets available'
  'queue exhausted'
  'failed to'
  'error:'
  'fatal:'
  'killed'
  'sigterm'
  'sigkill'
  'no current client'
  "can't find session"
  'session not found'
)

WARN_PATTERNS=(
  'waf'
  'blocked'
  'captcha'
  '429'
  '403'
  'cloudflare'
  'turnstile'
  'recaptcha'
)

# ── per-worker facts ──────────────────────────────────────────────────────────

NOW_EPOCH=$(date +%s)

worker_json() {
  local ID="$1" HANDLE="$2" SLOT="$3" LOG="$4"
  local TMUX_WIN=false PROC_ALIVE=false LOG_AGE_MIN=null LOG_SIZE=0
  local FATAL="[]" WARN="[]" LAST_LINE=""

  # tmux window alive?
  if tmux list-windows -t "$SESSION_NAME" 2>/dev/null | grep -q "^${SLOT}:"; then
    TMUX_WIN=true
  fi

  # process alive? check for the runner script or opencode process for this worker
  # The runner writes its PID to worker-<slot>-<handle>.pid
  local PID_FILE="$POOL_DIR/worker-${SLOT}-${HANDLE}.pid"
  if [[ -f "$PID_FILE" ]]; then
    local WPID
    WPID=$(cat "$PID_FILE" 2>/dev/null || echo "")
    if [[ -n "$WPID" ]] && kill -0 "$WPID" 2>/dev/null; then
      PROC_ALIVE=true
    fi
  fi
  # Fallback: check if opencode run with this agent name is alive
  if [[ "$PROC_ALIVE" == "false" ]]; then
    if pgrep -f "worker-${SLOT}-${HANDLE}" >/dev/null 2>&1; then
      PROC_ALIVE=true
    fi
  fi

  # CPU seconds consumed by the opencode process for this worker (cumulative).
  # This is the signal that distinguishes "working but not writing to the log"
  # (Caido/browser-heavy work) from "genuinely hung" (0 CPU since last cycle).
  # The monitor agent compares it against the previous cycle's value stored in
  # watchdog-state.json.
  local CPU_SECONDS=0
  local OPID
  OPID=$(pgrep -f "opencode run" 2>/dev/null | while read -r P; do
    if tr '\0' ' ' < "/proc/$P/cmdline" 2>/dev/null | grep -q "worker-${SLOT}-${HANDLE}"; then
      echo "$P"
      break
    fi
  done || true)
  if [[ -n "$OPID" && -r "/proc/$OPID/stat" ]]; then
    local STAT UTIME STIME CLK
    # comm (field 2) is in parens and may contain spaces — strip through the
    # last ')' so the remaining fields are stable: field 14 (utime) is the
    # 12th token after the paren, field 15 (stime) the 13th.
    STAT=$(sed 's/.*) //' "/proc/$OPID/stat")
    read -r -a FIELDS <<< "$STAT"
    # after the comm paren: token 12 = utime (field 14), token 13 = stime (field 15)
    UTIME=${FIELDS[11]:-0}
    STIME=${FIELDS[12]:-0}
    CLK=$(getconf CLK_TCK 2>/dev/null || echo 100)
    CPU_SECONDS=$(( (UTIME + STIME) / CLK ))
  fi

  # log age + size
  if [[ -f "$LOG" ]]; then
    local MTIME
    MTIME=$(stat -c %Y "$LOG" 2>/dev/null || echo 0)
    LOG_SIZE=$(stat -c %s "$LOG" 2>/dev/null || echo 0)
    if [[ "$MTIME" -gt 0 ]]; then
      LOG_AGE_MIN=$(( (NOW_EPOCH - MTIME) / 60 ))
    fi
    LAST_LINE=$(tail -1 "$LOG" 2>/dev/null | tr -d '\r' | cut -c1-300 || true)
  fi

  # error signatures in the last 200 lines
  if [[ -f "$LOG" ]]; then
    local TAIL
    TAIL=$(tail -200 "$LOG" 2>/dev/null || true)
    local P FOUND
    FOUND=""
    for P in "${FATAL_PATTERNS[@]}"; do
      if grep -qiE "$P" <<< "$TAIL"; then
        FOUND="${FOUND:+$FOUND,}\"$P\""
      fi
    done
    [[ -n "$FOUND" ]] && FATAL="[$FOUND]"

    FOUND=""
    for P in "${WARN_PATTERNS[@]}"; do
      if grep -qiE "$P" <<< "$TAIL"; then
        FOUND="${FOUND:+$FOUND,}\"$P\""
      fi
    done
    [[ -n "$FOUND" ]] && WARN="[$FOUND]"
  fi

  jq -nc \
    --arg id "$ID" \
    --arg handle "$HANDLE" \
    --argjson slot "$SLOT" \
    --argjson tmux "$TMUX_WIN" \
    --argjson proc "$PROC_ALIVE" \
    --argjson age "$LOG_AGE_MIN" \
    --argjson size "$LOG_SIZE" \
    --argjson cpu "$CPU_SECONDS" \
    --argjson fatal "$FATAL" \
    --argjson warn "$WARN" \
    --arg last "$LAST_LINE" \
    '{id:$id, handle:$handle, slot:$slot, tmux_alive:$tmux,
      proc_alive:$proc, log_age_min:$age, log_size:$size, cpu_seconds:$cpu,
      fatal_errors:$fatal, warn_signals:$warn, last_line:$last}'
}

WORKERS="[]"
if [[ -f "$POOL_STATE" ]]; then
  WORKERS=$(jq -c '[.workers[] | select(.status == "running")]' "$POOL_STATE" 2>/dev/null || echo "[]")
fi

# Build the workers array incrementally (jq -c per worker, then join)
ACC="[]"
while IFS= read -r W; do
  [[ -z "$W" ]] && continue
  ID=$(jq -r '.id' <<< "$W")
  HANDLE=$(jq -r '.handle' <<< "$W")
  SLOT=$(jq -r '.slot' <<< "$W")
  LOG=$(jq -r '.log // empty' <<< "$W")
  [[ -z "$LOG" ]] && LOG="$POOL_DIR/worker-${SLOT}-${HANDLE}.log"
  ONE=$(worker_json "$ID" "$HANDLE" "$SLOT" "$LOG")
  ACC=$(jq -c --argjson o "$ONE" '. + [$o]' <<< "$ACC")
done < <(jq -c '.[]' <<< "$WORKERS")

jq -nc \
  --arg ts "$(ts)" \
  --argjson pool "$POOL_RUNNING" \
  --argjson tmux "$TMUX_ALIVE" \
  --argjson free "$FREE_SLOTS" \
  --argjson pending "$PENDING_TARGETS" \
  --argjson workers "$ACC" \
  --argjson stale "$STALE_MIN" \
  --argjson summary "$POOL_SUMMARY" \
  --argjson stale_queue "$STALE_QUEUE" \
  --argjson stale_queue_len "$STALE_QUEUE_LEN" \
  --argjson orphans "$ORPHAN_WINDOWS" \
  --argjson orphan_count "$ORPHAN_COUNT" \
  '{generated_at:$ts, pool_running:$pool, tmux_session_alive:$tmux,
    free_slots:$free, pending_targets:$pending, stale_min:$stale,
    pool_summary:$summary,
    stale_queue:$stale_queue, stale_queue_len:$stale_queue_len,
    orphan_windows:$orphans, orphan_count:$orphan_count,
    workers:$workers}'
