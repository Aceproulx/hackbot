---
name: repo-recon
description: "Source-code recon subagent for bug bounty targets. Finds and clones the target's public repo, mines commit/PR/advisory history for leaked secrets and vulnerability patterns, runs dependency scanners, and outputs priority.json — a ranked list of vuln classes the target historically ships. Spawn this early in the hunt (after tech fingerprint, before deep testing). Returns: secrets_found, vuln_priority, dependency_findings, open_issue_leads."
---


# Repo Recon

Locates and clones a bug bounty target's open-source codebase, mines its
history for secrets and vulnerability patterns, and hands off structured
`priority.json` to the hunting worker.

**Mode:** Subagent — spawned by the orchestrator in Phase 2, runs in parallel
with the worker's early surface exploration.

**Output:** `~/Projects/hunts/<handle>-<YYYYMMDD>/recon/priority.json`

---

## When to Spawn

Trigger when ANY of these are true:
- Target has a public GitHub org (found via OSINT, generator meta tags, `X-Powered-By`)
- JS bundles reference internal-looking package names (`@target-internal/...`)
- Build logs, SBOMs, or `package-lock.json` publicly accessible
- Target uses a known open-source product (CMS, framework, app)
- `/version`, `/changelog`, `CHANGELOG.md`, or `README` links to a repo

Do NOT spawn when:
- Target is clearly custom/proprietary with no public source
- Repo search returns zero confidence matches (different org, different app)
- Private repo surfaced — **halt immediately**, report to orchestrator, do not clone

**Tool prerequisites (run health-check before spawning):**
```bash
which git osv-scanner trufflehog gitleaks gh 2>/dev/null
# All installed at: ~/.local/bin/ or /usr/local/bin/
# trivy: optional but adds breadth
```

---

## Phase 1 — Find & Clone

### 1.1 Identify the repo
Search in order:
```bash
# GitHub search by org name / product name
gh search repos "<target_name>" --json fullName,description,stargazersCount | head -10

# Check the target app itself
curl -sk "https://<target>" -I | grep -i "x-powered-by\|server\|generator"
curl -sk "https://<target>/version" 2>/dev/null
curl -sk "https://<target>/changelog" 2>/dev/null
```
Prefer org-specific forks (`github.com/{target-org}/...`) over upstream —
forks carry the real deployment patches.

### 1.2 Fingerprint deployed version
```bash
# From response headers, /version endpoint, JS bundle names, or CHANGELOG
VERSION=$(curl -sk "https://<target>/api/version" | jq -r '.version // empty')
```

### 1.3 Clone at deployed version
```bash
RECON_DIR=~/Projects/hunts/<handle>-<YYYYMMDD>/recon
mkdir -p "$RECON_DIR"

git clone --depth 1 <repo_url> "$RECON_DIR/repo"
cd "$RECON_DIR/repo"
git checkout <version_tag_or_commit>  # pin to deployed version
```

Cache check first — if `$RECON_DIR/repo/.git` exists, reuse it.

---

## Phase 2 — Secret Sweep (deleted/dangling commits)

Cheap and high-value — do before history mining.

```bash
cd "$RECON_DIR/repo"

# Fetch full history for orphan sweep
git fetch --unshallow 2>/dev/null || true

# Find dangling/orphaned commits
git fsck --unreachable --no-reflogs 2>/dev/null | grep commit | awk '{print $3}' | while read sha; do
  git show "$sha" 2>/dev/null | grep -iE "api_key|secret|password|token|credential|private_key" && \
    echo "LEAK in dangling commit: $sha"
done

# Full-history secret scan (primary)
trufflehog git "file://$RECON_DIR/repo" --json 2>/dev/null \
  | jq '{type: .DetectorType, location: .SourceMetadata.Data.Git.file, verified: .Verified}' \
  >> "$RECON_DIR/trufflehog-findings.jsonl"

# Backup with gitleaks
gitleaks detect --source "$RECON_DIR/repo" --log-opts="--all" \
  --report-format json --report-path "$RECON_DIR/gitleaks-findings.json" 2>/dev/null || true
```

**Any secret found = immediate standalone finding.** Report to orchestrator
right away tagged `credential-exposure`, don't wait for full pass:
```bash
hackbot-dashboard add \
  --program "<handle>" \
  --title "Leaked <type> in git history — <repo>@<sha>" \
  --severity "Critical" --status "confirmed" --bounty 5000 \
  --evidence "gitleaks/trufflehog" --url "<repo_url>/commit/<sha>"
hackbot-notify bug "<handle>" "Leaked <type> in git history" "Critical" "5000"
```

---

## Phase 3 — Vulnerability Pattern Mining

