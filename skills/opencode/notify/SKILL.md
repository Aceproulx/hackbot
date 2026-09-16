---
name: notify
description: "Hackbot Telegram notification layer. Use this skill to fire typed notifications to the operator's Telegram when key events happen during autonomous hunts: bugs confirmed, workers killed/encouraged, session start/end, WAF blocks, auth walls, interesting behaviors. Always call this — never skip notifications on important events."
---


# Hackbot Notify

## Overview
Sends typed Telegram messages to the operator. Uses the `hackbot-notify`
command (symlinked to `{{HACKBOT_MISC_DIR}}/notify/notify-telegram.sh`).
Credentials live in env: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.

**Never skip notifications on these events** — the operator is away and this
is their only window into what the bot is doing.

---

## Command Reference

### Bug Confirmed 🔴🟠🟡🟢
Fire immediately when `@bug-validator` returns CONFIRMED:
```bash
hackbot-notify bug "<program_handle>" "<bug_title>" "<severity>" "<bounty_estimate>"
# Severity: Critical | High | Medium | Low
# Example:
hackbot-notify bug "example-inc" "IDOR on /api/user/{id}" "High" "2000"
```

### Worker Encouraged 💪
Fire when orchestrator sends an encourage signal to a worker:
```bash
hackbot-notify encourage "<domain>"
# Example:
hackbot-notify encourage "app.example.com"
```

### Worker Killed 🛑
Fire when orchestrator kills a worker early:
```bash
hackbot-notify kill "<domain>" "<reason>"
# Example:
hackbot-notify kill "thin.example.com" "No auth surface after 30 min"
```

### Target Skipped ⏭
Fire when orchestrator skips a target in Phase 2 (THIN verdict):
```bash
hackbot-notify skip "<domain>" "<reason>"
# Example:
hackbot-notify skip "static.example.com" "Static marketing site only"
```

### Session Start 🤖
Fire once at the top of Phase 0:
```bash
hackbot-notify session-start "$SESSION_DIR"
```

### Session End 📊
Fire at session exit (SIGTERM):
```bash
hackbot-notify session-end "$SESSION_DIR" "<bugs_confirmed>" "<total_bounty_est>"
# Example:
hackbot-notify session-end "$SESSION_DIR" "3" "7500"
```

### Interesting Behavior 👀
Fire when something triggers spidy sense but isn't confirmed yet:
```bash
hackbot-notify interesting "<domain>" "<one-line note>"
# Example:
hackbot-notify interesting "app.example.com" "PATCH /profile accepts role field — testing escalation"
```

### Auth Wall Encountered 🔐
Fire when a target requires manual login (bot can't self-register):
```bash
hackbot-notify needs-auth "<domain>"
```

### WAF Block 🧱
Fire when WAF is killing requests and IP rotation is being attempted:
```bash
hackbot-notify waf-blocked "<domain>"
```

### Plain Message
For anything not covered above:
```bash
hackbot-notify "Your custom message here"
```

---

## Integration Points

### In hunter-orchestrator
```bash
# Phase 0 — session start
hackbot-notify session-start "$SESSION_DIR"

# Phase 2 — thin target skip
hackbot-notify skip "$DOMAIN" "Only $RICH_SIGNALS rich signals"

# Phase 4 — encourage
hackbot-notify encourage "$DOMAIN"

# Phase 4 — kill
hackbot-notify kill "$DOMAIN" "$KILL_REASON"

# Phase 5 — session end
hackbot-notify session-end "$SESSION_DIR" "$TOTAL_BUGS" "$TOTAL_BOUNTY"
```

### In bug-hunting worker (after bug-validator returns CONFIRMED)
```bash
hackbot-notify bug "$PROGRAM" "$BUG_TITLE" "$SEVERITY" "$BOUNTY_EST"
```

### In bug-hunting worker (spidy sense moments)
```bash
hackbot-notify interesting "$TARGET_DOMAIN" "Brief one-liner about what seemed odd"
```

---

## Notification Volume Guidelines

**Always notify:** bug confirmed, session start/end, needs-auth
**Notify once per event:** worker kill, worker encourage, WAF block
**Notify selectively:** interesting behaviors — only when genuinely worth
operator attention, not every HTTP 200 with a slightly longer response time.
Max ~3–5 interesting pings per hunt session to avoid noise.

**Never notify:** routine probe results, 404s, standard redirects, expected
auth flows working normally. Keep the signal-to-noise ratio high — the operator
should act on every message they receive.

---

## Troubleshooting

```bash
# Test manually
hackbot-notify "Test from hackbot at $(date)"

# Check env vars
echo "Token: $TELEGRAM_BOT_TOKEN" && echo "ChatID: $TELEGRAM_CHAT_ID"

# Send raw curl if hackbot-notify isn't in PATH
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="$TELEGRAM_CHAT_ID" \
  -d text="Test" -d parse_mode="Markdown"
```
