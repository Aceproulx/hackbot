# Hackbot

> Autonomous bug bounty pipeline for Intigriti researchers. Install once, hunt forever.

Hackbot is a complete bug-bounty automation framework. It bundles skills, agents, scripts, and MCP integrations for running autonomous hunting sessions via OpenCode, Antigravity CLI (agy), or both. One interactive `setup.sh` configures everything for your account.

## Features

- 🎯 Autonomous target queue management (Intigriti integration)
- 🤖 Parallel worker pool with tmux
- 📊 Findings dashboard with severity/bounty tracking
- 🔔 Real-time Telegram notifications
- 🧠 70+ bug hunting skills (web, API, mobile, cloud, source code)
- 🔍 MCP integrations (Caido proxy, Intigriti API, CAPTCHA solver, email)

## Prerequisites

- Caido (intercept proxy) — running with API enabled
- Chrome/Chromium (for agent-browser)
- agent-browser daemon (for browser automation during hunts)
- Node.js ≥ 18
- Python 3.10+
- OpenCode and/or Antigravity CLI (agy) — already installed
- tmux, jq, curl, git

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/hackbot.git
cd hackbot
chmod +x setup.sh
./setup.sh
```

Then:

```bash
hackbot-queue init
hackbot-workers start --budget 15
```

## Configuration

All settings live in `~/.hackbot/config.json` (created by `setup.sh`).

| Key | Description | Default |
|-----|-------------|---------|
| `platform` | `antigravity`, `opencode`, or `both` | — |
| `intigriti_username` | Your Intigriti username | — |
| `email_base` | Email prefix before `+`/`-` (e.g. `aceproulx`) | — |
| `email_domain` | Your email domain | `intigriti.me` |
| `telegram_bot_token` | Telegram Bot API token for notifications | — |
| `telegram_chat_id` | Telegram chat ID for notifications | — |
| `blind_xss_url` | Your blind XSS collector URL | — |
| `caido_proxy_port` | Caido proxy port | `8080` |
| `curl_proxy_port` | curl proxy port for Caido | `8081` |
| `oob_tunnel_url` | OOB/SSRF tunnel (e.g. cloudflared URL) | — |
| `payloads_dir` | Path to XSS/curl payloads directory | `~/Projects/payloads/coffinxp-payloads` |
| `sessions_dir` | Where hunt session data is stored | `~/Projects/hunts/sessions` |
| `hackbot_misc_dir` | Where hackbot runtime data lives | `~/Projects/hackbot-misc` |
| `max_worker_slots` | Max parallel workers | `2` |
| `default_budget_usd` | Default cost budget in USD | `15` |

## CLI Tools

### hackbot-notify

Sends Telegram notifications.

```bash
hackbot-notify "<message>"
hackbot-notify bug "<program>" "<title>" "<severity>" "<bounty>"
hackbot-notify encourage "<domain>"
hackbot-notify kill "<domain>" "<reason>"
hackbot-notify session-start "<session_dir>"
hackbot-notify session-end "<session_dir>" "<bugs>" "<bounty>"
```

### hackbot-queue

Target queue manager.

```bash
hackbot-queue init           # Pull programs from Intigriti, build queue
hackbot-queue next           # Get next pending target
hackbot-queue done <handle> <bugs> <verdict>   # Mark done
hackbot-queue skip <handle> [reason]           # Skip target
hackbot-queue status         # Show queue table
hackbot-queue history        # Past hunts
```

### hackbot-dashboard

Findings dashboard.

```bash
hackbot-dashboard show         # Full dashboard
hackbot-dashboard stats        # Stats only
hackbot-dashboard findings     # All findings
hackbot-dashboard add          # Log a finding
hackbot-dashboard export       # Export to markdown
```

### hackbot-workers

Parallel worker pool manager.

```bash
hackbot-workers start [--slots 2] [--budget 15]
hackbot-workers status
hackbot-workers stop
hackbot-workers logs [worker_id]
```

Workers run in tmux windows. Attach with: `tmux attach -t hackbot`

## Skills Reference

There are two skill packages: **Antigravity** (flat `.md` files) and **OpenCode** (directories with `SKILL.md`).

### Core Skills (7)

- **bug-hunting / web-hacking**: Main hunting methodology — full attack taxonomy, IP rotation, account strategies, XSS/SSRF/IDOR techniques
- **hunter-orchestrator**: Autonomous meta-orchestrator — picks targets, spawns workers, monitors progress
- **notify**: Telegram notification layer
- **target-queue**: Target queue management with scoring and cooldown
- **findings-dashboard**: Findings logging and dashboard
- **parallel-workers**: tmux-based parallel worker pool
- **repo-recon**: Source code reconnaissance — clones repos, mines history for secrets and vuln patterns

### Knowledge Skills (60+)

The `hunt-*` skill family covers: XSS, SQLi, SSRF, IDOR, XXE, SSTI, LFI, CSRF, CORS, auth bypass, OAuth, JWT, race conditions, GraphQL, gRPC, SAML, LDAP, clickjacking, HTTP smuggling, DOM clobbering, file upload, OSINT, etc.

Plus supporting skills: `mobile-hacking`, `agent-browser`, `agent-device`, `caido-mode`, `dogfood`, `email-inbox-check`, `bugcrowd-reporting`, `evidence-hygiene`, `report-writing`, `supply-chain-attack-recon`, `redteam-report-template`, `security-arsenal`, `find-skills`.

## MCPs

- **Caido MCP**: HTTP proxy integration — search history, replay/edit requests, manage findings
- **Intigriti MCP**: Intigriti API — list programs, fetch scopes, manage submissions
- **captcha-bridge MCP**: Automated CAPTCHA solving via Chrome extension bridge
- **Composio MCP**: Email/Gmail integration for inbox-based account verification

## Keeping Current

```bash
# For users:
./update.sh

# For repo authors (sync live edits back to repo):
make sync
```

## Troubleshooting

- **setup.sh fails with "command not found: jq"** — install jq first: `sudo apt install jq`
- **hackbot-notify not sending** — check `~/.hackbot/config.json` has valid Telegram token/chat_id
- **"No targets available"** — run `hackbot-queue init` first
- **Worker spawns but doesn't start hunting** — ensure OpenCode/agy is in PATH
- **MCP connection errors** — check API keys, ensure MCP server processes are running
- **macOS sed errors** — setup.sh auto-detects macOS; if issues occur, install GNU sed via `brew install gnu-sed`

## License

MIT License — use freely, modify freely.