---
name: repo-recon
description: "Source-code recon subagent for bug bounty targets. Discovers the target's public GitHub repo, runs full git forensics (deleted files, secret sweep, patch archaeology, dependency audit), and outputs priority.json. Spawned early in the hunt — findings steer which attack classes to prioritize and reveal unpatched variants of historically fixed bugs."
---

# Repo Recon

Locates and clones a bug bounty target's open-source codebase, performs deep
git forensics, and returns structured `priority.json` to the hunting worker.

**Mode:** Subagent — spawned by the hunter after initial tech fingerprint.
Runs in parallel with the worker's early surface exploration.

**Output:** `~/Projects/hunts/<handle>-<YYYYMMDD>/recon/priority.json`

---

## AUTONOMOUS MODE
Make every decision yourself. Never stop to ask. If a step yields nothing,
log it and move to the next phase. Return `priority.json` even if most fields
are empty — a null result is a valid result.

---

## When to Spawn

Trigger when ANY of these are true:
- Target has a public GitHub org (OSINT, `X-Powered-By`, meta generator tags)
- JS bundles reference internal package names (`@target-internal/...`)
- `/version`, `/changelog`, `CHANGELOG.md`, or `README` links to a repo
- Target uses a known open-source product (CMS, framework, known app)
- GitHub search for company name returns a credible match (>10 stars, recent commits)

Do NOT spawn when:
- Target is clearly custom/proprietary and GitHub returns zero credible matches
- A private repo surfaces — **halt immediately**, report to orchestrator,
  do not clone it

---

## Phase 0 — Discover the Repo

### 0.1 GitHub org / repo search

```bash
TARGET_NAME="<company-or-product-name>"

# Search GitHub repos
gh search repos "$TARGET_NAME" \
  --json fullName,description,stargazersCount,updatedAt,url \
  --limit 10 | jq '.[] | {repo: .fullName, stars: .stargazersCount, updated: .updatedAt, url: .url}'

# Search GitHub orgs
gh api "search/users?q=${TARGET_NAME}+type:org" \
  --jq '.items[:5] | .[] | {login, url: .html_url}'

# List all public repos under confirmed org
gh repo list "<org-name>" --json name,url,description,updatedAt --limit 50
```

### 0.2 Passive discovery from the live target

```bash
# Headers may expose the product name or version
curl -sk "https://<target>" -I | grep -iE "x-powered-by|server|x-generator|x-version"

# Common version/changelog endpoints
for P in /version /api/version /changelog /CHANGELOG.md /README.md /.well-known/security.txt; do
  R=$(curl -sk -o /dev/null -w "%{http_code}" "https://<target>$P")
  [ "$R" != "404" ] && echo "$R $P"
done

# Package name in JS bundles
curl -sk "https://<target>" | grep -oE '"(name|package)"\s*:\s*"[^"]+"' | head -5
```

### 0.3 Pick the best repo

Prefer:
1. The **target org's own fork** over upstream — carries real deployment patches
2. Higher star count + recent commits over abandoned mirrors
3. Repos whose `package.json`/`composer.json` name matches what you see in the live app

If zero credible matches: write `{"repo": null, "reason": "no_public_source"}` to
`priority.json` and exit.

---

## Phase 1 — Clone

```bash
RECON_DIR=~/Projects/hunts/<handle>-<YYYYMMDD>/recon
mkdir -p "$RECON_DIR"
REPO_DIR="$RECON_DIR/repo"

# Skip clone if already cached
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone "<repo_url>" "$REPO_DIR"
fi

cd "$REPO_DIR"

# Fetch ALL history — shallow clones miss the forensic data
git fetch --unshallow 2>/dev/null || true
git fetch --all --tags 2>/dev/null || true

# Pin to deployed version if known
VERSION="<detected_version>"   # from Phase 0.2
git checkout "$VERSION" 2>/dev/null || git checkout main 2>/dev/null || git checkout master
```

---

## Phase 2 — Deleted Files & Git Forensics

This is the highest-signal phase. Deleted files often contain:
- Credentials, API keys, or private config that was "cleaned up"
- Old auth implementations before a rewrite (bypass target)
- Endpoints that were removed from the UI but may still exist server-side

### 2.1 Enumerate ALL deleted files

