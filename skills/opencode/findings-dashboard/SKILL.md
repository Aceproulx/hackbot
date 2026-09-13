---
name: findings-dashboard
description: "Hackbot findings dashboard and log. Use hackbot-dashboard to view stats, browse findings by severity/program, log new confirmed findings, and export markdown reports. All findings live in {{HACKBOT_MISC_DIR}}/findings.jsonl. Call this skill after @bug-validator returns CONFIRMED to log the finding and fire a Telegram notification."
---


# Findings Dashboard

All confirmed findings live in `{{HACKBOT_MISC_DIR}}/findings.jsonl` (append-only JSONL).
Dashboard tool: `hackbot-dashboard` (symlink to `{{HACKBOT_MISC_DIR}}/dashboard.sh`).
Reports exported to: `{{HACKBOT_MISC_DIR}}/reports/`.

---

## Commands

### Full Dashboard (stats + table + top programs)
```bash
hackbot-dashboard show
```

### Stats Only
```bash
hackbot-dashboard stats
```

### Browse All Findings
```bash
hackbot-dashboard findings
```

### Filter by Program
```bash
hackbot-dashboard program <handle>
# Example:
hackbot-dashboard program "acme-corp"
```

### Filter by Severity
```bash
hackbot-dashboard severity <Critical|High|Medium|Low>
```

### Log a New Finding
Call this immediately after `@bug-validator` returns CONFIRMED:
```bash
hackbot-dashboard add \
  --program "<handle>" \
  --title "<bug title>" \
  --severity "<Critical|High|Medium|Low>" \
  --status "confirmed" \
  --bounty <est_usd> \
  --evidence "caido:<req_id1>,<req_id2>" \
  --url "<vulnerable endpoint>" \
  --notes "<optional one-liner>"
```
This also fires `hackbot-notify bug` automatically for confirmed findings.

**Status values:** `confirmed` | `triaged` | `duplicate` | `informative` | `n/a` | `pending`

### Export Markdown Report
```bash
hackbot-dashboard export
# Output: {{HACKBOT_MISC_DIR}}/reports/findings-YYYY-MM-DD.md
```

---

## Findings File Format
`{{HACKBOT_MISC_DIR}}/findings.jsonl` — one JSON object per line:

```json
{
  "id": "f-1789295472-df8bb1",
  "ts": "2026-09-13T17:00:00Z",
  "program": "example-inc",
  "title": "IDOR on /api/user/{id} allows cross-account data read",
  "severity": "High",
  "status": "confirmed",
  "bounty_est": 2000,
  "bounty_paid": null,
  "evidence": "caido:req_abc123,req_def456",
  "url": "https://app.example.com/api/user/17",
  "notes": "userA can read userB's private data by incrementing id",
  "reported_at": null,
  "resolved_at": null
}
```

---

## Integration with Orchestrator / Worker

In the bug-hunting worker, after `@bug-validator` returns CONFIRMED:
```bash
hackbot-dashboard add \
  --program "$PROGRAM_HANDLE" \
  --title "$BUG_TITLE" \
  --severity "$SEVERITY" \
  --status "confirmed" \
  --bounty "$BOUNTY_EST" \
  --evidence "$CAIDO_REQUEST_IDS" \
  --url "$VULN_URL"
# ↑ This auto-fires hackbot-notify bug too
```

In the orchestrator session-end summary:
```bash
hackbot-dashboard stats
hackbot-dashboard export
```
