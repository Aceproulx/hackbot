# Captcha Solving — captcha-bridge MCP

Load this only when a CAPTCHA actually appears on screen. Don't preload it
for every registration — most flows won't hit one every time.

The captcha-bridge MCP controls the reCAPTCHA-solver extension already loaded
in every Chrome profile. **The extension does NOT auto-click** — you must
trigger it via MCP every time a CAPTCHA appears.

> **2-minute window:** A solved token is valid for exactly 120 seconds.
> After that the token expires and any form submit will silently fail or
> return an error. Always submit the form immediately after `wait_for_captcha`
> returns `solved` — never fill the form first and solve later.

---

## The 4 MCP calls — exact syntax + what comes back

### 1. `captcha-bridge: click_captcha`
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

### 2. `captcha-bridge: wait_for_captcha`
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

### 3. `captcha-bridge: get_captcha_status`
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

### 4. `captcha-bridge: reset_captcha_session`
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

## Complete worked example — registering userA

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

Step 5: Write creds immediately (see reference/accounts-registration.md)
  cat > {{SESSIONS_DIR}}/target/userA.creds << EOF
  email={{EMAIL_BASE}}+target-a@{{EMAIL_DOMAIN}}
  password=P@ss9z!mX2
  created=2026-09-13T18:31:00Z
  EOF
```

---

## Expiry recovery — full sequence

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

## Multi-user parallel registration (userA + userB)

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

## Captcha bypass testing (separate concern)

`@hunt-captcha-bypass` (see the class table in core `SKILL.md`) =
**attacking** captcha implementations (replaying tokens, sharing across
users, entropy weaknesses, missing server-side validation). Completely
separate from solving.
- For bypass testing: use Caido automate / `batch_send` to replay tokens
- Never use captcha-bridge tools for bypass testing
