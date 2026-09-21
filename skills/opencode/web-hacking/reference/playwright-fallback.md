# Playwright MCP UNAVAILABLE — FALLBACK

Load this only when the trigger condition below is actually true — not
preemptively.

**Trigger condition — if ANY of these is true, use the fallback:**
- The Playwright MCP tools are NOT in your toolset: `browser_navigate`,
  `browser_snapshot`, `browser_click`, `browser_type`, `browser_fill_form`,
  `browser_select_option`, `browser_evaluate`, `browser_console_messages`,
  `browser_network_requests`, `browser_take_screenshot`, `browser_tabs`,
  `browser_press_key`, `browser_hover`, `browser_wait_for`, `browser_find`.
- The MCP connection is closed / erroring (`-32000 Connection closed`, tool
  calls fail, tools vanished mid-session).

**Do NOT skip browser verification when this happens.** Drive the browser
directly with the fallback helper:

```
node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js <command> [args] [--profile <dir>]
```

## Command mapping — MCP tool → fallback command

| MCP tool | Fallback command |
|---|---|
| `browser_navigate(url)` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js navigate <url>` |
| `browser_snapshot()` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js snapshot` |
| `browser_find(text)` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js find <text-or-/regex/>` |
| `browser_click(ref)` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js click <ref>` |
| `browser_type(ref, text)` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js type <ref> <text>` |
| `browser_press_key(key)` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js press <key>` |
| `browser_hover(ref)` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js hover <ref>` |
| `browser_evaluate(fn)` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js evaluate "() => ..."` |
| `browser_console_messages()` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js console` |
| `browser_network_requests()` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js network` |
| `browser_take_screenshot(path)` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js screenshot <path>` |
| `browser_wait_for(secs)` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js wait <seconds>` |
| `browser_close()` | `node /home/aceos/Projects/hackbot/scripts/playwright-fallback.js close` |

## Rules — non-negotiable

1. **One action per invocation.** Each call spawns a fresh server, performs
   ONE action, prints the result, exits. Chain calls: `navigate` → `snapshot`
   → `click` → `snapshot`. Do not expect state to survive between calls
   unless a profile is used.
2. **Profile resolution (in order):** `--profile <dir>` flag →
   `$PLAYWRIGHT_MCP_USER_DATA_DIR` → `$AGENT_BROWSER_PROFILE` → ephemeral.
   After `claim-account.sh` (see `reference/session-bootstrap.md`) the env
   vars are already set — just run the command. Without a profile the
   session does NOT persist between calls.
3. **Screenshots must be written inside the project dir.** The server only
   allows writes under `/home/aceos/Projects/hackbot` (e.g.
   `/home/aceos/Projects/hackbot/.playwright-mcp/evidence.png`). Writing to `/tmp` fails
   with `File access denied`.
4. **Element refs come from `snapshot` output.** Always run `snapshot` first,
   read the `[ref=eNN]` values, then use them in `click` / `type` / `hover`.
5. **The browser is headed** (same as the MCP) — a Chrome window opens per
   call. Same flags: `--no-sandbox --browser chrome --caps vision
   --console-level info --ignore-https-errors`.
6. **`navigate` prints the snapshot automatically** — you get the
   accessibility tree + refs in one call, no separate `snapshot` needed.
7. **If the helper itself errors**, check the printed `SERVER STDERR` — the
   most common failure is a profile dir locked by another Chrome instance
   (kill it: `pkill -f <profile-dir>`), or `playwright-mcp` not on PATH
   (reinstall: `npm install -g @playwright/mcp`).
