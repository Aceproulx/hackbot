#!/usr/bin/env bash
# notify-telegram.sh — hackbot Telegram notification helper
# Usage:
#   notify-telegram.sh "<message>"
#   notify-telegram.sh bug "<program>" "<title>" "<severity>" "<bounty_est>"
#   notify-telegram.sh encourage "<domain>"
#   notify-telegram.sh kill "<domain>" "<reason>"
#   notify-telegram.sh session-start "<session_dir>"
#   notify-telegram.sh session-end "<session_dir>" "<bugs>" "<bounty_est>"
#   notify-telegram.sh done "<handle>" "<bugs>" "<verdict>"
#   notify-telegram.sh interesting "<domain>" "<note>"

BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-{{TELEGRAM_BOT_TOKEN}}}"
CHAT_ID="${TELEGRAM_CHAT_ID:-{{TELEGRAM_CHAT_ID}}}"
API="https://api.telegram.org/bot${BOT_TOKEN}/sendMessage"

send() {
  local text="$1"
  curl -s -X POST "$API" \
    -d chat_id="$CHAT_ID" \
    -d parse_mode="Markdown" \
    --data-urlencode "text=$text" \
    -o /dev/null
}

MODE="${1:-plain}"
TS=$(date -u +"%Y-%m-%d %H:%M UTC")

case "$MODE" in

  bug)
    PROGRAM="$2"
    TITLE="$3"
    SEV="$4"
    BOUNTY="$5"
    case "$SEV" in
      Critical) EMOJI="🔴" ;;
      High)     EMOJI="🟠" ;;
      Medium)   EMOJI="🟡" ;;
      Low)      EMOJI="🟢" ;;
      *)        EMOJI="⚪" ;;
    esac
    send "${EMOJI} *BUG CONFIRMED*
*Program:* \`${PROGRAM}\`
*Title:* ${TITLE}
*Severity:* ${SEV}
*Bounty Est:* \$${BOUNTY}
_${TS}_"
    ;;

  encourage)
    DOMAIN="$2"
    send "💪 *ENCOURAGING WORKER*
*Target:* \`${DOMAIN}\`
_Looks juicy — keep digging_
_${TS}_"
    ;;

  kill)
    DOMAIN="$2"
    REASON="$3"
    send "🛑 *WORKER KILLED*
*Target:* \`${DOMAIN}\`
*Reason:* ${REASON}
_${TS}_"
    ;;

  skip)
    DOMAIN="$2"
    REASON="$3"
    send "⏭ *TARGET SKIPPED*
*Target:* \`${DOMAIN}\`
*Reason:* ${REASON:-Thin attack surface}
_${TS}_"
    ;;

  session-start)
    SESSION="$2"
    send "🤖 *HACKBOT SESSION STARTED*
*Session:* \`$(basename $SESSION)\`
_Autonomous hunt beginning — I'll message you when bugs drop_
_${TS}_"
    ;;

  session-end)
    SESSION="$2"
    BUGS="$3"
    BOUNTY="$4"
    send "📊 *SESSION COMPLETE*
*Session:* \`$(basename $SESSION)\`
*Bugs confirmed:* ${BUGS}
*Est. bounty:* \$${BOUNTY}
_${TS}_"
    ;;

  done)
    HANDLE="$2"
    BUGS="$3"
    VERDICT="$4"
    send "✅ *WORKER DONE*
*Target:* \`${HANDLE}\`
*Bugs found:* ${BUGS}
*Verdict:* ${VERDICT}
_${TS}_"
    ;;

  interesting)
    DOMAIN="$2"
    NOTE="$3"
    send "👀 *INTERESTING BEHAVIOR*
*Target:* \`${DOMAIN}\`
*Note:* ${NOTE}
_${TS}_"
    ;;

  needs-auth)
    DOMAIN="$2"
    send "🔐 *AUTH NEEDED*
*Target:* \`${DOMAIN}\`
_Bot can't register — manual login may be required_
_${TS}_"
    ;;

  waf-blocked)
    DOMAIN="$2"
    send "🧱 *WAF BLOCKED*
*Target:* \`${DOMAIN}\`
_IP rotation attempted — moving on_
_${TS}_"
    ;;

  *)
    # Plain message — treat all args as the message
    shift 0
    send "$*"
    ;;

esac
