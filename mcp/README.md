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
