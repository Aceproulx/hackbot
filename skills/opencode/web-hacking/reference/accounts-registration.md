# Two or more Accounts — Always

Load this before registering any new test account. Requires
`reference/session-bootstrap.md` to already be bootstrapped
(`$AGENT_BROWSER_ACCOUNT` set) — this file assumes that's done.

## Why
IDOR validation requires a DIFFERENT authenticated session — seeing your own
data proves nothing. You need userA → userB cross-check.

## Registration email — MANDATORY, NO EXCEPTIONS
**Never register with `test@test.com`, `test@example.com`, or any made-up
domain.** Registration/verification emails must arrive somewhere real or the
account is useless the moment the target requires email verification.

Every registration email MUST follow this pattern:
```
aceproulx+<target>-a@intigriti.me   # userA
aceproulx+<target>-b@intigriti.me   # userB
```
(`-` also works as the separator if `+` gets stripped by a target's input
validation — try `+` first, fall back to `-`.) These forward into the
hackbot inbox — see the `@email-inbox-check` skill for how to list/read them.

## Phone number verification — sms_fetcher
When a target requires a **phone number** at registration (SMS OTP, 2FA setup,
number ownership check), use the pre-loaded temp numbers via `sms_fetcher`.
Never use your real number. Never make one up — unverifiable numbers mean a
dead account.

**List all available numbers:**
```bash
sms_fetcher --list
# Output:
# Index  Phone Number     Region
# ------------------------------------------
# 1      19392529150      Puerto Rico
# 2      19392348210      Puerto Rico
# 3      19398930201      Puerto Rico
# 4      19395930086      Puerto Rico
# 5      19392980127      Puerto Rico
# 6      12366021668      Canada (BC)
# 7      12364744574      Canada (BC)
```
Pick any number — format for registration: `+<number>` (e.g. `+12366021668`).
Use a **different number for userA and userB** — never the same number on two
accounts for the same target.

**Check received SMS for a number:**
```bash
sms_fetcher -n 12366021668
# Output shows all recent messages with timestamp, sender, and body:
# [2026-09-13T14:01:47Z] From: +1 226-828-0540
#   Please use 218526 as login code for 3Fun (valid in 5 minutes)
```
Extract the OTP/verification code from the message body.

**Standard phone verification flow:**
```
1. Pick a number: sms_fetcher --list → pick index 1 for userA, index 2 for userB
2. Enter number at registration: +19392529150 (userA), +19392348210 (userB)
3. Wait for SMS: sms_fetcher -n 19392529150
   → scan latest message from the target's sender for the OTP code
4. Enter the OTP via Playwright MCP to complete verification
5. Write the chosen number into the creds file:
   echo "phone=+19392529150" >> /home/aceos/Projects/hackbot/hunts/sessions/<target>/userA.creds
```

**If no SMS arrives within 60 seconds:**
- Try requesting the code again (most targets allow a resend)
- If still nothing after 2 attempts, switch to a different number from the list
  (`sms_fetcher --list` → pick a different index) and update the creds file
- Numbers are shared — a previous message from the same sender means that
  number was used on that target before. Pick a different one.

## Before registering ANY account, in this order:
1. **You must have claimed your account first** — `$AGENT_BROWSER_ACCOUNT` must
   be set (see `reference/session-bootstrap.md`). Check: `echo $AGENT_BROWSER_ACCOUNT`.
2. Check `/home/aceos/Projects/hackbot/hunts/sessions/<domain>/$AGENT_BROWSER_ACCOUNT.creds` for
   an existing account. If found and not dead/banned, log in with those
   credentials instead of registering a new one.
3. If no creds file exists, ensure your profile exists (it should — `claim-account.sh`
   validates this, but check anyway):
   ```bash
   ABP=/home/aceos/Projects/hackbot-misc/.playwright-profiles
   [ -d "$ABP/Profile-$AGENT_BROWSER_ACCOUNT" ] || \
     (cd "$ABP" && ./clone-profile.sh "$AGENT_BROWSER_ACCOUNT")
   ```
4. Your Playwright MCP server is already pointed at your profile (set by
   `claim-account.sh` via `--user-data-dir`). Just navigate — no switch
   needed:
   ```
   Playwright MCP: browser_navigate("$TARGET/register")   # captcha solver already active
   ```
