---
name: rails-json-param-juggling
description: >
  Use this skill during authorized bug bounty / pentest recon whenever a target API is built on Ruby on Rails and accepts JSON request bodies, especially endpoints that can plausibly operate on either a single item (JSON object, e.g. {"id":123}) or multiple items (JSON array, e.g. [456,789]). Covers the "_json juggling attack": Rails wraps any top-level JSON body that isn't a Hash (arrays, strings, numbers) into an object with a literal "_json" key holding that value, before exposing it via params, so an attacker can submit a body that is simultaneously a valid object AND smuggles a conflicting array under the literal key "_json" (e.g. {"id":123,"_json":[456,789]}), causing an authorization-check code path and the action-execution code path to disagree about which form of the input they're looking at, which can bypass authorization. Trigger on requests to test Rails/ActionController JSON endpoints for authorization bypass, mass assignment, or "parameter pollution"/"param confusion" style bugs.
metadata:
  source: https://nastystereo.com/security/rails-_json-juggling-attack.html
---

# Rails `_json` Parameter Juggling Attack

From Luke Jahnke (nastystereo.com). Exploits a Rails-specific quirk in how `ActionController::Parameters` normalizes non-Hash JSON bodies, to smuggle two conflicting interpretations of the same request into one call.

## The root cause

Rails' JSON body parser (`actionpack/lib/action_dispatch/http/parameters.rb`) does:
```ruby
data = ActiveSupport::JSON.decode(raw_post)
data.is_a?(Hash) ? data : { _json: data }
```
`params` must always behave Hash-like, so a top-level JSON array/string/number gets wrapped as `{ _json: <the array/string/number> }`. Nothing stops you from *also* supplying a literal `"_json"` key in a genuine JSON object body — and because Rails params are a `HashWithIndifferentAccess`, the string key `"_json"` and the symbol `:_json` collide. So this body:
```json
{ "id": 123, "_json": [456, 789] }
```
is simultaneously: a normal Hash with `params[:id] == 123`, **and** carries `params[:_json] == [456, 789]` — the exact same shape Rails would have produced natively from a bare `[456, 789]` array body.

## Where the bug bites

Look for an endpoint that has (or plausibly has) two code paths reading the same request differently — commonly a single-item vs. bulk/multi-item operation on one route (e.g. a delete/update endpoint that supports both `{"id": 123}` and `[456, 789]` bodies). The vulnerability appears when:
- the **authorization check** reads the request one way (e.g. checks `params[:id]` — the single item — and confirms the caller owns that item), while
- the **action execution** reads it the other way (e.g. checks `params[:_json]` — the bulk array — and operates on every ID in it, because that's the "native" shape for bulk requests),

...or vice versa. Send both forms at once and the two code paths disagree about which items are actually being touched — you may be able to authorize against one item you own while the execution path acts on an array of items you don't own.

## How to test

1. **Fingerprint Rails.** JSON param handling like this, `HashWithIndifferentAccess`, `X-Runtime` response headers, or routes matching `/users/:user_id`-style path segments are good signals. Rack-specific unparseable query strings (`x[y]=1&x[y]z=2`, `x[y]=1&x[y][][w]=2`) 400ing distinctively can help fingerprint Rack/Rails blackbox.
2. **Find candidate endpoints.** Anything that conceptually operates on "an item" or "a list of items" via the same route/method is worth probing — bulk delete, bulk update, batch invite, multi-select actions.
3. **Probe param precedence and shape.** If you have any way to introspect what the server sees (a debug/echo endpoint, verbose error messages, timing/behavioral differences), send:
   ```
   POST /items
   Content-Type: application/json

   {"id": <your_own_item_id>, "_json": [<victim_item_id_1>, <victim_item_id_2>]}
   ```
   and see whether the action taken affects the victim IDs despite `id` (the "authorized" one) being yours.
4. **Also check precedence across path / query / body.** Rails' precedence order is **path > query string > body** — a route param and a body param with the same name don't collide the way `_json` does, but juggling across these three sources is a related class of bug worth checking alongside this one (e.g. does the authz check read the path segment while the action reads the body, or vice versa).
5. **Local repro environment.** To develop/confirm payload shapes safely before touching the real target, spin up a minimal Rails app that echoes back what it parsed (see the Dockerfile in the reference write-up — a single `DumpController#index` action rendering `params.inspect`), and diff how your candidate payloads land.

## Reporting checklist

- The two code paths you believe disagree (authz vs. execution, or path/query/body precedence) and why.
- A request/response pair showing the authorization check passing against an item you own while the action affects items you don't.
- Note whether this is a first-party finding or "just" a robustness bug (i.e. does the app actually have two divergent code paths, or did your payload just get ignored) — the bug only matters if you can show real impact (unauthorized read/write/delete of another user's data).
