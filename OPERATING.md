# Hackbot — Agent Operating Guide

This is the single reference for operating hackbot as an autonomous bug-bounty
pipeline. Read this file first; dig into scripts/agents/skills only when this
guide doesn't answer the question.

**Platform: OpenCode only.** No Antigravity, no agy. Everything runs through
`opencode`, tmux, and the CLI tools below.

---

## 1. What hackbot is

A fully autonomous bug-hunting pipeline for Intigriti programs:

```
Intigriti MCP ──► target-queue.json ──► worker pool (tmux) ──► findings.jsonl ──► Telegram
                     (queue-manager)      (worker-pool.sh)      (dashboard)      (notify)
```

- **Queue** holds scored Intigriti programs (pending/active/done/skipped, cooldowns).
- **Workers** are `opencode run --agent hunter` sessions, one per tmux window in
  session `hackbot`, each hunting one target.
- **Findings** are logged to `findings.jsonl` and pushed to Telegram.
- **Watchdog** periodically spawns a `worker-monitor` agent to diagnose/fix stuck workers.

---

## 2. Config & data locations

| Thing | Path |
|---|---|
| Runtime config | `~/.hackbot/config.json` |
| Target queue | `~/Projects/hackbot-misc/target-queue.json` |
| Queue history | `~/Projects/hackbot-misc/queue-history.jsonl` |
| Findings | `~/Projects/hackbot-misc/findings.jsonl` |
| Reports (markdown) | `~/Projects/hackbot-misc/reports/` |
| Worker pool state/logs | `~/Projects/hackbot-misc/worker-pool/` (`pool.json`, `pool.log`, `worker-<id>.log`) |
| Watchdog state/reports | `~/Projects/hackbot-misc/worker-pool/watchdog-*` |
| Hunt session dirs | `~/Projects/hackbot/hunts/sessions/<domain>/` |
| Payloads | `~/Projects/payloads/coffinxp-payloads` (from config `payloads_dir`) |
| Web dashboard | `~/Projects/hackbot-misc/dashboard/` (deployed via `deploy-web.sh`) |

Key config values: `intigriti_username=aceproulx`, `email_base=aceproulx`,
`email_domain=intigriti.me`, `telegram_chat_id=7699164876`,
`blind_xss_url=https://xss.report/c/aceos`, `caido_proxy_port=8080`,
`curl_proxy_port=8081`, `max_worker_slots=4`, `browser_isolation=isolated`.

---

## 3. CLI tools (installed to ~/.local/bin)

### `hackbot-queue` — target queue
```
hackbot-queue init                          # pull all open Intigriti programs, score, preserve history
hackbot-queue next                          # pop next pending target (marks it active) → JSON
hackbot-queue done <handle> <bugs> <verdict>  # verdict: RICH_TARGET|THIN_TARGET|WAF_BLOCKED|AUTH_BLOCKED
hackbot-queue skip <handle> [reason]
hackbot-queue fail <handle> [reason]
hackbot-queue status                        # queue overview
hackbot-queue history                       # past runs
hackbot-queue reset <handle>                # back to pending
hackbot-queue requeue <handle> <days>       # set rehunt_after
hackbot-queue boost <handle> <pts>          # +score for re-hunt priority
hackbot-queue add <url> [name] [notes]      # manual target
```

### `hackbot-workers` — worker pool (tmux)
```
hackbot-workers start [--slots N]           # default 2; fills all slots from queue
hackbot-workers status                      # slots, handles, status, bugs found
hackbot-workers stop                        # kill session, mark workers killed, reset queue to pending
hackbot-workers logs [worker_id]            # pool log or per-worker log
hackbot-workers attach                      # tmux attach to session 'hackbot'
hackbot-workers start-target <handle>       # start one hunt now (dashboard "Start Hunt")
hackbot-workers stop-target <handle>        # kill one worker, requeue target
```
Each worker = tmux window `hackbot:<slot>`. `--budget` was removed — no cost tracking.

### `hackbot-notify` — Telegram
```
hackbot-notify "<message>"                          # plain
hackbot-notify bug "<program>" "<title>" "<sev>" "<bounty_est>"
hackbot-notify encourage "<domain>"
hackbot-notify kill "<domain>" "<reason>"
hackbot-notify session-start "<session_dir>"
hackbot-notify session-end "<session_dir>" "<bugs>" "<bounty_est>"
hackbot-notify interesting "<domain>" "<note>"
```

