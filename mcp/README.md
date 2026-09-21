# Hackbot MCP Servers

These are the Model Context Protocol (MCP) servers that hackbot agents use.

## Installed MCPs

### Caido Proxy
HTTP/HTTPS intercept proxy for bug bounty traffic analysis.

### Intigriti
Official Intigriti API — list programs, fetch scopes, manage findings.

### captcha-bridge
Chrome extension bridge for automated CAPTCHA solving during hunts.

### Composio
Email/Gmail integration for inbox checking during account-based hunts.

### Playwright MCP
Browser automation via Playwright MCP (`@playwright/mcp`). Used by the
`web-hacking` skill for rendering XSS/HTML-injection probes, driving login
state machines, and verifying cache-poisoning/CSRF impact in a real browser.

- Runs via `npx -y @playwright/mcp@latest` (no global install needed).
- Configured with `--browser chrome`, `--no-sandbox`, vision caps, and an
  isolated `--user-data-dir` per agent pointing into the browser-profiles dir.
- Requires **Google Chrome** installed on the system.
- Concurrent agents each run their **own** Playwright MCP server process
  pointed at their own profile (`--user-data-dir`), so cookies/tabs/sessions
  stay isolated. See the `web-hacking` skill's "Concurrent agents" section
  (`reference/session-bootstrap.md`).

## Setup

MCPs are installed automatically by `./setup.sh`. If you need to install manually:

```bash
./scripts/install-mcps.sh
```

## API Keys

Some MCPs require API keys. Get them from:

- **Caido**: Settings → API (in the Caido UI)
- **Intigriti**: https://app.intigriti.com/profile/api-keys
- **Composio**: https://dashboard.composio.dev