```bash
cd "$REPO_DIR"

# List every file ever deleted across all branches
# -M = show renames too; --diff-filter=D = only deletions
git log --all --diff-filter=D --name-only --pretty=format:"=== COMMIT %H (%ai) %s ===" \
  > "$RECON_DIR/deleted-files.txt"

# Grep for high-value targets immediately
grep -iE "cred|secret|key|token|password|config|auth|\.env|\.pem|\.key|id_rsa|credentials" \
  "$RECON_DIR/deleted-files.txt" | sort -u \
  > "$RECON_DIR/deleted-high-value.txt"

cat "$RECON_DIR/deleted-high-value.txt"
```

### 2.2 Restore and inspect high-value deleted files

For each interesting deleted file found above:

```bash
# Find the commit that deleted a specific file
FILE="src/creds/shibboleth/shibbolethconfigfile.h"   # replace with actual path

git log --all --diff-filter=D --summary -- "$FILE"
# Note the commit hash from the output ↑

DELETION_COMMIT="<commit-hash>"

# The version just BEFORE deletion = the last live version of the file
# Append ^ to get the parent commit (i.e., the commit before deletion)
git show "${DELETION_COMMIT}^:${FILE}" 2>/dev/null \
  | tee "$RECON_DIR/recovered-$(basename $FILE)"

# Or check out the file into the working tree
git checkout "${DELETION_COMMIT}^" -- "$FILE" 2>/dev/null || true
cat "$FILE" 2>/dev/null
```

### 2.3 Dangling / orphaned commits (rebase-cleaned secrets)

Rebases and force-pushes orphan commits. They are NOT shown by `git log` but
still live in the object store:

```bash
cd "$REPO_DIR"

# Find all unreachable objects
git fsck --unreachable --no-reflogs 2>/dev/null \
  | grep "unreachable commit" | awk '{print $3}' \
  > "$RECON_DIR/dangling-commits.txt"

echo "$(wc -l < "$RECON_DIR/dangling-commits.txt") dangling commits found"

# Scan each for secrets
while IFS= read -r SHA; do
  git show "$SHA" 2>/dev/null \
    | grep -iE "(api_key|secret|password|token|credential|private_key|BEGIN (RSA|EC|OPENSSH)|AKIA[0-9A-Z]{16})" \
    && echo "^^^ FOUND IN DANGLING COMMIT: $SHA"
done < "$RECON_DIR/dangling-commits.txt"
```

### 2.4 Full-history secret scanners

Both scanners — different detection rules, run both:

```bash
cd "$REPO_DIR"

# TruffleHog — verified secrets only (high signal)
trufflehog git "file://$REPO_DIR" --json 2>/dev/null \
  | tee "$RECON_DIR/trufflehog-findings.jsonl" \
  | jq -c '{type: .DetectorType, file: .SourceMetadata.Data.Git.file, verified: .Verified, commit: .SourceMetadata.Data.Git.commit}'

# Gitleaks — broader regex coverage
gitleaks detect \
  --source "$REPO_DIR" \
  --log-opts="--all" \
  --report-format json \
  --report-path "$RECON_DIR/gitleaks-findings.json" 2>/dev/null || true
```

> **Any verified secret = immediate finding.** Report to orchestrator NOW
> tagged `credential-exposure`, do not wait for full recon pass.

---

## Phase 3 — Patch Archaeology (Vuln Pattern Mining)

Security commits reveal which bug classes the codebase historically ships.
The same pattern almost always appears in sibling features that weren't patched.

### 3.1 Find security-relevant commits

```bash
cd "$REPO_DIR"

# Cast a wide net — typos, language variants, CVE refs
git log --all --oneline -i --grep="fix\|patch\|security\|cve-\|vuln\|inject\|xss\|sqli\|csrf\|idor\|ssrf\|bypass\|sanitiz\|escape\|auth\|rce\|lfi\|xxe\|deserializ\|overflow\|race.condition\|privilege\|disclosure" \
  > "$RECON_DIR/security-commits.txt"

echo "$(wc -l < "$RECON_DIR/security-commits.txt") security-relevant commits"
cat "$RECON_DIR/security-commits.txt"
```

### 3.2 Inspect each patch — read the BEFORE and AFTER

