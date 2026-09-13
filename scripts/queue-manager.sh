#!/usr/bin/env bash
# queue-manager.sh — Hackbot Target Queue Manager
#
# Commands:
#   init                   Pull programs from Intigriti, build/refresh queue
#   next                   Print the next pending target as JSON, mark it active
#   done <handle> <bugs> <verdict>   Mark target complete
#   skip <handle> [reason] Mark target skipped (thin/WAF/no-auth)
#   fail <handle> [reason] Mark target failed (crash/error)
#   status                 Print current queue table
#   history                Print past hunts from history log
#   reset <handle>         Reset a target back to pending
#   requeue <handle> <days> Re-queue a target to be hunted again in N days
#   boost <handle> <pts>   Add score boost to a target (e.g. after finding a bug)

set -euo pipefail

QUEUE_FILE={{HACKBOT_MISC_DIR}}/target-queue.json
HISTORY_FILE={{HACKBOT_MISC_DIR}}/queue-history.jsonl
LOCK_FILE=/tmp/hackbot-queue.lock
MIN_REHUNT_DAYS="${MIN_REHUNT_DAYS:-7}"     # don't re-hunt a target within this window
NOTIFY="hackbot-notify"

# ── helpers ────────────────────────────────────────────────────────────────────

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

lock() {
  exec 9>"$LOCK_FILE"
  flock -x -w 5 9 || { echo "ERROR: queue is locked by another process" >&2; exit 1; }
}

unlock() { flock -u 9; }

require_queue() {
  [[ -f "$QUEUE_FILE" ]] || { echo "ERROR: queue not initialized. Run: queue-manager.sh init" >&2; exit 1; }
}

# ── init ───────────────────────────────────────────────────────────────────────

