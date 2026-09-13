#!/usr/bin/env bash
# hackbot-dashboard.sh — Hackbot Findings Dashboard
#
# Commands:
#   show              Full dashboard — stats + recent findings (default)
#   stats             Stats only
#   findings          All findings table
#   program <handle>  Filter by program
#   severity <sev>    Filter by severity (Critical|High|Medium|Low)
#   log               Log a new finding (interactive or via flags)
#   add               Alias for log
#   export            Export findings to markdown report
#   open              Open the markdown report in the browser (if available)
#
# Log a finding:
#   hackbot-dashboard add \
#     --program "example-inc" \
#     --title "IDOR on /api/user/{id}" \
#     --severity "High" \
#     --status "confirmed" \
#     --bounty 2000 \
#     --evidence "caido:req_abc123" \
#     --url "https://app.example.com/api/user/17"

set -euo pipefail

FINDINGS={{HACKBOT_MISC_DIR}}/findings.jsonl
REPORT_DIR={{HACKBOT_MISC_DIR}}/reports
NOTIFY="hackbot-notify"

# Colors
RED='\033[0;31m'; ORANGE='\033[0;33m'; YELLOW='\033[1;33m'
GREEN='\033[0;32m'; CYAN='\033[0;36m'; GRAY='\033[0;90m'
BOLD='\033[1m'; RESET='\033[0m'

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
today() { date -u +"%Y-%m-%d"; }

sev_color() {
  case "$1" in
    Critical) echo -e "${RED}" ;;
    High)     echo -e "${ORANGE}" ;;
    Medium)   echo -e "${YELLOW}" ;;
    Low)      echo -e "${GREEN}" ;;
    *)        echo -e "${GRAY}" ;;
  esac
}

status_color() {
  case "$1" in
    confirmed)   echo -e "${GREEN}" ;;
    duplicate)   echo -e "${GRAY}" ;;
    informative) echo -e "${GRAY}" ;;
    pending)     echo -e "${YELLOW}" ;;
    triaged)     echo -e "${CYAN}" ;;
    *)           echo -e "${RESET}" ;;
  esac
}

require_findings() {
  [[ -f "$FINDINGS" ]] || { echo -e "${GRAY}No findings logged yet. Start hunting!${RESET}"; exit 0; }
  [[ -s "$FINDINGS" ]] || { echo -e "${GRAY}findings.jsonl is empty.${RESET}"; exit 0; }
}

# ── stats ──────────────────────────────────────────────────────────────────────

