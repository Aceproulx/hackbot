---
name: hackbot-dashboard-conventions
description: Internal conventions and known gotchas for the Hackbot dashboard codebase (scripts/dashboard/ + scripts/*.sh). Load before editing dashboard routes, worker-pool/queue scripts, or anything that reads hunt dirs, pool state, or findings. Prevents recurring bugs: date-suffixed hunt dirs, unrendered install templates, stale pool state, findings-vs-reports confusion.
---

## When this applies

Any edit to `scripts/dashboard/` (router, views, actions, state,
config), `scripts/worker-pool.sh`, `scripts/queue-manager.sh`, or any
feature that reads hunt directories, worker pool state, the target
queue, or findings. These four conventions have each caused a real
bug; assume they still apply.

## 1. Hunt dirs are date-suffixed — never assume bare handle paths

The worker pool creates hunt dirs as `<handle>-<date>`, e.g.
`~/Projects/hunts/challenge-0326-intigriti-io-20260915/`. Queue
entries, report URLs, and the findings log only carry the bare handle
(`challenge-0326-intigriti-io`).

- ALWAYS resolve a handle to a real dir through the shared helpers in
  `scripts/dashboard/router.py`:
  - `_resolve_hunt_root(name)` — exact match in HUNTS_ROOT, then
    date-suffixed glob (`<handle>-*`, newest first), then SESSIONS_ROOT.
  - `_evidence_root(safe)` — evidence dir under the resolved root.
- NEVER write `os.path.join(HUNTS_ROOT, safe)` directly in a new route.
  It 404s for every current hunt (they all have date suffixes).
- The `sessions/` dir can contain a bare-handle dir with only a
  `session.log` and NO `reports/` — it is a session recording, not a
  hunt. Prefer HUNTS_ROOT (with date-suffix glob) over it.
- REVERSE CASE (real bug, fixed): a worker can write its report to
  SESSIONS_ROOT while leaving a date-suffixed hunt dir with an EMPTY
  `reports/` behind. `resolve_hunt_root` now prefers a date-suffixed dir
  that actually contains reports, and falls through to SESSIONS_ROOT
  before giving up. If a report URL 404s, check BOTH the date-suffixed
  dir AND `sessions/<handle>/reports/`.

## 2. Repo shell scripts are install templates — don't run them raw

`scripts/worker-pool.sh` and `scripts/queue-manager.sh` in the repo
are install templates containing `{{HACKBOT_MISC_DIR}}`,
`{{EMAIL_BASE}}`, `{{EMAIL_DOMAIN}}` placeholders. Running them
unrendered points at literal paths like
`{{HACKBOT_MISC_DIR}}/target-queue.json` and breaks every Start/Stop
action (it silently falls back to `hackbot-queue init`, which then
fails on unrelated jq errors).

- The dashboard (`scripts/dashboard/config.py`) resolves
  `WORKER_POOL` / `QUEUE_MANAGER` preferring the installed rendered
  copies (`~/.local/bin/hackbot-workers`, `~/.local/bin/hackbot-queue`)
  and skips any candidate still containing `{{`.
- When testing worker-pool/queue behavior, use the installed
  `hackbot-workers` / `hackbot-queue` commands, or render the template
  first. Do not `bash scripts/worker-pool.sh ...` directly.
- If you edit `scripts/queue-manager.sh` or `scripts/worker-pool.sh`,
  mirror the change into `{{HACKBOT_MISC_DIR}}/` (the installed
  copies) or the dashboard keeps using the old behavior.

## 3. Pool/queue disk state can go stale — trust liveness

`{{HACKBOT_MISC_DIR}}/worker-pool/pool.json` and
`target-queue.json` can say a worker is `running` / a target is
`active` while no process exists (crash, reboot, killed tmux). The
dashboard renders "HUNTING" + a Stop button purely from this disk
state.

- Before trusting "running", check liveness: `tmux ls` (session
  `hackbot`) and `ps aux | grep "opencode run"`.
- Recovery path is Stop-then-Start via the dashboard API (the exact
  calls the UI buttons make):
  - `POST /api/targets/stop`  `{"handle": ...}` — marks killed, resets
    queue item to pending.
  - `POST /api/targets/start` `{"handle": ...}` — spawns a fresh worker
    (tmux window + `opencode run --agent hunter`).
- `cmd_start_target` refuses if pool state says a worker is running, so
  Stop must come first when state is stale.

## 4. Stats come from findings.jsonl — reports are staged, not findings

- Dashboard stats (`/api/stats` findings count, `/v/findings`) read
  `{{HACKBOT_MISC_DIR}}/findings.jsonl` (one JSON object per entry,
  pretty-printed multi-line).
- A report `.md` under a hunt dir's `reports/` is a staged submission.
  It does NOT appear in stats until it is logged as a finding (via the
  findings-dashboard skill / `hackbot-dashboard log`).
- "New report but stats not found" usually means the report page 404s
  (see convention 1), not that the finding is missing — check
  findings.jsonl first.

## 5. Report TTS: browser voices are unreliable — server fallback exists

The report page's Read-aloud ("Vox") engine uses the Web Speech API
(`window.speechSynthesis`). On Chrome/Linux the voice list is often
empty: Chrome connects to speech-dispatcher via the system socket
`/run/speech-dispatcher/speechd.sock`, which requires the
`speech-dispatcher` group AND a Chrome restart to pick up (voices are
cached at startup). Result: `getVoices()` returns `[]`, the Read button
stays disabled, caption reads "loading voices…" forever.

- The dashboard ships a server-side fallback: `GET /api/tts?text=...`
  synthesizes WAV audio via `espeak-ng` (cached by sha1 in
  `/tmp/hackbot-tts/`). `GET /api/tts?probe=1` returns `{"ok": true}`
  when espeak-ng is installed.
- `tts.py` probes `/api/tts?probe=1` on load; when the browser has no
  voices (`UNSUPPORTED || !selectedVoices.length`), `Vox.speak` routes
  through `serverSpeak`/`serverPlayNext` — a hidden `<audio>` element
  plays server-synthesized chunks with the same sentence/word
  highlighting, pause/resume/stop.
- The segmentation TreeWalker reads inline `<code>` and `<pre>` blocks
  aloud too (grey-highlighted endpoints/URLs are report content). Only
  `script`, `style`, `.cv-ctl`, `.cv-out` are excluded. If someone
  "fixes" the walker to skip code again, grey-highlighted URLs silently
  vanish from read-aloud.
- If TTS is silent on a report page, check BOTH: (a) does the browser
  have voices (`speechSynthesis.getVoices().length`), and (b) is
  `espeak-ng` installed (`which espeak-ng`). The fallback only engages
  when (a) is empty AND (b) is true.
- System fix for native voices (optional, needs Chrome restart):
  `sudo usermod -aG speech-dispatcher aceos` +
  `sudo systemctl enable --now speech-dispatcherd.service`.

## Verification habit

After any dashboard route change: restart the server
(`nohup python3 scripts/dashboard --port 7878 &`) and smoke-test the
affected URLs with `urllib.request` — including a date-suffixed hunt
handle like `/report/challenge-0326-intigriti-io/<report>.md`.