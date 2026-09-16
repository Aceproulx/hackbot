# CAPTCHA solve-status bridge

Lets an AI agent know when the CAPTCHA extensions have actually finished,
instead of guessing or hardcoding a wait. Built for use within an
authorized bug bounty program's scope.

## How it fits together

    Extension (background.js)  --POST-->  captcha-bridge MCP server  <--MCP tools--  Agent (stdio)

The MCP server does double duty: it's a normal local MCP server your
agent talks to over stdio, and internally it also runs a small HTTP
listener on `127.0.0.1:5055` that only the extension talks to. One
process, no separate relay to babysit.

The agent drives the whole solve: `click_captcha` queues a click that
the extension picks up on its next poll (~500ms), clicks the real
reCAPTCHA checkbox, and reports back `solving` / `solved` / `failed`.

## Setup

1. **MCP server**
   ```
   cd mcp-server
   npm install
   ```
   Register it in your agent's MCP config (same pattern as
   intigriti-mcp) pointing at `node mcp-server/server.js`. Your
   agent's MCP client manages the process lifecycle; the HTTP
   listener comes up automatically when it starts.

2. **Extension** — load `extension/` as an unpacked extension
   (chrome://extensions → Developer mode → Load unpacked). This is the
   "Not-A-Robot Clicker" extension with two additions:
   - `content.js` reports state transitions (`solving` when the
     audio/image challenge iframe opens, `solved` when the checkbox
     becomes checked, `failed` if it becomes unchecked again after
     being checked).
   - `background.js` forwards those reports to the MCP server's HTTP
     listener via `POST /status`, keyed by the Chrome tab ID.
   - Keep Buster installed and enabled as before — it still does the
     actual audio-challenge solving. This bridge doesn't touch it;
     it just watches the same checkbox Buster's solve eventually checks.

3. **Agent** — call the MCP tools directly:
   - `click_captcha(session?)` — triggers the checkbox click (the
     extension never auto-clicks; this is the only way to start a solve)
   - `get_captcha_status(session?)`
   - `wait_for_captcha(session?, timeoutSeconds?, pollIntervalMs?)`
   - `reset_captcha_session(session)`

   See `mcp-server/README.md` for details and session-id notes.

## The 2-minute expiry

The server stamps `solvedAt` the moment it receives a `solved` report,
and computes `expiresAt = solvedAt + 120000ms` on every read — so the
agent never has to do its own clock math. Once expired, the state
flips to `"expired"` automatically on the next read.

Since expiry means "reload the page, refill the form," call
`reset_captcha_session` right after you trigger that reload so a stale
`"expired"`/`"solved"` entry isn't read back before the new solve
comes in.

## Known limitation

`failed` detection is a heuristic (checkbox goes from checked back to
unchecked). It won't catch every failure mode Buster/reCAPTCHA can hit
— for those, `wait_for_captcha`'s timeout will just kick in, which is
still a safe, actionable signal.
