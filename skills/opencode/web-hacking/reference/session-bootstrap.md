# Session Persistence — Load at session start, or before any Playwright MCP call

## Concurrent agents — REQUIRED bootstrap (do this FIRST, before any Playwright MCP call)

Two agents sharing one Playwright MCP server/browser instance will stomp
each other's tabs and cookies: if both agents call `browser_navigate` (or
any other Playwright MCP tool) against the same server connection, they're
driving the same browser context — one agent's navigation or login moves
the other agent's session too. Fix: each agent must run its **own Playwright
MCP server process**, launched with its **own `--user-data-dir`** pointing at
that account's Chrome profile. That gives each agent an independent browser
process, independent cookies/localStorage, and an independent MCP
connection — the direct equivalent of the old daemon-socket isolation.

| Isolation need | How it maps onto Playwright MCP |
|---|---|
| Which account slot you own (`userA` / `userB`) | `$AGENT_BROWSER_ACCOUNT` — unchanged, still your identity var |
| Separate cookies / login session | `--user-data-dir <profile-dir>` passed at Playwright MCP server launch |
| Separate browser process entirely | A separate Playwright MCP server instance/connection per agent (not a shared one with `--session` flags — Playwright MCP has no per-call session flag; isolation is at the server-process level) |

### Self-discovery — you don't know which agent you are ahead of time

Both agents load the same skill. Neither knows if it is "agent 1" or "agent 2".
Run `claim-account.sh` at startup — it atomically races to claim the first free
slot, tells you who you are, and now also **launches (or attaches to) your own
Playwright MCP server instance pointed at that slot's profile dir**:

```bash
ABP={{HACKBOT_MISC_DIR}}/.playwright-profiles

# Run this ONCE at the very start of the agent session:
eval "$(cd "$ABP" && ./claim-account.sh)"

# claim-account.sh outputs three export lines, e.g.:
#   export AGENT_BROWSER_ACCOUNT="userA"
#   export AGENT_BROWSER_PROFILE=".../.playwright-profiles/Profile-userA"
#   export PLAYWRIGHT_MCP_USER_DATA_DIR="$AGENT_BROWSER_PROFILE"
#
# The other agent racing concurrently will get userB automatically, with its
# own Playwright MCP server instance pointed at Profile-userB.
# After this, every Playwright MCP tool call in this agent's connection is
# fully isolated to this account's profile.
```

> **If `claim-account.sh` cannot launch/attach your Playwright MCP server**
> (no MCP tools in your toolset, connection closed), the env vars it exports
> (`AGENT_BROWSER_PROFILE`, `PLAYWRIGHT_MCP_USER_DATA_DIR`) still point at
> your profile — use the fallback helper with those vars (see
> `reference/playwright-fallback.md`):
> `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js navigate <url>`
> (profile is picked up automatically from the env vars).

Check your identity any time:
```bash
echo "I am: $AGENT_BROWSER_ACCOUNT"
echo "My creds: {{SESSIONS_DIR}}/<target>/$AGENT_BROWSER_ACCOUNT.creds"
```

### Release on clean exit
```bash
cd {{HACKBOT_MISC_DIR}}/.playwright-profiles && ./release-account.sh
# frees the slot for the next agent and signals your Playwright MCP server
# instance to shut down
```
A missed release is not fatal — stale locks from crashed agents are
auto-detected and cleared on the next `claim-account.sh` run.

### How the lock works
`claim-account.sh` uses `mkdir(2)` atomicity (POSIX-guaranteed) as a lock
primitive. It records the calling shell's PID (`$PPID`) in the lock dir. On
the next claim, if that PID is dead, the lock is reclaimed automatically.
No shared files are written — only the per-agent Playwright MCP launch config
is touched, never a shared `config.json`.

## Single-agent / sequential use
If only one agent is running, `switch-account.sh <name>` still works — it
points your single Playwright MCP server instance at a different
`--user-data-dir` and restarts the browser process on the old profile.
**Do not call it when two agents run concurrently** (race condition on a
shared browser process).

## Profile layout
One Chrome profile per account under
`{{HACKBOT_MISC_DIR}}/.playwright-profiles/Profile-<name>`. The profile
IS the session — cookies/localStorage persist inside it, and it's what you
pass as Playwright MCP's `--user-data-dir`. Every profile is cloned from
`Profile-Default`, so extensions + config (FoxyProxy, captcha solver) are
identical everywhere.

- **Reuse existing**: if `Profile-userA` exists and the account isn't dead,
  `claim-account.sh` will claim it and point your Playwright MCP instance at
  the existing cookies — no re-login needed.
- **Create if missing**: `./clone-profile.sh userA`, then run `claim-account.sh`,
  then log in once via Playwright MCP.
- **Two sessions, always**: userA and userB. If only userA's profile exists,
  `clone-profile.sh userB` and register it.
- **Re-auth**: if a session expires, log back in from that account's profile —
  the profile dir persists the new login automatically.
- **Sync extensions**: after changing FoxyProxy rules or captcha-solver config
  in the source profile, run `sync-extensions.sh` so the change reaches every
  account profile.
- **Creds**: durable login credentials live in
  `{{SESSIONS_DIR}}/<domain>/$AGENT_BROWSER_ACCOUNT.creds`.
  The auth state itself lives in the Chrome profile, not a state JSON.

## Browser Session — Keep Open

The browser is a headed Chromium session driven via Playwright MCP and
managed by the user. Never close it — just navigate for a fresh page.
⚠ idleTimeout is removed from config. The browser stays open forever. Do NOT
add a timeout back.
- Each Playwright MCP server instance auto-saves cookies/localStorage into
  the `--user-data-dir` profile it was launched with.
- Window crashed but the Playwright MCP server process lives → call
  `browser_navigate(<url>)` again to reconnect to a fresh tab.
- Server process dead too → relaunch the Playwright MCP server with the same
  `--user-data-dir`; the session persists in the active profile dir, then
  `browser_navigate(<url>)`.
- **Switch account** (concurrent agents) = set env vars and point your
  Playwright MCP server at a different profile via `use-account.sh`:
  ```bash
  eval "$(cd {{HACKBOT_MISC_DIR}}/.playwright-profiles && ./use-account.sh userB)"
  ```
  This sets `AGENT_BROWSER_PROFILE` and relaunches your own Playwright MCP
  server instance with `--user-data-dir` pointed at it. The old account's
  login stays in its profile dir — nothing to save or load. This does not
  touch any other agent's Playwright MCP server.
- **Switch account** (sequential, single agent only) = `switch-account.sh <name>`
  (in `{{HACKBOT_MISC_DIR}}/.playwright-profiles/`); re-points your
  single Playwright MCP server's `--user-data-dir` and restarts the browser
  process on the old profile only. Do not use when two agents are live.