This is the critical step. For every interesting security commit:

```bash
SHA="<commit-hash>"

# See the full diff — what was the vulnerable code, what's the fix?
git show "$SHA" --stat --patch

# Read the VULNERABLE version of a file (the state BEFORE the fix)
# This shows you what the bug actually looked like, and where to find variants
FILE_PATH="src/controllers/UserController.php"
git show "${SHA}^:${FILE_PATH}" 2>/dev/null   # ^ = parent = pre-fix state

# Compare before/after for a specific file in the commit
git diff "${SHA}^" "$SHA" -- "$FILE_PATH"
```

**What to extract per patch:**
1. **What was wrong** — the exact anti-pattern (e.g., "direct user input into query string")
2. **What directory / layer** — is this pattern specific to one module or widespread?
3. **The fix approach** — partial (just this one instance) or structural (added a wrapper)?
   Partial fixes = almost certainly more unfixed instances elsewhere
4. **Grep target** — synthesize a regex to find the same anti-pattern in current code

### 3.3 Classify each patch and count frequency

| Diff heuristic | Vuln class | Grep target in current tree |
|---|---|---|
| Added `htmlspecialchars()`, `escape()`, `encodeURIComponent()` | XSS | raw output of user-controlled vars |
| String concat → parameterized query / ORM | SQLi | string-concat SQL with `$_GET/$_POST` |
| Added ownership / `user_id` check to a query | IDOR | queries missing WHERE user_id |
| Added SSRF allowlist or URL scheme validation | SSRF | `file_get_contents($url)` / `fetch($param)` |
| Added CSRF token to form | CSRF | forms without token, state-changing GETs |
| Added auth middleware to a route | Auth bypass | routes registered without middleware |
| Added `path.resolve()` / `realpath()` / `basename()` | Path traversal | file ops with user-controlled paths |
| Added rate limiting decorator | Brute force | login / SMS / OTP endpoints without limit |
| Replaced `md5()`/`sha1()` with `bcrypt`/`argon2` | Weak crypto | legacy hash usage |
| Rewrote JWT validation | JWT | manual token decode without library verify |

```bash
# Grep current tree for the anti-pattern found in a patch
# Example: find raw SQL string concatenation still present today
grep -rn "\$.*=.*['\"]SELECT.*\+\s*\$\|\"SELECT.*\"\s*\.\s*\$" \
  "$REPO_DIR/src/" --include="*.php" -l

# Find routes added WITHOUT auth middleware (adapt to the framework)
grep -rn "router\.\(get\|post\|put\|delete\)" "$REPO_DIR" --include="*.js" \
  | grep -v "auth\|middleware\|protect\|require"
```

### 3.4 Commit messages mentioning specific bug references

```bash
# GitHub Security Advisories for this repo
gh api "repos/<org>/<repo>/security-advisories" 2>/dev/null \
  | jq '.[] | {ghsa: .ghsa_id, summary, severity, published_at}' || true

# Closed PRs tagged "security" or with CVE refs
gh search prs --repo "<org>/<repo>" "security CVE vulnerability fix" \
  --state closed --json url,title,mergedAt | head -20

# Open issues that mention vulns (wontfix = highest priority)
gh search issues --repo "<org>/<repo>" \
  "security OR vulnerable OR XSS OR SSRF OR injection OR bypass" \
  --state all --json url,title,state,labels,createdAt | jq '.[:20]' \
  > "$RECON_DIR/issue-leads.json"
```

Closed-as-wontfix security issues = maintainer explicitly declined to patch.
Attack those endpoints first.

---

## Phase 4 — Dependency Audit

```bash
cd "$REPO_DIR"

# OSV-scanner — walks lockfiles, structured JSON output
if command -v osv-scanner >/dev/null 2>&1; then
  osv-scanner --recursive --format json . > "$RECON_DIR/osv-results.json" 2>/dev/null || true
fi

# npm audit (if Node)
[ -f package.json ] && npm audit --json > "$RECON_DIR/npm-audit.json" 2>/dev/null || true

# pip-audit (if Python)
[ -f requirements.txt ] && pip-audit -r requirements.txt -f json \
  > "$RECON_DIR/pip-audit.json" 2>/dev/null || true

# Trivy (broad — vuln + secrets + IaC)
if command -v trivy >/dev/null 2>&1; then
  trivy fs --scanners vuln,secret,misconfig --format json \
    -o "$RECON_DIR/trivy-results.json" . 2>/dev/null || true
fi

# Parse CVEs from OSV output
jq -r '.results[]?.packages[]? | "\(.package.name)@\(.package.version) → \(.vulnerabilities[]?.id)"' \
  "$RECON_DIR/osv-results.json" 2>/dev/null | sort -u \
  > "$RECON_DIR/cve-summary.txt"
cat "$RECON_DIR/cve-summary.txt"
```

