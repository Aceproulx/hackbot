# agent-browser account profiles

Each account runs in its own Chrome profile directory
(`Profile-<name>`), so every account keeps its own login session, cookies,
history, and storage — while sharing the same extensions (FoxyProxy + captcha
solver) and their configuration.

The `profile` field in `~/.agent-browser/config.json` points at the active
profile directory. `switch-account.sh` is what changes it for single-agent use.

## Layout

```
.agent-browser-profiles/
  Profile-Default/          # initial account (source of truth for extensions)
  clone-profile.sh          # create a new account profile
  switch-account.sh         # switch account (single agent, sequential use only)
  use-account.sh            # ← use this for concurrent agents (no shared file)
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
3. Launch agent-browser and log into the new account **once manually**. This is
   intentionally not automated.

## Switch between accounts (single agent, sequential)

```
./switch-account.sh <name>
```

- Fails loudly if `Profile-<name>` does not exist.
- Edits only the `profile` field in `~/.agent-browser/config.json` (via a real
  JSON parser — `headed` and `args` are untouched).
- Kills any running agent-browser/Chrome process whose `--user-data-dir`
  matches the *old* profile path (not all Chrome).
- Prints which account is now active. Launch agent-browser next to use it.
- **⚠ Do NOT call this when two agents run concurrently** — it mutates the
  shared `config.json` and causes a race condition. Use `use-account.sh` instead.

## Concurrent agents — two agents at once

Two env vars give each agent a fully isolated browser:

| Env var | What it isolates |
|---|---|
| `AGENT_BROWSER_PROFILE` | Chrome profile dir → separate cookies/login session |
| `AGENT_BROWSER_NAMESPACE` | Daemon socket → **separate Chrome window entirely** |

Without `AGENT_BROWSER_NAMESPACE`, both agents share the same daemon process
and the same Chrome window. When Agent B calls `agent-browser open <url>`, it
navigates Agent A's active tab — Agent A loses its page.

### `use-account.sh` — sets both vars at once

```bash
# Agent 1 shell — run once at session start
eval "$(./use-account.sh userA)"
# → AGENT_BROWSER_PROFILE = .../Profile-userA
# → AGENT_BROWSER_NAMESPACE = agent-userA
# Every subsequent `agent-browser` call in this shell is fully isolated.

# Agent 2 shell — completely independent Chrome window + profile
eval "$(./use-account.sh userB)"
# → AGENT_BROWSER_PROFILE = .../Profile-userB
# → AGENT_BROWSER_NAMESPACE = agent-userB
```

Or source it directly:
```bash
source ./use-account.sh userA   # bash/zsh
. ./use-account.sh userA        # POSIX sh
```

After this, each agent has:
- Its own Chrome window (daemon namespace)
- Its own cookies/session (profile)
- Its own extensions already installed (cloned from Profile-Default)
- No dependency on `config.json` — that file is left untouched

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