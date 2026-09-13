# agent-browser account profiles

Each account runs in its own Chrome profile directory
(`Profile-<name>`), so every account keeps its own login session, cookies,
history, and storage — while sharing the same extension configuration.

The `profile` field in `~/.agent-browser/config.json` points at the active
profile directory. `switch-account.sh` is what changes it.

## What is in this directory

`Profile-Default/` is a **sanitized seed profile**: it contains the installed
extensions and their config, but is stripped of everything account-specific
(sessions, cookies, history, login data, caches, local storage). It is shipped
with the repo so a fresh install gets working extensions without a browser
session dump.

- **FoxyProxy** is fully self-contained: the extension code ships inside the
  profile (`Default/Extensions/...`) and its proxy rules/config ship in
  `Default/Local Extension Settings/...`, both registered via
  `Default/Preferences`. It is ready to use on install.
- **Captcha solver / buster** are *developer-mode unpacked extensions* loaded
  from their own source directories outside this profile (i.e. the
  `I-m-Not-A-Robot-Clicker` and `buster` projects). Their code is not in this
  repo; add them once manually per machine (`chrome://extensions` → Developer
  mode → *Load unpacked*) and they are picked up by every clone.

## Layout

```
.agent-browser-profiles/
  Profile-Default/          # initial account (source of truth for extensions)
  clone-profile.sh          # create a new account profile
  switch-account.sh         # switch which account agent-browser uses
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
2. Switch to it: `./switch-account.sh <name>`.
3. Launch agent-browser and log into the new account **once manually**. This is
   intentionally not automated.

## Switch between accounts

```
./switch-account.sh <name>
```

- Fails loudly if `Profile-<name>` does not exist.
- Edits only the `profile` field in `~/.agent-browser/config.json` (via a real
  JSON parser — `headed` and `args` are untouched).
- Kills any running agent-browser/Chrome process whose `--user-data-dir`
  matches the *old* profile path (not all Chrome).
- Prints which account is now active. Launch agent-browser next to use it.

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