---

## Phase 5 — Output: priority.json

Assemble and write the output contract. This is what the hunter reads.

```bash
OUTPUT="$RECON_DIR/priority.json"
```

```json
{
  "target": "<handle>",
  "repo": "<org/repo>",
  "repo_url": "https://github.com/<org>/<repo>",
  "deployed_version": "<tag-or-sha>",
  "scanned_at": "<ISO-8601>",

  "secrets_found": [
    {
      "type": "aws_access_key",
      "location": "commit abc123 : config/deploy.yml",
      "value_preview": "AKIA...XXXX",
      "verified": true,
      "status": "unrotated|rotated|unknown",
      "action": "test against live AWS API immediately"
    }
  ],

  "deleted_files_of_interest": [
    {
      "path": "src/creds/shibboleth/shibbolethconfigfile.h",
      "deleted_in": "b52f9f53",
      "recovered_to": "recon/recovered-shibbolethconfigfile.h",
      "summary": "Contained hardcoded IdP shared secret"
    }
  ],

  "vuln_priority": [
    {
      "rank": 1,
      "vuln_class": "IDOR",
      "frequency": 9,
      "pattern": "DB queries filter by resource ID but not by user_id ownership",
      "affected_dirs": ["src/api/", "controllers/"],
      "confidence": "high",
      "last_patched": "2025-11-02",
      "partial_fix": true,
      "live_grep_hits": 4,
      "grep_command": "grep -rn 'findById\\|WHERE id =' src/ | grep -v user_id",
      "attack_hint": "Enumerate resource IDs as userB and check if userA's data returns"
    }
  ],

  "patch_archaeology": [
    {
      "sha": "abc1234",
      "message": "Fix XSS in comment renderer",
      "date": "2025-08-14",
      "vuln_class": "XSS",
      "pre_fix_pattern": "innerHTML = userInput directly",
      "fix_approach": "partial — only comment.js patched, profile.js not touched",
      "unpatched_siblings": ["src/views/profile.js:142", "src/widgets/bio.js:89"],
      "attack_hint": "Try stored XSS in profile bio field, same sink as comment"
    }
  ],

  "dependency_findings": [
    {
      "package": "lodash",
      "version": "4.17.15",
      "cve": "CVE-2020-8203",
      "severity": "high",
      "exploitable_in_context": "prototype pollution → check for merge/extend calls with user input",
      "source": "osv-scanner"
    }
  ],

  "open_issue_leads": [
    {
      "url": "https://github.com/org/repo/issues/123",
      "title": "XSS in comment rendering not sanitized server-side",
      "state": "closed",
      "wontfix": true,
      "endpoint_hint": "/api/comments POST body.content field"
    }
  ]
}
```

---

## Returning Results to the Hunter

After writing `priority.json`, send it back:

```
FINDINGS SUMMARY for <target>:

Repo: <org/repo> @ <sha>

SECRETS: <N found — list types and locations>
DELETED FILES OF INTEREST: <list paths recovered>
TOP VULN CLASSES (historically patched, look for unpatched siblings):
  1. <class> — <frequency> patches, last: <date>, live grep hits: <N>
  2. ...
PARTIAL FIXES (explicitly test these):
  - <sha>: <description of what wasn't fixed>
DEPENDENCY CVEs: <list high/critical only>
WONTFIX ISSUES: <list endpoints>

Full output: ~/Projects/hunts/<handle>-<YYYYMMDD>/recon/priority.json
```

If repo-recon finds nothing usable (no public source, zero matches):
- Write `{"repo": null, "reason": "no_public_source"}` to `priority.json`
- Return: `repo-recon: no public source found for <target>. Proceeding with black-box only.`
