---
name: csrf-blob-no-content-type
description: >
  Use this skill during authorized bug bounty / pentest recon whenever a target's CSRF defense relies on checking the request's Content-Type header (e.g. rejecting anything that isn't exactly "application/json", assuming a cross-site request can't have that header without a CORS preflight). Covers the "missing Content-Type" bypass: browsers' fetch() accepts a Blob (constructed with no explicit type) as the request body, which sends a genuine cross-site, non-preflighted POST whose Content-Type header is entirely absent — not "text/plain" or one of the three CORS-safelisted values, just missing — which slips past naive "Content-Type must equal application/json" checks that only special-case the safelisted types and don't reject a missing header. Trigger on requests to test CSRF protections, review a server's request.content_type check, or "can this JSON endpoint be CSRF'd" — always only against in-scope targets.
metadata:
  source: https://nastystereo.com/security/cross-site-post-without-content-type.html
---

# CSRF via Blob POST With No Content-Type Header

From Luke Jahnke (nastystereo.com). Targets a specific, easy-to-miss gap in "reject non-JSON Content-Type" CSRF defenses.

## The defense being bypassed

Some apps try to block CSRF by rejecting any POST whose `Content-Type` isn't `application/json`, reasoning that a browser can only send the three CORS-safelisted content types (`application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain`) cross-site without a preflight, and none of those is `application/json` — so a same-origin-only header check should be safe. Example vulnerable pattern (Sinatra, but the same logic appears in Rails/Express/etc.):
```ruby
post "/transfer-funds" do
  if request.content_type && request.content_type != "application/json"
    halt 403, "CSRF detected"
  end
  transaction = JSON.parse(request.body.read)
  # ...
end
```
The bug: this only rejects when `content_type` is **present and wrong**. It doesn't handle **absent**.

## The bypass

`fetch()`'s `body` parameter accepts a `Blob`, and a `Blob` constructed with no explicit MIME type produces a cross-site POST with **no `Content-Type` header at all** — not `text/plain`, actually absent — while still being CORS-safelisted (so no preflight, no CORS permission needed from the target):
```js
fetch("https://victim.com/transfer-funds", {
  method: "POST",
  body: new Blob(["payload"])   // no type argument → no Content-Type header
});
```
This isn't limited to an empty body — whatever you pass to `Blob(...)` becomes the raw HTTP request body, so you can send arbitrary raw JSON text (or anything else) with a `Content-Length` but no `Content-Type`. Against the pattern above, `request.content_type` is `nil`, the `if` short-circuits, and `JSON.parse(request.body.read)` happily parses your attacker-supplied body as if it were a legitimate JSON request.

## How to test

1. **Identify the defense shape.** Find a state-changing JSON endpoint and check whether the server's CSRF protection is (or looks like) a Content-Type allow/deny check rather than a token-based defense (CSRF token, `SameSite` cookie, custom-header requirement that can't be set cross-site). A same-site `application/json`-only request that fails when you switch `Content-Type` to `text/plain` — but you haven't yet tried *removing* it — is the tell.
2. **Confirm the endpoint accepts a body with no Content-Type.** From an attacker-controlled page (or `fetch` in devtools against the target origin while authenticated, to approximate a cross-site request), send:
   ```js
   fetch("https://target.example/api/endpoint", {
     method: "POST",
     credentials: "include", // only relevant same-site; irrelevant for the actual cross-site PoC, cookies ride along automatically
     body: new Blob([JSON.stringify({ /* your JSON payload */ })])
   });
   ```
   from a page hosted on a **different origin** than the target, while logged into the target in the same browser. Confirm via the Network tab that the outgoing request has no `Content-Type` header and that the server processed it (200/302, state actually changed) rather than returning the app's CSRF-rejection response.
3. **Build the PoC page.** A minimal attacker HTML page with the `fetch` call (no user interaction needed beyond visiting the page, if the target uses ambient cookie auth) is enough for the report. Confirm impact against your own test account/session only.

## Reporting checklist

- The vulnerable Content-Type check (source if whitebox, or the observed behavior difference if blackbox: request rejected with wrong Content-Type, accepted with none).
- The PoC HTML/JS and a captured raw request showing the missing `Content-Type` header.
- Recommend fixing forward: don't rely on Content-Type sniffing for CSRF defense at all — use a synchronizer token, `SameSite=Lax/Strict` cookies, or a custom header (e.g. `X-Requested-With`) that genuinely cannot be set on a no-CORS cross-site request.
- Note this is distinct from the older 307-redirect/Flash (CVE-2011-0059/CVE-2011-0447) and `navigator.sendBeacon` (Chromium #490015) bypasses of the same defense class — those vectors are patched/removed; this `Blob` vector is the current one to check for.
