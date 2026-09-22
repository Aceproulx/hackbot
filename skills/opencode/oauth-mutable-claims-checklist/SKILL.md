---
name: oauth-mutable-claims-checklist
description: >
  Use this skill during authorized bug bounty / pentest recon whenever a target has "Login with Microsoft/Google/etc." (OAuth/OIDC social login), and as a general checklist for testing any OAuth2/OIDC Client application. Covers the "nOAuth" bug class: apps that identify users by a mutable, attacker-settable claim like "email" instead of the immutable "sub", combined with an IdP (classically Azure AD multi-tenant apps) that lets an attacker freely set their own account's email to a victim's real email with no verification, then "Log in" as the victim and take over or merge into their existing account. Also covers the broader OAuth checklist: missing/weak "state" (OAuth CSRF), missing or loosely-matched redirect_uri validation, client confusion / access-token substitution, scope-upgrade at token exchange, and mobile custom-URL-scheme redirect hijacking. Trigger on requests to audit an OAuth Client integration, test account-merging logic, check redirect_uri validation, or "is this OAuth login secure" — always only against in-scope targets and your own test accounts.
metadata:
  source: https://www.descope.com/blog/post/noauth
  related_source: https://blog.doyensec.com/2025/01/30/oauth-common-vulnerabilities.html
---

# OAuth Mutable-Claims (nOAuth) and General Vulnerability Checklist

Two combined sources: Descope's nOAuth disclosure (Omer Cohen, 2023) and Doyensec's comprehensive OAuth vulnerability writeup (Jose Catalan, Szymon Drosdzol, 2025). Use the first section as a focused, high-value test; use the checklist for a fuller audit.

## nOAuth: mutable email claim → account takeover

**The root flaw:** per spec, the `sub` (subject) claim is the only claim guaranteed unique and immutable per user. Many client apps instead identify/merge users by the `email` claim because it's more convenient and human-readable. This is only safe if the IdP guarantees `email` is verified and immutable. **Azure AD (multi-tenant apps) does not** — a user can freely edit their own "Email" contact attribute with zero verification, and that value flows straight into the `email` claim of the JWT the client app receives.

**Attack:**
1. Attacker creates their own Azure AD tenant (free, self-service) and an admin account in it.
2. Attacker edits that account's "Email" contact attribute to the victim's real email address (e.g. `victim@realcompany.com`) — Azure AD does not verify this.
3. Attacker clicks "Log in with Microsoft" on the target app. The returned JWT has `sub`/`oid` belonging to the attacker's own tenant/account, but `email` (and often `preferred_username`) equal to the victim's address.
4. **Impact depends on how the target handles it:**
   - If the app uses `email` as the unique identifier outright → instant account takeover, no victim interaction needed.
   - If the app "helpfully" merges a new OAuth login with an existing account that shares the same email → the attacker's OAuth identity gets merged into/granted control of the victim's existing (e.g. password-based) account.

**How to test (on your own org / test target only):**
- Create a throwaway Azure AD tenant, set its test-user email to an address you control (a second one of your own accounts on the target), and run "Log in with Microsoft" against the target with that email set to your second account's address.
- Decode the returned id_token/access_token (JWT) and check which claim(s) the app's backend actually keys off — if you have any visibility (error messages, API responses, support docs) into how login/merge logic works, use it.
- If merging is confirmed and keyed on `email`, that's the reportable nOAuth condition — you do not need to actually complete a takeover against a real account to prove it; showing the unverified merge is enough for a report.
- Check whether the app/IdP integration already opts into Microsoft's mitigations: the `xms_edov` claim (indicates domain-verified email) and `RemoveUnverifiedEmailClaim` behavior — their absence is itself worth noting in the report.

**Not Azure-specific:** the same class of bug applies to any IdP that (a) exposes a mutable/user-editable claim and (b) lets a client rely on it for identity — always check what a given IdP actually guarantees before assuming `email`/`preferred_username` is safe.

## Broader OAuth vulnerability checklist (Doyensec)

Work through each of these against the target's Client-side implementation:

1. **CSRF via missing/predictable `state`.** The OAuth spec's `state` parameter exists specifically to bind the authorization request to the browser that started it. If it's absent, static, or not actually validated on return, an attacker can complete their own OAuth flow, capture the resulting callback URL (with their own valid code), and get the victim to load it — binding the *victim's* session to the *attacker's* linked account. Test: start the flow, strip/replace `state`, see if the callback still succeeds.

2. **`redirect_uri` validation weaknesses.** The only safe validation is an **exact match** of scheme+host+port+path against a per-client allowlist. Look for apps that only check origin/domain (allowing arbitrary paths), allow subdomains, allow subpaths, or use a loose/misused regex. If a permitted redirect target itself has an open redirect or hosts user-controlled content, the authorization code can be leaked via the `Referer` header or the open redirect itself once the flow lands there — chain this with the non-happy-path Referer techniques from OAuth callback-fallback research.

3. **Client confusion / access-token substitution.** For apps using the (deprecated but still-seen) Implicit Flow for *authentication*, check whether the app actually validates that a returned token was issued **for its own client_id**. If not: host your own public page that also does "Login with Google" via Implicit Flow (harvesting real users' tokens issued for *your* client_id), then replay one of those captured tokens against the vulnerable target — if the target only checks token validity and not audience/client_id, this logs the attacker in as that other user.

4. **Scope-upgrade at the token exchange.** In the Authorization Code flow, the `scope` parameter has no defined role in the Access Token Request (per RFC 6749 §4.1.3) — if the authorization server nonetheless trusts a `scope` value supplied at that step instead of re-using/validating against the original authorization request's scope, a malicious/compromised client could request a broader scope than the user actually consented to.

5. **Mobile custom-URL-scheme redirect hijacking.** When `redirect_uri` is a custom scheme (`com.example.app://oauth`) rather than an HTTPS Universal/App Link, any other app that registers an Intent Filter (Android) for the same scheme can potentially intercept the authorization code. Check how loosely the legitimate app's Intent Filter is defined (scheme-only filters catch everything for that scheme) — the more specific the legitimate filter, paradoxically, the easier it is to craft a competing filter that wins. The correct fix is PKCE plus Android App Links (`autoVerify` + `assetlinks.json`) or iOS Associated Domains, not a bare custom scheme.

## Reporting checklist

- For nOAuth: the JWT diff showing identical claims except `email`, and (if possible without touching a real victim) proof the app either identifies by `email` directly or silently merges accounts on it.
- For each checklist item: which validation is missing (exact match vs. origin-only, `state` presence/validation, token audience check, scope re-validation, Intent Filter specificity) and a minimal PoC request/response demonstrating the gap.
- Doyensec publishes a companion OAuth Security Cheat Sheet PDF — useful as a testing checklist template when writing up findings.