5. Immediately after successful registration — before doing anything else —
   write the credentials:
   ```bash
   # Derive the email suffix: userA → "a", userB → "b"
   SUFFIX=$(echo "$AGENT_BROWSER_ACCOUNT" | sed 's/user//')
   cat > /home/aceos/Projects/hackbot/hunts/sessions/${TARGET}/$AGENT_BROWSER_ACCOUNT.creds <<EOF
   email=aceproulx+${TARGET}-${SUFFIX}@intigriti.me
   password=${GENERATED_PASSWORD}
   created=$(date -u +%Y-%m-%dT%H:%M:%SZ)
   EOF
   chmod 600 /home/aceos/Projects/hackbot/hunts/sessions/${TARGET}/$AGENT_BROWSER_ACCOUNT.creds
   ```
   This is not an end-of-hunt cleanup step — do it immediately or a
   crash/pivot mid-hunt loses the account.
6. If the target sends a verification email, check the inbox using the
   `@email-inbox-check` skill's filtered list — never poll the raw endpoint.

## Workflow (profile-based; curl still the IDOR transport)
```bash
ABP=/home/aceos/Projects/hackbot-misc/.playwright-profiles
TARGET=https://example.com

# 0. Bootstrap — each agent runs this ONCE at session start.
#    Both agents run the exact same line; claim-account.sh assigns them
#    different slots (userA / userB) automatically and points each agent's
#    Playwright MCP server instance at the matching profile dir.
eval "$(cd "$ABP" && ./claim-account.sh)"
# → $AGENT_BROWSER_ACCOUNT is now set (e.g. "userA")
# → $AGENT_BROWSER_PROFILE is set, and your Playwright MCP server was
#   launched/attached with --user-data-dir=$AGENT_BROWSER_PROFILE

# 1. Ensure your Chrome profile exists (clone from Default if missing)
[ -d "$ABP/Profile-$AGENT_BROWSER_ACCOUNT" ] || \
  (cd "$ABP" && ./clone-profile.sh "$AGENT_BROWSER_ACCOUNT")

# 2. Register in your profile (Playwright MCP already uses the right
#    profile because it was launched with your --user-data-dir — no
#    switch needed)
Playwright MCP: browser_navigate("$TARGET/register")
# ... fill form (browser_type / browser_click / browser_fill_form),
# verify email, confirm login persisted in your profile dir

# 3. Keep extensions/config in sync whenever FoxyProxy or captcha-solver
#    config changes in the source profile:
(cd "$ABP" && ./sync-extensions.sh)

# 4. IDOR cross-check — each agent stays in its own browser process; curl
#    does the swap. Collect your own resource IDs via Playwright MCP, then
#    hit the other account's IDs via curl with your own cookies:
Playwright MCP: browser_navigate("$TARGET/profile")   # note your resource IDs
# Export cookies and replay as the other user via curl:
# curl -sk --proxy 127.0.0.1:8080 -b /tmp/my_cookies.txt \
#   "$TARGET/api/profile/<other-user-id>"
# If you get the other user's data → IDOR confirmed
```

## Workflow (curl-based token swap, captcha-less targets)
```bash
# 1. Register both users, grab tokens
UA=$(curl -sk -X POST "$TARGET/register" \
  -d "username=hunter_a_$(date +%s)&password=Pass123!" \
  -c - | grep token | awk '{print $NF}')

UB=$(curl -sk -X POST "$TARGET/register" \
  -d "username=hunter_b_$(date +%s)&password=Pass123!" \
  -c - | grep token | awk '{print $NF}')

# 2. Test IDOR — request userA's resource with userB's token
curl -sk "$TARGET/api/profile" -b "token=$UA"    # userA's own data
curl -sk "$TARGET/api/profile" -b "token=$UB"    # userB's own data

# 3. Swap: userA's endpoint ID with userB's token
curl -sk "$TARGET/api/profile/17" -b "token=$UB" # userB accessing userA's profile

# 4. If they match or userB sees userA's fields → IDOR confirmed
```

## UI Bypass via Caido Match & Replace
Use `create_tamper_rule` / `toggle_tamper_rule` to flip UI-gating flags in
transit:
- Premium bypass, role escalation, feature flags, paywalls, rate limits,
  disabled/hidden fields.
- Browse the feature via Playwright MCP, inspect the response for boolean
  flags, create a tamper rule, reload.
- If the unlocked UI reveals new endpoints, pivot into them.
