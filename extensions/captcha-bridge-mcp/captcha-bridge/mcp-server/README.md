# captcha-bridge MCP server

Run as a normal local MCP server. It does two things in one process:

1. Listens on `http://127.0.0.1:5055` for `POST /status` from the
   extension (state changes: `solving` / `solved` / `failed`, keyed by
   Chrome tab ID).
2. Exposes MCP tools over stdio for your agent:
   - `click_captcha(session?)` — queue a click for a tab's checkbox
     (the extension does NOT auto-click; this is the only trigger)
   - `get_captcha_status(session?)` — one-shot check
   - `wait_for_captcha(session?, timeoutSeconds?, pollIntervalMs?)` —
     polls until solved (and not expired) or failed; returns
     `remainingMs` so the agent can judge whether there's enough time
     left to finish a long form
   - `reset_captcha_session(session)` — call right after triggering a
     page reload (2-minute expiry) so stale state isn't read back

## Setup

```
cd mcp-server
npm install
```

Register it in your agent's MCP config the same way you did
intigriti-mcp, pointing the command at `node mcp-server/server.js`
(stdio transport). No separate process to babysit — your agent's MCP
client will spawn/manage it, and it starts the HTTP listener
internally on launch.

## Session IDs

The extension keys everything by Chrome tab ID (grabbed automatically
from `sender.tab.id` in the background script). If `agent-browser`
already knows the tab ID (e.g. via CDP `Target.getTargets`), pass the
same value as `session` to the tools. If you're only ever running one
CAPTCHA at a time, omit `session` everywhere — the server tracks the
most recently updated one automatically.
