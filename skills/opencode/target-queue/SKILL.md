---
name: target-queue
description: "Hackbot target queue system. Manages the persistent list of Intigriti programs to hunt — pulling from the MCP, scoring by bounty/recency/richness, tracking what's been hunted, and enforcing cooldown windows so the bot doesn't re-hunt a target too soon. Use this skill whenever the orchestrator needs to pick a target, mark one complete, or check queue state."
---


# Target Queue

Persistent JSON queue at `{{HACKBOT_MISC_DIR}}/target-queue.json`.
Managed by `hackbot-queue` (symlink to `queue-manager.sh`).
History log at `{{HACKBOT_MISC_DIR}}/queue-history.jsonl`.

---

## Command Reference

### Initialize / Refresh Queue
Pull all open bounty programs from Intigriti, score and rank them.
Run this once at session start, or weekly to pick up new programs.
```bash
hackbot-queue init
```
- Filters: `status=open`, `maxBounty > 0` (skips VDPs)
- Preserves existing scores, boosts, and hunt history on refresh
- Re-opens any `done` targets whose `rehunt_after` date has passed

---

### Get Next Target
Pick the highest-scored pending target and mark it `active`:
```bash
NEXT=$(hackbot-queue next)
# Returns JSON or "NO_TARGETS_AVAILABLE"

HANDLE=$(echo "$NEXT" | jq -r '.handle')
PROGRAM_ID=$(echo "$NEXT" | jq -r '.program_id')
MAX_BOUNTY=$(echo "$NEXT" | jq -r '.max_bounty')
```
Respects `MIN_REHUNT_DAYS` env var (default: 7 days).

---

### Mark Target Done
Call when a worker finishes. Sets `rehunt_after` based on verdict:
```bash
hackbot-queue done <handle> <bugs_found> <verdict>

# Verdict options:  RICH_TARGET | MODERATE | THIN_TARGET | WAF_BLOCKED | AUTH_BLOCKED
# Rehunt cooldown:  RICH=3d  MODERATE=7d  THIN=30d  WAF/AUTH=14d

# Examples:
hackbot-queue done "example-inc" 3 "RICH_TARGET"   # returns in 3 days
hackbot-queue done "thin-corp" 0 "THIN_TARGET"     # returns in 30 days
hackbot-queue done "blocked-co" 0 "WAF_BLOCKED"    # returns in 14 days
```

---

### Skip a Target (thin verdict during recon)
Call during Phase 2 when richness score is too low to bother:
```bash
hackbot-queue skip <handle> [reason]

# Example:
hackbot-queue skip "static-site" "Only 1 rich signal — static marketing site"
```
Automatically sets `rehunt_after` to 30 days.

---

### Mark Target Failed (worker crashed/errored)
Resets back to `pending` so it gets retried:
```bash
hackbot-queue fail <handle> [reason]
```

---

### View Queue Status
```bash
hackbot-queue status
```
Prints ranked table with status, score, bugs found, last hunted date.

---

### View Hunt History
```bash
hackbot-queue history
```
Last 30 hunt entries: date, handle, bugs, verdict.

---

### Boost a Target's Score
After finding a bug on a target — boost its priority for the next pass:
```bash
hackbot-queue boost <handle> <points>

# Example — found 2 bugs, boost for return visit:
hackbot-queue boost "example-inc" 25
```

---

### Re-queue with Custom Cooldown
```bash
hackbot-queue requeue <handle> <days>

# Example — come back in 3 days after a juicy find:
hackbot-queue requeue "example-inc" 3
```

---

### Reset a Target to Pending
```bash
hackbot-queue reset <handle>
```

---

## Integration with Orchestrator

The orchestrator uses the queue like this:

```bash
# Phase 0 — init queue
hackbot-queue init

# Phase 1 — pick target
NEXT=$(hackbot-queue next)
[[ "$NEXT" == "NO_TARGETS_AVAILABLE" ]] && {
  hackbot-notify "⚠️ No targets available — queue exhausted or all on cooldown"
  exit 0
}
HANDLE=$(echo "$NEXT" | jq -r '.handle')
PROGRAM_ID=$(echo "$NEXT" | jq -r '.program_id')

# ... Phase 2 recon, Phase 3 spawn worker ...

# Phase 2 — thin target
hackbot-queue skip "$HANDLE" "Only $SIGNAL_COUNT rich signals"
hackbot-notify skip "$HANDLE" "Thin — skipping"

# Phase 4 — worker done
hackbot-queue done "$HANDLE" "$BUGS_FOUND" "$VERDICT"

# Boost if bugs found
[[ $BUGS_FOUND -gt 0 ]] && hackbot-queue boost "$HANDLE" 20
```

---

## Queue File Format
`{{HACKBOT_MISC_DIR}}/target-queue.json`

```json
[
  {
    "handle": "example-inc",
    "program_id": "abc-123",
    "name": "Example Inc Bug Bounty",
    "max_bounty": 10000,
    "min_bounty": 100,
    "tags": ["Software"],
    "confidentiality": "Public",
    "status": "pending",
    "score": 30,
    "boost": 20,
    "bugs_found": 3,
    "last_hunted": "2026-09-10T14:00:00Z",
    "last_verdict": "RICH_TARGET",
    "active_worker": null,
    "started_at": null,
    "queued_at": "2026-09-01T00:00:00Z",
    "rehunt_after": "2026-09-13T14:00:00Z"
  }
]
```

**Status values:** `pending` → `active` → `done` / `skipped` / `failed`

---

## Cooldown Windows

| Verdict | Rehunt After |
|---|---|
| RICH_TARGET | 3 days |
| MODERATE | 7 days |
| THIN_TARGET | 30 days |
| WAF_BLOCKED | 14 days |
| AUTH_BLOCKED | 14 days |
| SKIPPED | 30 days |

Override default minimum window: `MIN_REHUNT_DAYS=3 hackbot-queue next`
