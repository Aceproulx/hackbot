#!/usr/bin/env bash
# queue-manager.sh — Hackbot Target Queue Manager
#
# Commands:
#   init                   Pull programs from Intigriti, build/refresh queue
#   next                   Print the next pending target as JSON, mark it active
#   done <handle> <bugs> <verdict>   Mark target complete (releases pool slot)
#   skip <handle> [reason] Mark target skipped (thin/WAF/no-auth)
#   fail <handle> [reason] Mark target failed (crash/error)
#   release <handle>       Idempotent pool-slot release (heals drift)
#   status                 Print current queue table
#   history                Print past hunts from history log
#   reset <handle>         Reset a target back to pending
#   requeue <handle> <days> Re-queue a target to be hunted again in N days
#   boost <handle> <pts>   Add score boost to a target (e.g. after finding a bug)
#   add <url> [name] [notes]  Add a self-hosted / non-platform target (full browser scope, no bounty ceiling)

set -euo pipefail

QUEUE_FILE={{HACKBOT_MISC_DIR}}/target-queue.json
HISTORY_FILE={{HACKBOT_MISC_DIR}}/queue-history.jsonl
POOL_STATE={{HACKBOT_MISC_DIR}}/worker-pool/pool.json
FINDINGS_FILE={{HACKBOT_MISC_DIR}}/findings.jsonl
POOL_SESSION="hackbot"
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

