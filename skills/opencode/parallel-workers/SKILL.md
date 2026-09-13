---
name: parallel-workers
description: "Hackbot parallel worker pool. Runs 2-3 simultaneous bug-hunting workers in tmux windows, each targeting a different Intigriti program. Orchestrator spawns workers, monitors them, and refills slots as targets complete. Use this skill when the orchestrator needs to manage multiple concurrent workers."
---


# Parallel Workers

Runs N simultaneous bug-hunting workers, each in its own tmux window, each
hunting a different target pulled from `hackbot-queue`.

**CLI tool:** `hackbot-workers` (symlink to `{{HACKBOT_MISC_DIR}}/worker-pool.sh`)
**Worker state:** `{{HACKBOT_MISC_DIR}}/worker-pool/pool.json`
**Worker logs:** `{{HACKBOT_MISC_DIR}}/worker-pool/worker-<slot>-<handle>.log`

---

## Quick Start

```bash
# Start 2 workers with $15 total budget ($7.50 each)
hackbot-workers start --slots 2 --budget 15

# Start 3 workers with $30 budget ($10 each) — overnight mode
hackbot-workers start --slots 3 --budget 30

# Watch what's happening
tmux attach -t hackbot

# Status from another terminal
hackbot-workers status

# Stop everything
hackbot-workers stop
```

---

## Commands

### `start [--slots N] [--budget USD]`
- Pulls next N targets from `hackbot-queue`
- Spawns each into a separate tmux window as an AI session
- Fires `hackbot-notify` when each worker starts
- Default: 2 slots, $15 total budget

### `status`
Color-coded table: slot, handle, status (running/done/killed), bugs found, started time.

### `stop`
Kills the tmux session, marks all running workers as killed in pool state.

### `attach`
Attach to the tmux session to watch workers live:
```bash
hackbot-workers attach
# Then switch windows: Ctrl+B then 1, 2, 3...
```

### `logs [worker_id]`
```bash
hackbot-workers logs            # pool log
hackbot-workers logs 1-acme     # specific worker log
```

---

## How Parallelism Works

```
Orchestrator
├── hackbot-queue next → target A  → tmux window 1 → AI worker (bug-hunting)
├── hackbot-queue next → target B  → tmux window 2 → AI worker (bug-hunting)
└── hackbot-queue next → target C  → tmux window 3 → AI worker (bug-hunting)

Each worker independently:
  → fetches scope from Intigriti MCP
  → hunts using bug-hunting / web-hacking skill
  → logs findings to findings.jsonl via hackbot-dashboard add
  → marks target done via hackbot-queue done <handle> <bugs> <verdict>
  → fires hackbot-notify bug on each confirmed finding
```

---

## Orchestrator Integration (AI Agent Mode)

When running as an AI orchestrator (not CLI), spawn workers as subagents
instead of tmux windows:

```
Phase 3 — Spawn N workers in parallel:

1. Call hackbot-queue next → get target A
2. Call hackbot-queue next → get target B
3. Spawn subagent A with target A brief (do NOT await)
4. Spawn subagent B with target B brief (do NOT await)
5. Immediately start Phase 2 recon on next queued target (stay one ahead)

When a worker subagent sends its completion message:
1. Parse: bugs_found, verdict, time_spent_min
2. hackbot-queue done <handle> <bugs> <verdict>
3. hackbot-workers fills the freed slot: hackbot-queue next → spawn new subagent
```

**Key rule:** Never wait idle for a worker to finish. The orchestrator is always
preparing the next target while current workers run.

---

## Token Budget Split

| Total Budget | Slots | Per Worker | Recommended Use |
|---|---|---|---|
| $10 | 2 | $5 | Quick daytime run |
| $15 | 2 | $7.50 | Standard session |
| $30 | 3 | $10 | Overnight hunt |
| $50 | 3 | $16.67 | Deep overnight hunt |

Rule: never spawn more workers than `floor(total_budget / 5)`.
A worker with less than $5 budget will burn out before making progress.

---

## Safety Rules

1. **One worker per program.** Never two workers on the same target.
2. **Budget hard stops.** Each worker's prompt contains its individual budget.
   Workers exit gracefully at 90% of their slice.
3. **Queue owns state.** Workers call `hackbot-queue done` themselves when
   finished — the queue is the source of truth, not the pool state.
4. **Findings are atomic.** Workers call `hackbot-dashboard add` immediately on
   CONFIRMED — not in a batch at the end. If a worker crashes, findings already
   logged are safe.
5. **Out-of-scope never.** Each worker's prompt contains the full verbatim
   scope from `intigriti get_program_scope`. No scope inheritance between workers.

---

## Tmux Navigation

```
tmux attach -t hackbot     # attach
Ctrl+B, 1                  # switch to window 1 (worker slot 1)
Ctrl+B, 2                  # switch to window 2 (worker slot 2)
Ctrl+B, d                  # detach (workers keep running)
Ctrl+B, &                  # kill current window
```