### `hackbot-dashboard` — findings
```
hackbot-dashboard show | stats | findings | program <handle> | severity <sev>
hackbot-dashboard add --program <h> --title <t> --severity <s> --status <st> \
    --bounty <est> --evidence <caido_ids> --url <url>
hackbot-dashboard export | open
```
Statuses: `confirmed|duplicate|informative|pending|triaged`. Severities: `Critical|High|Medium|Low`.

### `hackbot-watchdog` — worker monitor
```
hackbot-watchdog start [--interval 1800] [--timeout 900]   # foreground loop
hackbot-watchdog daemon [...]                              # background (nohup)
hackbot-watchdog once                                      # single monitor run
hackbot-watchdog stop | status | logs | clean
```
Spawns the `worker-monitor` agent every interval (default 30 min) in tmux session
`hackbot-watchdog` (window `monitor`). Requires `worker-monitor` agent installed.

### `refill-watcher.sh` — slot refill
```
scripts/refill-watcher.sh [--interval 60] [--max-slots 4]
```
When a slot frees up, starts the next pending target. For overnight autonomous runs.

### Web dashboard
```
python3 scripts/dashboard-web.py [--port 7878] [--host 127.0.0.1]   # dev
scripts/deploy-web.sh                                               # deploy to hackbot-misc with real paths
```
Wild Hunt-style operator UI. **Always deploy via `deploy-web.sh`** — the repo
copy has `{{PLACEHOLDERS}}` and won't resolve paths.

---

## 4. Agents (opencode)

| Agent | Mode | Purpose |
|---|---|---|
| `hunter-orchestrator` | primary | Top-level autonomous overnight hunts. Picks targets, scores richness, spawns hunters, monitors/kills/encourages. **Use for autonomous sessions.** |
| `hunter` | primary | Single-target long-running hunt (Ralph loop). Use for one manual target. |
| `bug-validator` | subagent | Adversarially re-tests a candidate finding → CONFIRMED / NEEDS MORE WORK / FALSE POSITIVE. **Never skip it.** |
| `repo-recon` | subagent | Finds target's public repo, git forensics, outputs `priority.json` steering attack classes. |
| `worker-monitor` | subagent | Watchdog's monitor: checks running workers, diagnoses/fixes, writes report. |
| `web-builder` | primary | Front-end/full-stack build requests (this agent). |

---

## 5. Skills (skills/opencode/, installed to ~/.config/opencode/skill/)

- **`web-hacking`** — main hunting skill (Ralph loop, routes to hunt-* skills). Load first for any web hunt.
- **`hunt-*`** (30+) — per-attack-class knowledge: xss, sqli, idor, ssrf, ssti, rce, csrf, cors, ato, auth-bypass, jwt-crypto, race-condition, graphql, nosqli, lfi, xxe, deserialization, file-upload, http-smuggling, cache-poison, host-header, open-redirect, clickjacking, dom, oauth, session, brute-force, mfa-bypass, business-logic, misc, shadow-api, source-leak, spa-api, springboot, nextjs, nodejs, laravel, aspnet, sharepoint, grpc, websocket, ntlm-info, tls-network, cloud-misconfig, llm-ai, rag-vector, ldap, html-injection, api-misconfig, supply-chain-attack-recon, gRPC, etc.
- **`caido-mode`** — Caido SDK usage (search history, replay, fuzz, findings).
- **`clairvoyance-graphql`** — GraphQL schema reconstruction when introspection is off.
- **`findings-dashboard`** — log findings + Telegram notify after CONFIRMED.
- **`evidence-hygiene`** — evidence collection standards.
- **`email-inbox-check`** — check AgentMail/Gmail inbox (registration emails).
- **`agent-device` / `mobile-hacking` / `objection`** — mobile app testing.
- **`bugcrowd-reporting` / `report-writing` / `redteam-report-template`** — report formats.
- **`security-arsenal`** — payloads, bypass tables, wordlists, always-rejected bugs.
- **`notify`** — Telegram notification layer (always call on key events).
- **`target-queue`** — queue management rules (cooldowns, scoring).
- **`parallel-workers`** — managing 2-3 concurrent workers in tmux.
- **`hunter-orchestrator`** — the orchestrator skill itself.
- **`repo-recon`** — spawn for open-source targets.
- **`planning-decomposition` / `frontend-design` / `component-patterns` / `ship-checklist`** — web-builder skills.