### 3.1 Mine security-relevant commits
```bash
cd "$RECON_DIR/repo"
git log --all --oneline \
  --grep="fix\|security\|CVE\|XSS\|SQLi\|auth\|sanitiz\|escape\|vuln\|injection\|bypass\|idor\|ssrf" \
  -i > "$RECON_DIR/security-commits.txt"

wc -l "$RECON_DIR/security-commits.txt"
cat "$RECON_DIR/security-commits.txt" | head -30
```

Also check `CHANGELOG.md`, `SECURITY.md`, GitHub Security Advisories:
```bash
gh api "repos/<org>/<repo>/security-advisories" 2>/dev/null | jq '.[].summary' || true
```

### 3.2 Classify each patch into vuln classes
For each security commit, inspect the diff:
```bash
git show <sha> --stat --patch | head -100
```

Tag with CWE-style class using diff heuristics:
| Diff pattern | Class |
|---|---|
| Added `htmlspecialchars()`, `escape()`, `encodeURIComponent()` | XSS |
| String concat → parameterized query | SQLi |
| Added ownership/`user_id` check | IDOR |
| Added SSRF allowlist or URL validation | SSRF |
| Added CSRF token check | CSRF |
| Added auth middleware to a route | Auth bypass |
| Added `path.resolve()` or `realpath()` | Path traversal |
| Added rate limiting | Brute force |

Tally frequency per class. Find the **anti-pattern** — e.g. "no centralized
output encoding" or "auth reimplemented per route" — not just the count.
Grep the **current** tree for unpatched instances of the same pattern.

### 3.3 Dependency vulnerability scan
```bash
cd "$RECON_DIR/repo"

# Primary — walks lockfiles directly, low noise
osv-scanner --lockfile=package-lock.json --format json \
  > "$RECON_DIR/osv-results.json" 2>/dev/null || \
osv-scanner --recursive --format json . > "$RECON_DIR/osv-results.json" 2>/dev/null || true

# Breadth pass (vuln + secrets + IaC)
trivy fs --scanners vuln,secret,misconfig --format json \
  -o "$RECON_DIR/trivy-results.json" . 2>/dev/null || true
```

### 3.4 Open issue sweep
```bash
gh search issues --repo "<org>/<repo>" \
  "security OR vulnerable OR XSS OR SSRF OR injection" \
  --state all --json url,title,state,labels | head -20 \
  > "$RECON_DIR/issue-leads.json"
```
Closed-as-wontfix security issues are highest priority — maintainer explicitly
declined to patch.

---

## Output Contract

Write `priority.json` and return it as your final message:

```bash
OUTPUT="$RECON_DIR/priority.json"
```

```json
{
  "target": "<handle>",
  "repo": "<org/repo>",
  "commit": "<sha>",
  "scanned_at": "<ISO>",
  "secrets_found": [
    {
      "type": "aws_access_key",
      "location": "commit abc123:config/deploy.yml",
      "status": "unrotated|rotated|unknown"
    }
  ],
  "vuln_priority": [
    {
      "rank": 1,
      "vuln_class": "XSS",
      "frequency": 7,
      "pattern": "user input rendered via {{raw}} template without escaping",
      "affected_dirs": ["src/views/", "plugins/comments/"],
      "confidence": "high",
      "last_patched": "2025-11-02",
      "live_grep_hits": 3
    }
  ],
  "dependency_findings": [
    {
      "package": "lodash",
      "version": "4.17.15",
      "cve": "CVE-2020-8203",
      "severity": "high",
      "source": ["osv-scanner"]
    }
  ],
  "open_issue_leads": [
    {
      "url": "https://github.com/org/repo/issues/123",
      "title": "XSS in comment rendering — not fixed",
      "state": "closed",
      "wontfix": true
    }
  ]
}
```

---

## Orchestrator Integration

### In Phase 2 (pre-hunt recon), after richness scoring:
```bash
# Spawn repo-recon in parallel — don't block the hunt on it
# Pass output to worker brief once it returns

# In AI mode: spawn @repo-recon subagent with:
RECON_INPUT="TARGET: <handle>
REPO_HINT: <any version/tech fingerprint found>
OUTPUT_DIR: ~/Projects/hunts/<handle>-<YYYYMMDD>/recon/"

# Worker brief includes repo-recon results:
PRIORITY_JSON=$(cat ~/Projects/hunts/<handle>-<YYYYMMDD>/recon/priority.json 2>/dev/null || echo "{}")
```

### Worker uses priority.json like this:
```
1. Attack top-ranked vuln_priority class FIRST — it's the target's historical weak spot
2. Treat every secrets_found entry as immediate live-app test (leaked key → try it)
3. dependency_findings CVEs → find the vulnerable code path, confirm exploitability
4. open_issue_leads → go straight to those endpoints
```

### If repo-recon finds nothing usable (private repo, no source):
Don't stall the hunt. Proceed with standard exploration.
Log `repo-recon: no source found` to `interesting.md` and move on.
