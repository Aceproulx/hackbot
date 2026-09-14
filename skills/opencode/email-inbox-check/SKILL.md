---
name: inbox-check
description: Check hackbot's AgentMail inbox without burning context on raw MIME headers. Filtered list first, full body only for the one message that matters. Falls back to Composio Gmail (CLI) if AgentMail is down.
---

# Inbox Check

## Rule — Never Dump Raw Headers
The raw `/messages` list endpoint returns full MIME headers (DKIM, ARC-Seal,
Gm-Message-State, etc.) — none of it actionable, all of it context. Every
list call goes through the jq filter below. No exceptions, no "just this
once to see the full thing."

## Step 1 — List (filtered)
```bash
curl -s -X GET "https://api.agentmail.to/v0/inboxes/$INBOX/messages" \
  -H "Authorization: Bearer $AGENTMAIL_KEY" \
  | jq '[.messages[] | {message_id, from, reply_to, subject, preview, timestamp}]'
```
Returns just enough to decide which message (if any) is worth opening. Use
this for routine polling / triage — never the raw endpoint.

## Step 2 — Only if a message needs full body
Don't re-list. Fetch that single message and pull the extracted body, not
the header block:
```bash
curl -s -X GET "https://api.agentmail.to/v0/inboxes/$INBOX/messages/$MESSAGE_ID" \
  -H "Authorization: Bearer $AGENTMAIL_KEY" \
  | jq '{from, subject, extracted_text, extracted_html}'
```
`extracted_text`/`extracted_html` strip quoted reply history automatically —
this is the field to reason over, not `text`/`html` (which include the full
thread) and never `headers`.

## Decision Rule
- Triage / "anything new?" → Step 1 only.
- Acting on a specific message (replying, extracting an OTP, reading a full
  report) → Step 1 to find the `message_id`, then Step 2 on that one ID only.
- Never loop Step 2 across every message in a list — that's the exact
  context burn this skill exists to prevent.

## Address Generation — For Test Account Registration
Base address: `{{INTIGRITI_USERNAME}}@{{EMAIL_DOMAIN}}`. Both `+` and `-` are valid separators
— anything appended after either lands in the same inbox:
- `{{EMAIL_BASE}}+<tag>@{{EMAIL_DOMAIN}}`
- `{{EMAIL_BASE}}-<tag>@{{EMAIL_DOMAIN}}`

Use this whenever a hunt needs a fresh registration email (userA, userB,
throwaway signups, per-target isolation) instead of asking or reusing a
fixed address:
```bash
# Per-target, per-role tag keeps inbox triage sane later
EMAIL_A="{{EMAIL_BASE}}+${TARGET}-a@{{EMAIL_DOMAIN}}"
EMAIL_B="{{EMAIL_BASE}}+${TARGET}-b@{{EMAIL_DOMAIN}}"
```
Tag convention: `<target>-<role>` (e.g. `magnific-a`, `1win-victim`,
`dedistart-b`). This keeps Step 1's filtered list scannable — the tag in
the `subject`/`to` line tells you at a glance which hunt and which role a
verification email belongs to without opening it.

Every one of these forwards into the same `hackbot.prime@agentmail.to`
inbox — Step 1's list command already surfaces all of them, no separate
inbox to check per tag.

## Credential Persistence — Per-Hunt Test Accounts
This ties into the existing `~/hunts/sessions/<domain>/` structure from
bug-hunting (userA.json/userB.json hold auth *state* — cookies/tokens).
This is the missing piece: the plaintext email+password used to *create*
that account, so a session can be recreated if it expires and re-login is
needed without re-registering.

Store alongside the session files:
```bash
# ~/hunts/sessions/<domain>/userA.creds
cat > ~/hunts/sessions/${TARGET}/userA.creds <<EOF
email={{EMAIL_BASE}}+${TARGET}-a@{{EMAIL_DOMAIN}}
password=${GENERATED_PASSWORD}
created=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
chmod 600 ~/hunts/sessions/${TARGET}/userA.creds
```
Same for `userB.creds`. `chmod 600` — these are real credentials on real
(if throwaway) accounts, keep them out of group/world read.

**Write this immediately after registration succeeds**, before moving on to
testing — not as an end-of-hunt cleanup step you might skip.

**On re-auth**: check for a `.creds` file before registering a new account.
If one exists and isn't tied to a dead/banned account, log back in with it
and refresh the session state file, rather than creating yet another
throwaway user for the same target.

## Replying
Use the `reply` endpoint directly with the `message_id` from Step 1/2 —
don't re-fetch first if you already have the ID and know what to send:
```bash
curl -s -X POST "https://api.agentmail.to/v0/inboxes/$INBOX/messages/$MESSAGE_ID/reply" \
  -H "Authorization: Bearer $AGENTMAIL_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "reply body here"}'
```

## Fallback — Composio Gmail (AgentMail down)
If AgentMail is unreachable, erroring, or `$AGENTMAIL_KEY` is dead, switch to
the Composio CLI (already authed — `composio whoami` to verify). Same
discipline as above applies unchanged: filtered list first, open only the one
message you need. Never paste raw payloads into context.

### List (filtered)
```bash
composio execute GMAIL_FETCH_EMAILS \
  -d '{"query":"in:inbox","max_results":10,"include_payload":false}' \
  | jq '[.data.messages[] | {id: .messageId, from: .sender, subject, ts: .messageTimestamp, preview: .preview.body}]'
```
Gmail search operators work in `query`: `from:`, `subject:`, `is:unread`,
`after:YYYY/MM/DD`. Filter by hunt tag with `"query":"in:inbox subject:<target>"`.
Note `.preview.body` is already truncated by Composio — don't fetch bodies for
triage.

### One message's body
```bash
composio execute GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID \
  -d '{"message_id":"<ID>","format":"metadata"}'   # subject/sender checks only
composio execute GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID \
  -d '{"message_id":"<ID>","format":"full"}'       # when body is actually needed
```
With `format:"full"`, bodies are base64url-encoded under
`.payload.parts[].body.data` (`-`→`+`, `_`→`/`, fix padding) — decode to a
file or pipe, don't dump into context.

### Sending / replying
```bash
# Reply in-thread
composio execute GMAIL_REPLY_TO_THREAD -d '{thread_id:"<TID>", recipient_email:"<to>", message_body:"..."}'
# New mail (e.g. sending creds/report)
composio execute GMAIL_SEND_EMAIL -d '{recipient_email:"<to>", subject:"...", body:"..."}'
```
Unknown slug → `composio search "<use case>"`, then check inputs with
`composio execute <SLUG> --get-schema`.

### Address tagging — parity with AgentMail
All `{{EMAIL_BASE}}+<tag>@{{EMAIL_DOMAIN}}` mail forwards into this Gmail too — same
messages as the AgentMail inbox, so every flow above (tagged test-account
registrations, OTP extraction, per-target triage) works unchanged as a
fallback. Filter by tag (`to:{{EMAIL_DOMAIN}}` is precise; bare `to:{{INTIGRITI_USERNAME}}`
over-matches GitHub notifications):
```bash
composio execute GMAIL_FETCH_EMAILS \
  -d '{"query":"in:inbox to:{{EMAIL_DOMAIN}}","max_results":10,"include_payload":false}' \
  | jq '[.data.messages[] | {id: .messageId, from: .sender, subject, ts: .messageTimestamp}]'
```
Prefer {{EMAIL_DOMAIN}} tags over Gmail's own `+` addressing
(`masangamike07+...@gmail.com`) so both inboxes stay interchangeable —
this is the real account, keep hunt traffic on the alias domain.
