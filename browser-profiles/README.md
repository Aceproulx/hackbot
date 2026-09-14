# Browser account profiles

Each account runs in its own Chrome profile directory
(`Profile-<name>`), so every account keeps its own login session, cookies,
history, and storage — while sharing the same extensions (FoxyProxy + captcha
solver) and their configuration.

The profile directory is passed to Playwright MCP as `--user-data-dir`, which
is how the browser process gets its cookies/login session.

## Layout

```
.agent-browser-profiles/
  Profile-Default/          # initial account (source of truth for extensions)
  clone-profile.sh          # create a new account profile
  switch-account.sh         # switch account (single agent, sequential use only)
  use-account.sh            # ← use this for concurrent agents (no shared file)
  claim-account.sh          # ← atomic race for concurrent agents (self-discovery)
  release-account.sh        # release a claimed profile slot
  sync-extensions.sh        # propagate extension/config changes to all accounts
  README.md
```

## Add a new account

```
./clone-profile.sh <name>
```

1. Clones `Profile-Default` (or pass a second arg for a different source:
   `./clone-profile.sh <name> <source-profile-name>`) into `Profile-<name>`,
   including the installed extensions.
2. Switch to it: `./switch-account.sh <name>` (or `use-account.sh` for
   concurrent use, see below).
3. Launch your Playwright MCP server pointed at the profile and log into the
   new account **once manually**. This is intentionally not automated.

## Switch between accounts (single agent, sequential)

```
./switch-account.sh <name>
```

- Fails loudly if `Profile-<name>` does not exist.
- Edits only the `profile` field in `~/.agent-browser/config.json` (legacy —
  kept for agent-browser compatibility) via a real JSON parser.
- Kills any running Chrome process whose `--user-data-dir`
  matches the *old* profile path (not all Chrome).
- Prints which account is now active.
- **⚠ Do NOT call this when two agents run concurrently** — it mutates the
  shared `config.json` and causes a race condition. Use `use-account.sh` instead.

## Concurrent agents — two agents at once

Each agent gets a fully isolated browser by running its **own Playwright MCP
server process** pointed at its **own profile dir**:

| Env var | What it isolates |
|---|---|
| `AGENT_BROWSER_ACCOUNT` | Which slot you own (`userA` / `userB`) — your identity var |
| `AGENT_BROWSER_PROFILE` | Chrome profile dir → separate cookies/login session |
| `PLAYWRIGHT_MCP_USER_DATA_DIR` | The profile dir — feed into Playwright MCP's `--user-data-dir` flag |

Without a per-agent Playwright MCP server process (each with its own
`--user-data-dir`), both agents drive the same browser context — one agent's
`browser_navigate` (or login) moves the other agent's session.

### `use-account.sh` — sets the vars for a named slot

```bash
# Agent 1 shell — run once at session start
eval "$(./use-account.sh userA)"
# → AGENT_BROWSER_PROFILE = .../Profile-userA
# → PLAYWRIGHT_MCP_USER_DATA_DIR = .../Profile-userA
# Launch your own Playwright MCP server instance with --user-data-dir from this.

# Agent 2 shell — completely independent browser context + profile
eval "$(./use-account.sh userB)"
```

Or source it directly (bash/zsh only — POSIX sh's `.` drops the arg, so
use the `eval` form there):
```bash
source ./use-account.sh userA   # bash/zsh
```

### `claim-account.sh` — self-discovery when you don't know your slot

Both agents load the same skill and neither knows if it is "agent 1" or
"agent 2". Run once at the very start of the session:

```bash
eval "$( ./claim-account.sh )"   # note: it must NOT be sourced
```

It atomically races (via `mkdir(2)` lock) to claim the first free slot, prints
`AGENT_BROWSER_ACCOUNT`, `AGENT_BROWSER_PROFILE`, and
`PLAYWRIGHT_MCP_USER_DATA_DIR`, and signals your Playwright MCP connection to
use that profile. The other agent gets `userB` automatically.

Release the slot on clean exit:
```bash
./release-account.sh          # uses $AGENT_BROWSER_ACCOUNT
./release-account.sh userA    # explicit
```
A missed release is not fatal — stale locks from crashed agents are
auto-detected and cleared on the next `claim-account.sh` run.

After bootstrap each agent has:
- Its own Chrome process / browser context (own Playwright MCP server instance)
- Its own cookies/session (profile dir)
- Its own extensions already installed (cloned from Profile-Default)

## Propagate extension / config changes

```
./sync-extensions.sh                # sync from Profile-Default
./sync-extensions.sh <source-name>  # sync from another profile
```

Copies `Default/Extensions` and `Default/Local Extension Settings` (where the
FoxyProxy rules and captcha solver config live) from the source profile onto
every other account profile. Run this whenever those change, so all accounts
stay in sync without redoing manual extension setup.

Note: extension *settings* are synced wholesale; account-specific data
(cookies, logins, history) is intentionally never touched.

## How this maps to the web-hacking skill

The `web-hacking` skill's "Concurrent agents — REQUIRED bootstrap" section
walks through this exact flow: run `claim-account.sh` first, then every
Playwright MCP tool call in your connection is isolated to that account's
profile. See that skill for the full walkthrough.