cmd_init() {
  lock
  echo "Fetching programs from Intigriti MCP..."

  # Pull programs via intigriti MCP node script (uses same config as opencode/AGY)
  # Falls back to a direct API call if the MCP runner isn't available
  PROGRAMS_JSON=$(node - <<'EOF' 2>/dev/null || echo "[]"
const { execSync } = require('child_process');
// Try to call the intigriti MCP server directly
try {
  const result = execSync(
    'node ~/Projects/intigriti-mcp/dist/index.js list-programs 2>/dev/null',
    { timeout: 15000 }
  ).toString();
  console.log(result);
} catch(e) {
  console.log('[]');
}
EOF
)

  # If MCP call returned nothing, fall back to curl against Intigriti public API
  if [[ "$PROGRAMS_JSON" == "[]" || -z "$PROGRAMS_JSON" ]]; then
    echo "MCP unavailable — falling back to Intigriti REST API..."
    PROGRAMS_JSON=$(curl -s \
      -H "Authorization: Bearer ${INTIGRITI_API_TOKEN}" \
      "https://api.intigriti.com/external/researcher/v1/programs?status=open&limit=100" \
      2>/dev/null || echo '{"records":[]}')
  fi

  # Load existing queue if present (to preserve history/scores)
  EXISTING="[]"
  [[ -f "$QUEUE_FILE" ]] && EXISTING=$(cat "$QUEUE_FILE")

  # Build new queue with jq — merge existing entries, add new ones
  NEW_QUEUE=$(echo "$PROGRAMS_JSON" "$EXISTING" | jq -s '
    # normalize both inputs
    def existing_map: .[1] | map({(.handle): .}) | add // {};
    def programs: .[0] | if type == "array" then . else (.records // []) end;

    programs as $progs |
    existing_map as $ex |
    $progs
    | map(select(.status == "open" and (.maxBounty // 0) > 0))
    | map({
        handle:               .handle,
        program_id:           .id,
        name:                 .name,
        max_bounty:           (.maxBounty // 0),
        min_bounty:           (.minBounty // 0),
        tags:                 (.tags // []),
        confidentiality:      (.confidentialityLevel // "Public"),
        status:               ($ex[.handle].status // "pending"),
        score:                ($ex[.handle].score // (
          # base score from bounty
          if (.maxBounty // 0) >= 10000 then 30
          elif (.maxBounty // 0) >= 5000 then 20
          elif (.maxBounty // 0) >= 1000 then 10
          else 5 end
        )),
        boost:                ($ex[.handle].boost // 0),
        bugs_found:           ($ex[.handle].bugs_found // 0),
        last_hunted:          ($ex[.handle].last_hunted // null),
        last_verdict:         ($ex[.handle].last_verdict // null),
        active_worker:        null,
        started_at:           null,
        queued_at:            ($ex[.handle].queued_at // now | todate),
        rehunt_after:         ($ex[.handle].rehunt_after // null)
      })
    # Re-open targets whose rehunt_after has passed
    | map(
        if .status == "done" and .rehunt_after != null
           and (.rehunt_after < (now | todate))
        then .status = "pending"
        else .
        end
      )
    # Sort by effective score desc
    | sort_by(-(.score + .boost))
  ')

  echo "$NEW_QUEUE" > "$QUEUE_FILE"
  TOTAL=$(echo "$NEW_QUEUE" | jq 'length')
  PENDING=$(echo "$NEW_QUEUE" | jq '[.[] | select(.status=="pending")] | length')
  echo "Queue initialized: $TOTAL programs total, $PENDING pending"
  unlock
}

# ── next ───────────────────────────────────────────────────────────────────────

cmd_next() {
  lock
  require_queue

  NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  TODAY=$(date -u +"%Y-%m-%d")
  CUTOFF=$(date -u -d "-${MIN_REHUNT_DAYS} days" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null \
           || date -u -v-"${MIN_REHUNT_DAYS}"d +"%Y-%m-%dT%H:%M:%SZ")  # macOS fallback

  # Pick highest-score pending target not hunted too recently
  NEXT=$(jq --arg cutoff "$CUTOFF" '
    [.[] | select(
      .status == "pending" and
      (.last_hunted == null or .last_hunted < $cutoff)
    )]
    | sort_by(-(.score + .boost))
    | first // empty
  ' "$QUEUE_FILE")

  if [[ -z "$NEXT" || "$NEXT" == "null" ]]; then
    echo "NO_TARGETS_AVAILABLE"
    unlock
    exit 0
  fi

  HANDLE=$(echo "$NEXT" | jq -r '.handle')

  # Mark as active in queue
  jq --arg h "$HANDLE" --arg ts "$NOW" '
    map(if .handle == $h then .status = "active" | .started_at = $ts else . end)
  ' "$QUEUE_FILE" > /tmp/queue-tmp.json && mv /tmp/queue-tmp.json "$QUEUE_FILE"

  echo "$NEXT"
  unlock
}

# ── done ───────────────────────────────────────────────────────────────────────

cmd_done() {
  HANDLE="${2:-}"
  BUGS="${3:-0}"
  VERDICT="${4:-UNKNOWN}"
  [[ -z "$HANDLE" ]] && { echo "Usage: queue-manager.sh done <handle> <bugs_found> <verdict>" >&2; exit 1; }

  lock
  require_queue
  NOW=$(ts)

  # Compute rehunt_after (days from now based on richness)
  case "$VERDICT" in
    RICH_TARGET)   REHUNT_DAYS=3  ;;
    MODERATE)      REHUNT_DAYS=7  ;;
    THIN_TARGET)   REHUNT_DAYS=30 ;;
    WAF_BLOCKED)   REHUNT_DAYS=14 ;;
    AUTH_BLOCKED)  REHUNT_DAYS=14 ;;
    *)             REHUNT_DAYS=7  ;;
  esac
  REHUNT_AFTER=$(date -u -d "+${REHUNT_DAYS} days" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null \
                 || date -u -v+"${REHUNT_DAYS}"d +"%Y-%m-%dT%H:%M:%SZ")

  jq --arg h "$HANDLE" --arg ts "$NOW" --argjson bugs "$BUGS" \
     --arg verdict "$VERDICT" --arg rehunt "$REHUNT_AFTER" '
    map(if .handle == $h then
      .status = "done" |
      .last_hunted = $ts |
      .last_verdict = $verdict |
      .bugs_found = (.bugs_found + $bugs) |
      .active_worker = null |
      .rehunt_after = $rehunt
    else . end)
  ' "$QUEUE_FILE" > /tmp/queue-tmp.json && mv /tmp/queue-tmp.json "$QUEUE_FILE"

  # Append to history
  echo "{\"ts\":\"$NOW\",\"handle\":\"$HANDLE\",\"bugs\":$BUGS,\"verdict\":\"$VERDICT\",\"rehunt_after\":\"$REHUNT_AFTER\"}" \
    >> "$HISTORY_FILE"

  echo "Marked $HANDLE as done (bugs=$BUGS, verdict=$VERDICT, rehunt_after=$REHUNT_AFTER)"
  unlock
}

# ── skip ───────────────────────────────────────────────────────────────────────

cmd_skip() {
  HANDLE="${2:-}"
  REASON="${3:-Thin attack surface}"
  [[ -z "$HANDLE" ]] && { echo "Usage: queue-manager.sh skip <handle> [reason]" >&2; exit 1; }

  lock
  require_queue
  NOW=$(ts)
  REHUNT_AFTER=$(date -u -d "+30 days" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null \
                 || date -u -v+30d +"%Y-%m-%dT%H:%M:%SZ")

  jq --arg h "$HANDLE" --arg ts "$NOW" --arg reason "$REASON" --arg rehunt "$REHUNT_AFTER" '
    map(if .handle == $h then
      .status = "skipped" |
      .last_hunted = $ts |
      .last_verdict = ("SKIPPED: " + $reason) |
      .active_worker = null |
      .rehunt_after = $rehunt
    else . end)
  ' "$QUEUE_FILE" > /tmp/queue-tmp.json && mv /tmp/queue-tmp.json "$QUEUE_FILE"

  echo "{\"ts\":\"$NOW\",\"handle\":\"$HANDLE\",\"bugs\":0,\"verdict\":\"SKIPPED\",\"reason\":\"$REASON\",\"rehunt_after\":\"$REHUNT_AFTER\"}" \
    >> "$HISTORY_FILE"

  echo "Skipped $HANDLE (reason: $REASON, rehunt_after=$REHUNT_AFTER)"
  unlock
}

# ── fail ───────────────────────────────────────────────────────────────────────

cmd_fail() {
  HANDLE="${2:-}"
  REASON="${3:-Unknown error}"
  [[ -z "$HANDLE" ]] && { echo "Usage: queue-manager.sh fail <handle> [reason]" >&2; exit 1; }

  lock
  require_queue
  NOW=$(ts)

  jq --arg h "$HANDLE" --arg ts "$NOW" --arg reason "$REASON" '
    map(if .handle == $h then
      .status = "pending" |
      .last_verdict = ("FAILED: " + $reason) |
      .active_worker = null |
      .started_at = null
    else . end)
  ' "$QUEUE_FILE" > /tmp/queue-tmp.json && mv /tmp/queue-tmp.json "$QUEUE_FILE"

  echo "Reset $HANDLE to pending after failure: $REASON"
  unlock
}

# ── status ─────────────────────────────────────────────────────────────────────

cmd_status() {
  require_queue
  echo ""
  echo "═══════════════════════════════════════════════════════════════"
  echo "  HACKBOT TARGET QUEUE"
  echo "═══════════════════════════════════════════════════════════════"
  printf "  %-5s %-22s %-10s %-8s %-8s %-10s\n" "RANK" "HANDLE" "STATUS" "SCORE" "BUGS" "LAST"
  echo "  ─────────────────────────────────────────────────────────────"

  jq -r '
    to_entries[] |
    [
      (.key+1 | tostring),
      .value.handle,
      .value.status,
      ((.value.score + .value.boost) | tostring),
      (.value.bugs_found | tostring),
      (.value.last_hunted // "never" | split("T")[0])
    ] | @tsv
  ' "$QUEUE_FILE" | while IFS=$'\t' read -r rank handle status score bugs last; do
    case "$status" in
      pending)  COLOR="\033[32m" ;;
      active)   COLOR="\033[33m" ;;
      done)     COLOR="\033[90m" ;;
      skipped)  COLOR="\033[90m" ;;
      *)        COLOR="\033[0m"  ;;
    esac
    printf "  ${COLOR}%-5s %-22s %-10s %-8s %-8s %-10s\033[0m\n" \
      "$rank" "$handle" "$status" "$score" "$bugs" "$last"
  done

  echo ""
  STATS=$(jq '{
    total: length,
    pending:  [.[] | select(.status=="pending")] | length,
    active:   [.[] | select(.status=="active")] | length,
    done:     [.[] | select(.status=="done")] | length,
    skipped:  [.[] | select(.status=="skipped")] | length,
    total_bugs: [.[].bugs_found] | add // 0
  }' "$QUEUE_FILE")

  echo "  Total: $(echo $STATS | jq .total)  Pending: $(echo $STATS | jq .pending)  Active: $(echo $STATS | jq .active)  Done: $(echo $STATS | jq .done)  Skipped: $(echo $STATS | jq .skipped)  Bugs found: $(echo $STATS | jq .total_bugs)"
  echo "═══════════════════════════════════════════════════════════════"
  echo ""
}

# ── history ────────────────────────────────────────────────────────────────────

cmd_history() {
  [[ -f "$HISTORY_FILE" ]] || { echo "No hunt history yet."; exit 0; }
  echo ""
  echo "═══════════════════ HUNT HISTORY ═══════════════════"
  printf "  %-20s %-22s %-5s %-20s\n" "DATE" "HANDLE" "BUGS" "VERDICT"
  echo "  ────────────────────────────────────────────────────"
  jq -r '. | [.ts[0:10], .handle, (.bugs|tostring), .verdict] | @tsv' "$HISTORY_FILE" \
    | tail -30 \
    | while IFS=$'\t' read -r date handle bugs verdict; do
        printf "  %-20s %-22s %-5s %-20s\n" "$date" "$handle" "$bugs" "$verdict"
      done
  echo ""
}

# ── reset ──────────────────────────────────────────────────────────────────────

cmd_reset() {
  HANDLE="${2:-}"
  [[ -z "$HANDLE" ]] && { echo "Usage: queue-manager.sh reset <handle>" >&2; exit 1; }
  lock
  require_queue
  jq --arg h "$HANDLE" '
    map(if .handle == $h then
      .status = "pending" | .active_worker = null |
      .started_at = null | .last_hunted = null | .rehunt_after = null
    else . end)
  ' "$QUEUE_FILE" > /tmp/queue-tmp.json && mv /tmp/queue-tmp.json "$QUEUE_FILE"
  echo "Reset $HANDLE to pending"
  unlock
}

# ── requeue ────────────────────────────────────────────────────────────────────

cmd_requeue() {
  HANDLE="${2:-}"
  DAYS="${3:-7}"
  [[ -z "$HANDLE" ]] && { echo "Usage: queue-manager.sh requeue <handle> <days>" >&2; exit 1; }
  lock
  require_queue
  NOW=$(ts)
  REHUNT_AFTER=$(date -u -d "+${DAYS} days" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null \
                 || date -u -v+"${DAYS}"d +"%Y-%m-%dT%H:%M:%SZ")
  jq --arg h "$HANDLE" --arg rehunt "$REHUNT_AFTER" '
    map(if .handle == $h then
      .status = "done" | .rehunt_after = $rehunt
    else . end)
  ' "$QUEUE_FILE" > /tmp/queue-tmp.json && mv /tmp/queue-tmp.json "$QUEUE_FILE"
  echo "Requeued $HANDLE — will re-appear after $REHUNT_AFTER"
  unlock
}

# ── boost ──────────────────────────────────────────────────────────────────────

cmd_boost() {
  HANDLE="${2:-}"
  PTS="${3:-20}"
  [[ -z "$HANDLE" ]] && { echo "Usage: queue-manager.sh boost <handle> <points>" >&2; exit 1; }
  lock
  require_queue
  jq --arg h "$HANDLE" --argjson pts "$PTS" '
    map(if .handle == $h then .boost = (.boost + $pts) else . end)
  ' "$QUEUE_FILE" > /tmp/queue-tmp.json && mv /tmp/queue-tmp.json "$QUEUE_FILE"
  echo "Boosted $HANDLE by +$PTS points"
  unlock
}

# ── dispatch ───────────────────────────────────────────────────────────────────

CMD="${1:-status}"
case "$CMD" in
  init)     cmd_init ;;
  next)     cmd_next ;;
  done)     cmd_done "$@" ;;
  skip)     cmd_skip "$@" ;;
  fail)     cmd_fail "$@" ;;
  status)   cmd_status ;;
  history)  cmd_history ;;
  reset)    cmd_reset "$@" ;;
  requeue)  cmd_requeue "$@" ;;
  boost)    cmd_boost "$@" ;;
  *)        echo "Unknown command: $CMD"; echo "Commands: init next done skip fail status history reset requeue boost"; exit 1 ;;
esac
