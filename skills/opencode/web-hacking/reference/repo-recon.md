# Repo Recon — Spawn After Initial Feature Exploration

Load this only when you're about to spawn `@repo-recon`.

Spawning `@repo-recon` is not optional and not a final-pass step. Do it early —
while your own exploration is still warm — so its findings steer the rest of
the hunt. The subagent runs **in parallel** with your continued testing.

## When to spawn

Trigger as soon as ANY of these are true:
- You can name the stack/package (from `X-Powered-By`, `__NEXT_DATA__`,
  generator meta tags, JS bundle names, `/version`, `CHANGELOG`)
- Target looks like an open-source product, CMS, or known app
- GitHub search for the company name returns a credible match

## How to spawn

```
@repo-recon

TARGET: <domain or product name>
VERSION_HINT: <anything fingerprinted — version string, framework, package name>
OUTPUT_DIR: ~/Projects/hackbot/hunts/<handle>-<YYYYMMDD>/recon/
```

Remember to include the Subagent Scope Inheritance requirements from core
`SKILL.md` (authorized host list, discovered-host rule, action-endpoint
deny-list, read-only spelled out as forbidden verbs) in the spawn prompt —
this subagent does not inherit scope implicitly.

## What repo-recon does (load the skill to see full detail)

The subagent runs five phases:

| Phase | What it does |
|---|---|
| **0 — Discover** | `gh search repos`, org search, live target headers, JS bundle names |
| **1 — Clone** | Full history fetch (`--unshallow`), pin to deployed version |
| **2 — Deleted files & forensics** | Enumerate every file ever deleted; restore & read high-value ones (creds, config, old auth); sweep dangling/orphaned commits from force-pushes |
| **3 — Patch archaeology** | Find security commits; read the BEFORE-fix code to understand the anti-pattern; detect partial fixes (patched one file, missed siblings); grep current tree for unpatched instances |
| **4 — Dependency audit** | osv-scanner, gitleaks, trufflehog, npm audit |

## What comes back: `priority.json`

```
secrets_found          → leaked keys/tokens in git history — test immediately
deleted_files_of_interest → recovered content of removed credential/config files
vuln_priority          → ranked vuln classes by historical frequency
  ↳ pattern           → exact anti-pattern to grep for in the live app
  ↳ partial_fix: true → patched in one place; siblings likely still vulnerable
  ↳ grep_command      → ready-to-run grep to find unpatched instances
patch_archaeology      → per-commit: pre-fix code, what wasn't fixed, attack hint
dependency_findings    → CVEs in pinned deps, exploitability context
open_issue_leads       → wontfix security issues = highest-priority endpoints
```

## How to use the results

- **`secrets_found`**: any entry with `verified: true` → test against the live
  app immediately. AWS key → call `aws sts get-caller-identity`. API key →
  hit the target's API endpoints. Don't wait.
- **`deleted_files_of_interest`**: read every recovered file. Old auth
  implementations reveal bypass paths. Old config files reveal infra structure.
- **`vuln_priority` rank 1**: that's the class the target historically can't
  stop shipping. Use `grep_command` against the live app source (jxscout
  output) to find unpatched instances. Attack those first.
- **`partial_fix: true`**: this commit patched ONE place. The `unpatched_siblings`
  list tells you exactly where the same bug still lives. Go there directly.
- **`patch_archaeology` → `attack_hint`**: read every hint. These are derived
  from the actual pre-fix code, not guesses.
- **`open_issue_leads` → `wontfix: true`**: maintainer explicitly declined to
  fix. Go straight to that endpoint.

All findings are hypotheses — `@bug-validator` still has the final say.
Log any `interesting.md`-worthy leads from `priority.json` using the same
anchor convention as everything else (see core `SKILL.md` Logging section).
