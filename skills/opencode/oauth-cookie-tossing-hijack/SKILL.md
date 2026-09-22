---
name: oauth-cookie-tossing-hijack
description: >
  Use this skill during authorized bug bounty / pentest recon whenever a target hosts user-controlled or per-customer subdomains (a CDE/workspace platform, a "yourname.target.com"-style multi-tenant product, or anywhere you have or can get JavaScript execution on any subdomain via XSS or by design) AND the same parent domain runs multi-step state-changing flows — especially an OAuth "connect your account" flow — using cookies that lack the __Host- prefix. Covers "Cookie Tossing": a subdomain can set a cookie scoped to the parent domain (Domain=.target.com) with an attacker-chosen Path, which browsers will send on the victim's behalf to matching requests on other subdomains/paths, silently overriding the victim's own same-named cookie for those requests — this can hijack a multi-step OAuth linking flow so the victim ends up connecting their third-party account to the attacker's session instead of their own. Trigger on requests to test subdomain isolation, cookie scoping, or OAuth "connect account" flows on multi-tenant/subdomain-heavy platforms.
metadata:
  source: https://labs.snyk.io/resources/hijacking-oauth-flows-via-cookie-tossing/
---

# Cookie Tossing → OAuth Flow Hijack

From Elliot Ward, Snyk Security Labs (building on Thomas Houhou's cookie-tossing research). Targets platforms that let users/customers execute JavaScript on a subdomain (by design — a CDE, a workspace, a customer portal subdomain — or via an XSS bug on any subdomain) combined with a parent-domain OAuth "connect your account" flow that doesn't use `__Host-` prefixed cookies.

## Background: how cookie tossing works

Browser cookie scoping has two independent axes that don't require a matching origin the way most web security controls do:
- **Domain**: a cookie set by `sub.target.com` with `Domain=.target.com` becomes valid for `target.com` and *every* subdomain, not just the one that set it. A subdomain **cannot** set a cookie scoped to a sibling subdomain directly, but it *can* set one scoped to the shared parent, which every subdomain (including siblings) will then send.
- **Path**: cookies are also scoped by path, and **more specific paths are sent before less specific ones** when multiple same-named cookies could match a request. This lets an attacker "override" a victim's real cookie for one specific endpoint (e.g. `Path=/api/authorize`) while leaving the rest of the victim's session looking completely normal.

Critically: **`SameSite` provides no protection here.** Cookie tossing is launched from a subdomain of the same registrable domain, which satisfies `SameSite=Lax`/`Strict` by definition — this isn't a cross-site request in the `SameSite` sense at all.

## Step 1: Confirm you have (or can get) JS execution on a subdomain

Either:
- The product **by design** gives customers a subdomain that runs their own code (CDE/workspace platforms, customer-branded portals, anything where `customer123.target.com` serves customer-supplied content), or
- You have an XSS finding on any subdomain of the target's parent domain (even a low-severity "self-XSS" — cookie tossing is a well-known way to escalate a self-XSS into cross-user impact, which is worth calling out explicitly in your report).

## Step 2: Identify a state-changing flow on the parent domain worth hijacking

Look for multi-step flows on the parent domain (or another subdomain) that rely on a session/identity cookie across more than one request — OAuth "connect third-party account" flows are the prime target because the final step (the OAuth callback) trusts whatever session cookie is present at that moment, and the whole point of the flow is to *link* something to "whichever account is currently authenticated." Also worth checking: any sensitive state-changing endpoint (add payment method, change email, invite a user) reachable via a JSON API that relies solely on cookies with no separate CSRF token — cookie tossing bypasses `SameSite` but a real anti-CSRF token you don't possess still blocks you, since the victim's cookie carries their real token but your tossed cookie won't match it.

## Step 3: Toss the cookie

From your subdomain (or XSS context), set the parent-domain session cookie to your own (attacker) session value, scoped narrowly to the endpoint(s) the target flow hits:
```
document.cookie = "session=<attacker_session_value>; domain=.target.com; path=/api/authorize; secure";
```
Set one tossed cookie per distinct path the multi-step flow touches (e.g. both the initial `/api/authorize` and the eventual `/auth/<provider>/callback`), matching exactly what you observed the real flow use when you walked it once yourself.

## Step 4: Get the victim to trigger the flow

Send the victim a link to the subdomain that runs your tossing script (e.g. a link into a workspace/CDE instance you control). Visiting it is enough — nothing looks abnormal, the victim's normal session continues to work for everything except the specific path(s) you tossed a cookie for. When the victim next performs the targeted action (e.g. clicks "Connect GitHub account" in their normal, legitimate session), the requests hitting your tossed paths carry *your* session cookie instead of theirs — so the OAuth provider's authorization callback completes against **your** account, linking the victim's third-party account (their real GitHub/Bitbucket repos, etc.) to the **attacker's** session on the target platform.

## Step 5: Confirm impact

After the victim completes the flow, check (from the attacker account) whether you now have access to whatever the flow granted — repo access, data source access, payment method, etc. Only do this end-to-end with your own two test accounts.

## Reporting checklist

- Confirm which cookies on the target lack the `__Host-` prefix (check DevTools → Application → Cookies, or the raw `Set-Cookie` header — no `Domain` attribute at all combined with `Secure` and root `Path=/` is what `__Host-` requires; its presence would have blocked this entirely).
- Show the full sequence diagram: subdomain JS sets scoped cookies → victim performs the normal-looking flow → attacker account receives the linked resource.
- Note whether the endpoints involved have CSRF tokens (if they do and you still worked, explain why — likely a JSON endpoint relying on CORS/SOP instead of a token, which cookie tossing doesn't need to bypass since it's not a cross-origin request).
- Recommended fix: adopt the `__Host-` cookie prefix for all session/auth cookies (it forbids the `Domain` attribute being set and pins `Path=/`, which structurally prevents a subdomain from tossing a cookie either onto the parent or onto a narrower path).