---

## 6. MCP servers

| Server | Purpose |
|---|---|
| `intigriti` | Program list, scope, scope diff, recommend-program |
| `caido` | HTTP proxy: send/edit/batch requests, fuzz (automate), replay sessions, findings, tamper rules, WebSocket, race-window |
| `composio` | Gmail (registration emails, inbox) |
| `playwright` | Browser automation (headed for XSS validation) |
| `captcha-bridge` | reCAPTCHA solving |
| `jadx` / `ghidra` | Android / binary analysis |
| `agent-device` | iOS/Android device automation |

---

## 7. Standard workflows

### Start an autonomous overnight hunt
```bash
hackbot-queue init
hackbot-workers start --slots 4        # or 3 overnight
tmux attach -t hackbot                 # watch live
hackbot-watchdog daemon                # auto-monitor workers
scripts/refill-watcher.sh --max-slots 4 &   # auto-refill slots
```
Or run the orchestrator agent directly: `opencode run --agent hunter-orchestrator`.

### Worker lifecycle (per target)
1. `hackbot-queue next` → handle, program_id, max_bounty.
2. Spawn `@hunter` with full brief (handle, program_id, hunt dir, slot, richness, time cap, deny list, registration emails, findings command, done command).
3. On confirmed finding → `hackbot-dashboard add ...` immediately (never batch).
4. On finish → `hackbot-queue done <handle> <bugs> <verdict>`; if bugs>0 and RICH_TARGET → `hackbot-queue boost <handle> 20` for 3-day return.
5. Refill slot with next target.

### Log a confirmed finding
```bash
hackbot-dashboard add --program "example-inc" --title "IDOR on /api/user/{id}" \
  --severity "High" --status "confirmed" --bounty 2000 \
  --evidence "caido:req_abc123" --url "https://app.example.com/api/user/17"
```

### Stop everything
```bash
hackbot-workers stop        # kills tmux session, marks workers killed, queue → pending
hackbot-watchdog stop
```

---

## 8. Hard rules

1. **Never probe out-of-scope assets.** Newly discovered hosts → log only.
2. **Never skip @bug-validator.** A finding is NOT confirmed until it returns CONFIRMED.
3. **Respect no-automated-scanning rules** — manual curl + browser only.
4. **One worker per program at a time.**
5. **Log everything** — spawns, kills, encourages, findings, skips.
6. **Use Caido for all HTTP** in hunting/validation (never raw curl for testing).
7. **Deploy dashboard via `deploy-web.sh`**, never bare `cp`.
8. **install-skills.sh is opencode-only** — usage: `bash scripts/install-skills.sh --config ~/.hackbot/config.json [--no-prompt]` (no `--platform` arg).

---

## 9. Repo layout (what lives where)

```
hackbot/
├── OPERATING.md          ← this file
├── README.md             ← user-facing install docs
├── Makefile              ← install / update / sync / clean
├── setup.sh              ← interactive install
├── update.sh             ← pull + re-install
├── config/config.json    ← repo copy of config (placeholders)
├── agents/opencode/      ← agent definitions (hunter, orchestrator, validator, etc.)
├── skills/opencode/      ← skill templates (installed to ~/.config/opencode/skill/)
├── scripts/              ← CLI tools + installers
│   ├── queue-manager.sh      → hackbot-queue
│   ├── worker-pool.sh        → hackbot-workers
│   ├── notify-telegram.sh    → hackbot-notify
│   ├── dashboard.sh          → hackbot-dashboard
│   ├── watchdog.sh           → hackbot-watchdog
│   ├── refill-watcher.sh
│   ├── dashboard-web.py + dashboard/   ← web dashboard package
│   ├── deploy-web.sh
│   └── install-skills.sh / install-mcps.sh / install-tools.sh / sync-to-repo.sh
└── hunts/                ← per-target hunt dirs + sessions/
```