# slugify a hostname into a queue handle: lowercase, alnum + hyphens only
slugify_host() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g'
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
    'node /home/aceos/Projects/intigriti-mcp/dist/index.js list-programs 2>/dev/null',
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
    # The API caps `limit` per page (limit=1000 => HTTP 400) and reports the
    # true total in `maxCount`. A single page of 100 silently dropped ~2/3 of
    # in-scope programs — including most InviteOnly private invites — so page
    # through with `offset` and merge every page until a short page comes back.
    _PAGE=500
    _OFFSET=0
    _PARTS=""
    while :; do
      _PAGE_JSON=$(curl -s \
        -H "Authorization: Bearer ${INTIGRITI_API_TOKEN}" \
        "https://api.intigriti.com/external/researcher/v1/programs?status=open&limit=${_PAGE}&offset=${_OFFSET}" \
        2>/dev/null || echo '')
      _N=$(printf '%s' "$_PAGE_JSON" | jq -r '(.records // []) | length' 2>/dev/null || echo 0)
      if [[ -z "$_PAGE_JSON" || "$_N" -eq 0 ]]; then break; fi
      _PARTS+="$_PAGE_JSON"$'\n'
      _OFFSET=$(( _OFFSET + _N ))
      if [[ "$_N" -lt "$_PAGE" || "$_OFFSET" -ge 5000 ]]; then break; fi
    done
    PROGRAMS_JSON=$(printf '%s' "${_PARTS:-}" | jq -s '{records: (map(.records // []) | add // [])}' 2>/dev/null || echo '{"records":[]}')
    _FETCHED=$(printf '%s' "$PROGRAMS_JSON" | jq -r '(.records // []) | length' 2>/dev/null || echo 0)
    if [[ "$_FETCHED" -eq 0 ]]; then
      echo "ERROR: Intigriti fetch returned no programs (missing token / network?) — refusing to overwrite queue." >&2
      unlock
      exit 1
    fi
    echo "Fetched ${_FETCHED} open programs from Intigriti."
  fi

  # Load existing queue if present (to preserve history/scores)
  EXISTING="[]"
  [[ -f "$QUEUE_FILE" ]] && EXISTING=$(cat "$QUEUE_FILE")

  # Build new queue with jq — merge existing entries, add new ones
  NEW_QUEUE=$(echo "$PROGRAMS_JSON" "$EXISTING" | jq -s '
    # normalize both inputs (REST returns objects: {value:..}/{"id","value"})
    def existing_map: .[1] | map({(.handle): .}) | add // {};
    def programs: .[0] | if type == "array" then . else (.records // []) end;
    def st:  if (.status|type) == "object" then ((.status.value // "")|ascii_downcase) else (.status // "") end;
    def maxv: if (.maxBounty|type) == "object" then (.maxBounty.value // 0) else (.maxBounty // 0) end;
    def minv: if (.minBounty|type) == "object" then (.minBounty.value // 0) else (.minBounty // 0) end;
    def conf: if (.confidentialityLevel|type) == "object" then (.confidentialityLevel.value // "Public") else (.confidentialityLevel // "Public") end;

    programs as $progs |
    existing_map as $ex |
    ($progs
      | map(select(st == "open" and (maxv // 0) > 0))
      | map({
          handle:               .handle,
          program_id:           .id,
          name:                 .name,
          max_bounty:           maxv,
          min_bounty:           minv,
          tags:                 (.tags // []),
          confidentiality:      conf,
          status:               ($ex[.handle].status // "pending"),
          score:                ($ex[.handle].score // (
            # base score from bounty
            if maxv >= 10000 then 30
            elif maxv >= 5000 then 20
            elif maxv >= 1000 then 10
            else 5 end
          )),
          boost:                ($ex[.handle].boost // 0),
          bugs_found:           ($ex[.handle].bugs_found // 0),
          last_hunted:          ($ex[.handle].last_hunted // null),
          last_verdict:         ($ex[.handle].last_verdict // null),
          active_worker:        null,
          started_at:           null,
          queued_at:            (($ex[.handle].queued_at // now) | if type == "string" then (try fromdateiso8601 catch now) else . end | todate),
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
      | sort_by(.queued_at, -(.score + .boost))) as $new_progs |
    # Preserve self-hosted targets through refreshes (no Intigriti program behind them)
    ($ex | to_entries | map(select(.value.self_hosted == true)) | map(.value)) as $selfhosted |
    ($new_progs + $selfhosted)
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

  # Count currently active targets per pool (self-hosted vs Intigriti)
  ACTIVE_SELF=$(jq '[.[] | select(.status == "active" and (.program_id | startswith("self:")))] | length' "$QUEUE_FILE")
  ACTIVE_INT=$(jq '[.[] | select(.status == "active" and (.program_id | startswith("self:") | not))] | length' "$QUEUE_FILE")

  # Alternate pools in blocks of 2: keep 2 self-hosted + 2 Intigriti running.
  # Prefer the pool that's under its quota; fall back to the other if empty.
  if [[ "$ACTIVE_SELF" -lt 2 ]]; then
    PREFER="self"
  else
    PREFER="intigriti"
  fi

  # Pick highest-score pending target from the preferred pool
  NEXT=$(jq --arg cutoff "$CUTOFF" --arg prefer "$PREFER" '
    [.[] | select(
      .status == "pending" and
      (.last_hunted == null or .last_hunted < $cutoff) and
      (if $prefer == "self" then (.program_id | startswith("self:"))
       else (.program_id | startswith("self:") | not) end)
    )]
    | sort_by(.queued_at, -(.score + .boost))
    | first // empty
  ' "$QUEUE_FILE")

  # Fallback: preferred pool exhausted -> take from the other pool
  if [[ -z "$NEXT" || "$NEXT" == "null" ]]; then
    NEXT=$(jq --arg cutoff "$CUTOFF" --arg prefer "$PREFER" '
      [.[] | select(
        .status == "pending" and
        (.last_hunted == null or .last_hunted < $cutoff) and
        (if $prefer == "self" then (.program_id | startswith("self:") | not)
         else (.program_id | startswith("self:")) end)
      )]
      | sort_by(.queued_at, -(.score + .boost))
      | first // empty
    ' "$QUEUE_FILE")
  fi

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

# Free the worker-pool slot for a target that has finished. Workers end their
# session by calling `hackbot-queue done` and then sit idle at a tmux shell;
# unless the slot is cleared here, pool.json keeps it "running" forever, the
# refill watcher sees no free slot, and queued targets never start. Only the
# pool record is touched — the queue is already being updated by the caller.
release_pool_slot() {
  local H="$1" NOTE="${2:-session completed: queue marked done}"
  [[ -n "$H" && -f "$POOL_STATE" ]] || return 0

  local SLOT
  SLOT=$(jq -r --arg h "$H" \
    '[.workers[] | select(.handle==$h and .status=="running")][0].slot // empty' \
    "$POOL_STATE" 2>/dev/null || true)

  if jq --arg h "$H" --arg ts "$(ts)" --arg note "$NOTE" '
      .workers |= map(if .handle == $h and .status == "running"
        then .status = "done" | .done_at = $ts | .done_note = $note
        else . end)
    ' "$POOL_STATE" > /tmp/pool-tmp.json 2>/dev/null; then
    mv /tmp/pool-tmp.json "$POOL_STATE"
  fi

  # The window outlives `opencode run` as an idle shell — kill it so the slot
  # is genuinely free (and so the watchdog does not read it as a lost worker).
  if [[ -n "$SLOT" ]] && command -v tmux >/dev/null 2>&1; then
    tmux kill-window -t "${POOL_SESSION}:${SLOT}" 2>/dev/null || true
  fi
}

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

  # The worker's self-reported bug count is unreliable — workers routinely
  # pass 0 even after logging confirmed findings. The authoritative count
  # comes from the findings log: confirmed findings for this program.
  REAL_BUGS=0
  if [[ -f "$FINDINGS_FILE" ]]; then
    REAL_BUGS=$(jq -s -r --arg h "$HANDLE" \
      '[.[] | select(.program == $h and .status == "confirmed")] | length' \
      "$FINDINGS_FILE" 2>/dev/null || echo 0)
  fi
  # Never let an under-report zero out a real count; fall back to the worker's
  # number only when the findings log has nothing for this program.
  if [[ "$REAL_BUGS" -lt "$BUGS" ]]; then
    REAL_BUGS="$BUGS"
  fi

  jq --arg h "$HANDLE" --arg ts "$NOW" --argjson bugs "$REAL_BUGS" \
     --arg verdict "$VERDICT" --arg rehunt "$REHUNT_AFTER" '
    map(if .handle == $h then
      .status = "done" |
      .last_hunted = $ts |
      .last_verdict = $verdict |
      .bugs_found = $bugs |
      .active_worker = null |
      .rehunt_after = $rehunt
    else . end)
  ' "$QUEUE_FILE" > /tmp/queue-tmp.json && mv /tmp/queue-tmp.json "$QUEUE_FILE"

  # Append to history
  echo "{\"ts\":\"$NOW\",\"handle\":\"$HANDLE\",\"bugs\":$REAL_BUGS,\"verdict\":\"$VERDICT\",\"rehunt_after\":\"$REHUNT_AFTER\"}" \
    >> "$HISTORY_FILE"

  # Release the pool slot so the refill watcher can start the next target.
  release_pool_slot "$HANDLE"

  # Fire the completion alert. Single source of truth: every worker calls
  # `hackbot-queue done`, so this covers old-contract workers too (the alert
  # used to live only in the worker prompt, which pre-fix workers lacked).
  "$NOTIFY" done "$HANDLE" "$REAL_BUGS" "$VERDICT" >/dev/null 2>&1 || true

  echo "Marked $HANDLE as done (bugs=$REAL_BUGS, verdict=$VERDICT, rehunt_after=$REHUNT_AFTER)"
  unlock
}

# ── release ────────────────────────────────────────────────────────────────────

# Idempotent slot release for a target that is already finished (queue status
# "done"). Used to heal drift — e.g. a worker killed after writing its session
# log — and by the refill watcher's reconcile pass. Never touches queue
# bookkeeping.
cmd_release() {
  local HANDLE="${2:-}"
  [[ -z "$HANDLE" ]] && { echo "Usage: queue-manager.sh release <handle>" >&2; exit 1; }
  release_pool_slot "$HANDLE" "${3:-}"
  echo "Released pool slot for '$HANDLE' (if it was running)"
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
  NOW=$(ts)
  jq --arg h "$HANDLE" --arg ts "$NOW" '
    map(if .handle == $h then
      .status = "pending" | .active_worker = null |
      .started_at = null | .last_hunted = null | .rehunt_after = null |
      .queued_at = $ts
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

# ── add (self-hosted / non-platform target) ───────────────────────────────────

cmd_add() {
  URL="${2:-}"
  NAME="${3:-$URL}"
  NOTES="${4:-}"
  [[ -z "$URL" ]] && { echo "Usage: queue-manager.sh add <url> [name] [notes]" >&2; exit 1; }

  # normalize — default to https:// if no scheme given
  [[ "$URL" =~ ^[a-zA-Z][a-zA-Z0-9+.-]*:// ]] || URL="https://$URL"

  HOST=$(echo "$URL" | sed -E 's~^[a-zA-Z][a-zA-Z0-9+.-]*://~~; s~[/?#].*$~~; s~:.*$~~')
  [[ -z "$HOST" ]] && { echo "ERROR: could not parse a host from '$URL'" >&2; exit 1; }
  HANDLE=$(slugify_host "$HOST")
  [[ -z "$HANDLE" ]] && HANDLE="self-$(date -u +%s)"

  lock
  [[ -f "$QUEUE_FILE" ]] || echo "[]" > "$QUEUE_FILE"

  if jq -e --arg h "$HANDLE" '.[] | select(.handle == $h)' "$QUEUE_FILE" >/dev/null 2>&1; then
    echo "ERROR: target '$HANDLE' is already in the queue (re-run 'reset $HANDLE' to re-hunt it)" >&2
    unlock
    exit 1
  fi

  NOW=$(ts)
  jq --arg h "$HANDLE" --arg url "$URL" --arg name "$NAME" --arg notes "$NOTES" --arg ts "$NOW" '
    . + [{
      handle: $h,
      program_id: ("self:" + $h),
      name: $name,
      base_url: $url,
      max_bounty: 0,
      min_bounty: 0,
      tags: ["self-hosted"],
      confidentiality: "private",
      status: "pending",
      score: 50,
      boost: 0,
      bugs_found: 0,
      last_hunted: null,
      last_verdict: null,
      active_worker: null,
      started_at: null,
      queued_at: $ts,
      rehunt_after: null,
      self_hosted: true,
      browser_scope: "full",
      notes: $notes
    }]
  ' "$QUEUE_FILE" > /tmp/queue-tmp.json && mv /tmp/queue-tmp.json "$QUEUE_FILE"

  echo "{\"ts\":\"$NOW\",\"handle\":\"$HANDLE\",\"event\":\"added\",\"url\":\"$URL\",\"self_hosted\":true}" \
    >> "$HISTORY_FILE"

  echo "Added self-hosted target '$HANDLE' ($URL) — full browser scope, no bounty ceiling, no platform rules apply"
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
  release)  cmd_release "$@" ;;
  status)   cmd_status ;;
  history)  cmd_history ;;
  reset)    cmd_reset "$@" ;;
  requeue)  cmd_requeue "$@" ;;
  boost)    cmd_boost "$@" ;;
  add)      cmd_add "$@" ;;
  *)        echo "Unknown command: $CMD"; echo "Commands: init next done skip fail release status history reset requeue boost add"; exit 1 ;;
esac