cmd_stats() {
  require_findings

  STATS=$(jq -s '{
    total:      length,
    confirmed:  [.[] | select(.status=="confirmed")] | length,
    duplicate:  [.[] | select(.status=="duplicate")] | length,
    informative:[.[] | select(.status=="informative" or .status=="n/a")] | length,
    pending:    [.[] | select(.status=="pending" or .status=="triaged")] | length,
    critical:   [.[] | select(.severity=="Critical")] | length,
    high:       [.[] | select(.severity=="High")] | length,
    medium:     [.[] | select(.severity=="Medium")] | length,
    low:        [.[] | select(.severity=="Low")] | length,
    total_bounty: [.[].bounty_est // 0] | add // 0,
    paid_bounty:  [.[] | select(.bounty_paid != null) | .bounty_paid] | add // 0,
    programs:   [.[].program] | unique | length
  }' "$FINDINGS")

  TOTAL=$(echo "$STATS"     | jq '.total')
  CONFIRMED=$(echo "$STATS" | jq '.confirmed')
  DUPES=$(echo "$STATS"     | jq '.duplicate')
  INFO=$(echo "$STATS"      | jq '.informative')
  PENDING=$(echo "$STATS"   | jq '.pending')
  CRIT=$(echo "$STATS"      | jq '.critical')
  HIGH=$(echo "$STATS"      | jq '.high')
  MED=$(echo "$STATS"       | jq '.medium')
  LOW=$(echo "$STATS"       | jq '.low')
  EST=$(echo "$STATS"       | jq '.total_bounty')
  PAID=$(echo "$STATS"      | jq '.paid_bounty')
  PROGS=$(echo "$STATS"     | jq '.programs')

  # True positive rate = (confirmed + dupes) / total
  if [[ $TOTAL -gt 0 ]]; then
    TP_RATE=$(awk "BEGIN {printf \"%.1f%%\", ($CONFIRMED + $DUPES) * 100 / $TOTAL}")
  else
    TP_RATE="N/A"
  fi

  echo ""
  echo -e "${BOLD}╔══════════════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}║           HACKBOT FINDINGS DASHBOARD             ║${RESET}"
  echo -e "${BOLD}╚══════════════════════════════════════════════════╝${RESET}"
  echo ""
  echo -e "  ${BOLD}OVERVIEW${RESET}"
  echo -e "  ─────────────────────────────────────────────────"
  printf "  %-22s %s\n" "Total findings:" "$TOTAL"
  printf "  %-22s ${GREEN}%s${RESET}\n" "Confirmed / Real:" "$CONFIRMED"
  printf "  %-22s ${GRAY}%s${RESET}\n" "Duplicates:" "$DUPES"
  printf "  %-22s ${GRAY}%s${RESET}\n" "Informative / N/A:" "$INFO"
  printf "  %-22s ${YELLOW}%s${RESET}\n" "Pending / Triaged:" "$PENDING"
  printf "  %-22s %s\n" "Programs hunted:" "$PROGS"
  printf "  %-22s ${BOLD}%s${RESET}\n" "True positive rate:" "$TP_RATE"
  echo ""
  echo -e "  ${BOLD}SEVERITY BREAKDOWN${RESET}"
  echo -e "  ─────────────────────────────────────────────────"
  printf "  ${RED}%-22s %s${RESET}\n"    "Critical:" "$CRIT"
  printf "  ${ORANGE}%-22s %s${RESET}\n" "High:" "$HIGH"
  printf "  ${YELLOW}%-22s %s${RESET}\n" "Medium:" "$MED"
  printf "  ${GREEN}%-22s %s${RESET}\n"  "Low:" "$LOW"
  echo ""
  echo -e "  ${BOLD}BOUNTY${RESET}"
  echo -e "  ─────────────────────────────────────────────────"
  printf "  %-22s ${BOLD}\$%s${RESET}\n" "Estimated total:" "$EST"
  printf "  %-22s ${GREEN}\$%s${RESET}\n" "Paid so far:" "$PAID"
  echo ""
}

# ── findings table ─────────────────────────────────────────────────────────────

cmd_findings() {
  local FILTER="${1:-}"
  local FILTER_VAL="${2:-}"
  require_findings

  echo ""
  echo -e "  ${BOLD}$(printf '%-6s %-20s %-12s %-10s %-9s %-8s %s' 'DATE' 'PROGRAM' 'SEVERITY' 'STATUS' 'BOUNTY' 'DUPES' 'TITLE')${RESET}"
  echo "  ──────────────────────────────────────────────────────────────────────────────────────"

  local JQ_SELECT="true"
  [[ "$FILTER" == "program"  ]] && JQ_SELECT=".program == \"$FILTER_VAL\""
  [[ "$FILTER" == "severity" ]] && JQ_SELECT=".severity == \"$FILTER_VAL\""

  jq -rs "
    .[] | select(${JQ_SELECT:-true}) |
    [
      (.ts[0:10] // \"?\"),
      (.program // \"?\"),
      (.severity // \"?\"),
      (.status // \"?\"),
      ((.bounty_est // 0) | tostring),
      (if .status == \"duplicate\" then \"yes\" else \"no\" end),
      (.title // \"?\")
    ] | @tsv
  " "$FINDINGS" | while IFS=$'\t' read -r date prog sev status bounty dupe title; do
    SEV_C=$(sev_color "$sev")
    ST_C=$(status_color "$status")
    printf "  %-6s ${CYAN}%-20s${RESET} ${SEV_C}%-12s${RESET} ${ST_C}%-10s${RESET} \$%-8s %-8s %s\n" \
      "$date" "${prog:0:20}" "$sev" "$status" "$bounty" "$dupe" "${title:0:50}"
  done
  echo ""
}

# ── log / add finding ──────────────────────────────────────────────────────────

cmd_add() {
  shift  # remove 'add' or 'log'

  PROGRAM=""; TITLE=""; SEVERITY=""; STATUS="confirmed"
  BOUNTY=0; EVIDENCE=""; URL=""; NOTES=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --program)  PROGRAM="$2";  shift 2 ;;
      --title)    TITLE="$2";    shift 2 ;;
      --severity) SEVERITY="$2"; shift 2 ;;
      --status)   STATUS="$2";   shift 2 ;;
      --bounty)   BOUNTY="$2";   shift 2 ;;
      --evidence) EVIDENCE="$2"; shift 2 ;;
      --url)      URL="$2";      shift 2 ;;
      --notes)    NOTES="$2";    shift 2 ;;
      *) shift ;;
    esac
  done

  # Interactive fallback for missing required fields
  [[ -z "$PROGRAM" ]]  && { read -rp "  Program handle: " PROGRAM; }
  [[ -z "$TITLE" ]]    && { read -rp "  Bug title: " TITLE; }
  [[ -z "$SEVERITY" ]] && { read -rp "  Severity (Critical/High/Medium/Low): " SEVERITY; }
  [[ -z "$BOUNTY" || "$BOUNTY" == "0" ]] && { read -rp "  Bounty estimate (\$): " BOUNTY; }

  mkdir -p "$(dirname "$FINDINGS")"
  touch "$FINDINGS"

  ID="f-$(date +%s)-$(openssl rand -hex 3 2>/dev/null || echo $RANDOM)"
  NOW=$(ts)

  ENTRY=$(jq -n \
    --arg id "$ID" \
    --arg ts "$NOW" \
    --arg program "$PROGRAM" \
    --arg title "$TITLE" \
    --arg severity "$SEVERITY" \
    --arg status "$STATUS" \
    --argjson bounty "$BOUNTY" \
    --arg evidence "$EVIDENCE" \
    --arg url "$URL" \
    --arg notes "$NOTES" \
    '{
      id: $id, ts: $ts, program: $program, title: $title,
      severity: $severity, status: $status, bounty_est: $bounty,
      bounty_paid: null, evidence: $evidence, url: $url,
      notes: $notes, reported_at: null, resolved_at: null
    }')

  echo "$ENTRY" >> "$FINDINGS"
  echo -e "\n  ${GREEN}✓ Finding logged: $ID${RESET}"
  echo -e "  $SEVERITY | $PROGRAM | $TITLE | \$$BOUNTY\n"

  # Notify if confirmed
  [[ "$STATUS" == "confirmed" ]] && \
    $NOTIFY bug "$PROGRAM" "$TITLE" "$SEVERITY" "$BOUNTY" 2>/dev/null || true
}

# ── export to markdown ─────────────────────────────────────────────────────────

cmd_export() {
  require_findings
  mkdir -p "$REPORT_DIR"
  OUT="$REPORT_DIR/findings-$(today).md"

  {
    echo "# Hackbot Findings Report"
    echo "_Generated: $(date -u)_"
    echo ""

    # Stats block
    TOTAL=$(jq -rs 'length' "$FINDINGS")
    CONFIRMED=$(jq -rs '[.[] | select(.status=="confirmed")] | length' "$FINDINGS")
    EST=$(jq -rs '[.[].bounty_est // 0] | add // 0' "$FINDINGS")
    echo "## Summary"
    echo "| Metric | Value |"
    echo "|---|---|"
    echo "| Total findings | $TOTAL |"
    echo "| Confirmed | $CONFIRMED |"
    echo "| Est. bounty | \$$EST |"
    echo ""

    echo "## Severity Breakdown"
    echo "| Severity | Count |"
    echo "|---|---|"
    for SEV in Critical High Medium Low; do
      CNT=$(jq -rs --arg s "$SEV" '[.[] | select(.severity==$s)] | length' "$FINDINGS")
      echo "| $SEV | $CNT |"
    done
    echo ""

    echo "## All Findings"
    echo "| Date | Program | Severity | Status | Bounty | Title |"
    echo "|---|---|---|---|---|---|"
    jq -rs '.[] | "| \(.ts[0:10]) | \(.program) | \(.severity) | \(.status) | $\(.bounty_est // 0) | \(.title) |"' \
      "$FINDINGS"
    echo ""

    echo "## Detailed Findings"
    jq -rs '.[]' "$FINDINGS" | jq -rc '.' | while read -r line; do
      TITLE=$(echo "$line" | jq -r '.title')
      SEV=$(echo "$line" | jq -r '.severity')
      PROG=$(echo "$line" | jq -r '.program')
      STATUS=$(echo "$line" | jq -r '.status')
      BOUNTY=$(echo "$line" | jq -r '.bounty_est // 0')
      DATE=$(echo "$line" | jq -r '.ts[0:10]')
      EVIDENCE=$(echo "$line" | jq -r '.evidence // ""')
      URL=$(echo "$line" | jq -r '.url // ""')
      NOTES=$(echo "$line" | jq -r '.notes // ""')
      ID=$(echo "$line" | jq -r '.id')

      echo "### [$SEV] $TITLE"
      echo "- **Program:** $PROG"
      echo "- **Status:** $STATUS"
      echo "- **Date:** $DATE"
      echo "- **Bounty est.:** \$$BOUNTY"
      [[ -n "$EVIDENCE" ]] && echo "- **Evidence:** $EVIDENCE"
      [[ -n "$URL" ]]      && echo "- **URL:** $URL"
      [[ -n "$NOTES" ]]    && echo "- **Notes:** $NOTES"
      echo "- **ID:** \`$ID\`"
      echo ""
    done
  } > "$OUT"

  echo -e "\n  ${GREEN}✓ Report exported: $OUT${RESET}\n"
  echo "$OUT"
}

# ── full dashboard ─────────────────────────────────────────────────────────────

cmd_show() {
  cmd_stats
  cmd_findings "" ""

  # Top programs by bugs
  echo -e "  ${BOLD}TOP PROGRAMS${RESET}"
  echo -e "  ─────────────────────────────────────────────────"
  jq -rs '
    group_by(.program) |
    map({program: .[0].program, bugs: length, bounty: (map(.bounty_est // 0) | add)}) |
    sort_by(-.bugs) | .[:5][] |
    "  \(.program)  bugs=\(.bugs)  est=$\(.bounty)"
  ' "$FINDINGS" 2>/dev/null || true
  echo ""
}

# ── dispatch ───────────────────────────────────────────────────────────────────

CMD="${1:-show}"
case "$CMD" in
  show|dashboard) cmd_show ;;
  stats)          cmd_stats ;;
  findings)       cmd_findings "" "" ;;
  program)        cmd_findings "program" "${2:-}" ;;
  severity)       cmd_findings "severity" "${2:-}" ;;
  log|add)        cmd_add "$@" ;;
  export)         cmd_export ;;
  *)              echo "Commands: show stats findings program severity add log export"; exit 1 ;;
esac
