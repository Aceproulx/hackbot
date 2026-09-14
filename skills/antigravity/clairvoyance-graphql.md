---
name: clairvoyance-graphql
description: "GraphQL schema reconstruction when introspection is disabled. Uses clairvoyance (field-suggestion error mining) to brute-force the full schema without __schema access. Covers: introspection probe, field suggestion confirmation, clairvoyance run, depth/complexity WAF bypass, manual curl fallback, and schema-to-attack-surface mapping."
---

# Clairvoyance — GraphQL Schema Reconstruction Without Introspection

When a GraphQL endpoint has introspection disabled, it often still leaks the
schema through **field suggestion errors** — server responses like
`"Did you mean: characters?"` when you send an invalid field name.
Clairvoyance exploits this to brute-force the complete schema without ever
touching `__schema`.

---

## Step 0 — Probe: Introspection On or Off?

Always check both standard introspection AND field suggestions before deciding which path to take.

```bash
TARGET="https://rickandmortyapi.com/graphql"
PROXY=""   # set to "-x http://127.0.0.1:8080" to log through Caido

# Test 1: Standard introspection
curl -sk $PROXY -X POST "$TARGET" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ __schema { queryType { name } } }"}' | jq -r '
    if .data then "INTROSPECTION: ON"
    elif (.errors[]?.message | test("introspection";"i")) then "INTROSPECTION: DISABLED"
    else "INTROSPECTION: UNKNOWN — \(.errors[]?.message)"
    end'

# Test 2: Field suggestion probe (clairvoyance prerequisite)
curl -sk $PROXY -X POST "$TARGET" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ zzz_doesnotexist }"}' | jq -r '
    .errors[]?.message //
    "no errors returned"'
# ✅ Good: "Cannot query field \"zzz_doesnotexist\" on type \"Query\". Did you mean..."
# ❌ Dead end: generic "Unknown field" with no suggestions → clairvoyance won't work
```

### Decision tree

| Introspection | Field suggestions | Path |
|---|---|---|
| ON | — | Use standard introspection (see Appendix A) |
| OFF | YES (suggests field names) | ✅ Use clairvoyance |
| OFF | NO (generic error only) | Manual JS-bundle mining + `__typename` probes |
| Depth-limited | partial | Split queries per type (see Appendix B) |

---

## Step 1 — Install & Verify

```bash
pip3 install clairvoyance

# Verify
python3 -m clairvoyance --help

# Verify graphql-cop too (misconfig scanner)
pip3 install graphql-cop
```

---

## Step 2 — Run Clairvoyance

### Basic run (no auth)

```bash
TARGET="https://target.com/graphql"
OUTPUT="schema.json"

python3 -m clairvoyance \
  "$TARGET" \
  -o "$OUTPUT" \
  --progress
```

### With auth headers (most real targets)

```bash
python3 -m clairvoyance \
  "$TARGET" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Cookie: session=abc123" \
  -o "$OUTPUT" \
  --progress
```

### Through Caido proxy (recommended — logs every request in history)

```bash
python3 -m clairvoyance \
  "$TARGET" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -x http://127.0.0.1:8080 \
  -k \
  -o "$OUTPUT" \
  --progress
```

> **`-k`** disables SSL verification — required when Caido intercepts HTTPS.

### Speed profiles

```bash
# Fast (more concurrent workers — use first, watch for rate limiting)
python3 -m clairvoyance "$TARGET" -p fast -c 10 -o schema.json --progress

# Slow (rate-limit safe — if the fast run starts getting 429s)
python3 -m clairvoyance "$TARGET" -p slow -c 2 -o schema.json --progress

# Custom concurrency
python3 -m clairvoyance "$TARGET" -c 5 -o schema.json --progress
```

### With a custom wordlist (higher coverage than built-in)

The built-in wordlist (`~/.local/lib/python3.*/site-packages/clairvoyance/wordlist.txt`)
has ~10k English words. For API-specific terms, combine it with a GraphQL-focused
wordlist:

```bash
# GraphQL-specific wordlist (camelCase identifiers common in APIs)
cat > /tmp/graphql-words.txt << 'EOF'
id
userId
user
users
viewer
me
account
accounts
profile
profiles
email
username
password
token
role
roles
permission
permissions
admin
organization
organizations
org
team
teams
member
members
group
groups
post
posts
comment
comments
message
messages
chat
notification
notifications
subscription
subscriptions
order
orders
product
products
item
items
invoice
invoices
payment
payments
billing
webhook
webhooks
event
events
log
logs
audit
session
sessions
node
nodes
edge
edges
cursor
pageInfo
first
last
after
before
filter
sort
search
query
mutation
create
update
delete
remove
add
get
list
fetch
find
count
total
page
offset
limit
EOF

# Merge with built-in wordlist
BUILTIN=$(python3 -c "import clairvoyance, os; print(os.path.dirname(clairvoyance.__file__))")/wordlist.txt
cat "$BUILTIN" /tmp/graphql-words.txt | sort -u > /tmp/combined-wordlist.txt

python3 -m clairvoyance \
  "$TARGET" \
  -w /tmp/combined-wordlist.txt \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -x http://127.0.0.1:8080 \
  -k \
  -o schema.json \
  --progress \
  -p fast
```

### Incremental run (supplement existing schema)

If clairvoyance partially ran and produced some output, continue from where it left off:

```bash
python3 -m clairvoyance \
  "$TARGET" \
  -i existing-schema.json \
  -o schema.json \
  --progress
```

---

## Step 3 — Rick & Morty API Example

The Rick & Morty API (`https://rickandmortyapi.com/graphql`) has introspection
**enabled** but applies a **query depth limit** (returns
`"Query depth limit exceeded"` on nested queries). This is a useful test case
for the depth-limit bypass pattern.

### When introspection IS on but depth-limited

```bash
TARGET="https://rickandmortyapi.com/graphql"

# Step 1: Get type names (shallow — works within depth limit)
curl -s -X POST "$TARGET" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ __schema { types { name kind } } }"}' \
  | jq -r '.data.__schema.types[] | select(.kind == "OBJECT" and (.name | startswith("__") | not)) | .name' \
  > /tmp/type-names.txt

cat /tmp/type-names.txt
# Output: Query, Character, Location, Episode, Characters, Info, Locations, Episodes

# Step 2: Get fields per type (one query per type — avoids depth limit)
while IFS= read -r TYPE; do
  echo "=== $TYPE ===" 
  curl -s -X POST "$TARGET" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"{ __type(name: \\\"$TYPE\\\") { fields { name type { name kind ofType { name kind } } args { name type { name kind } } } } }\"}" \
    | jq -r --arg t "$TYPE" \
      '.data.__type.fields[] | "  \(.name): \(.type.name // .type.ofType.name // "[\(.type.kind)]")"'
done < /tmp/type-names.txt
```

### Full schema.json output (depth-limited target workaround)

```bash
TARGET="https://rickandmortyapi.com/graphql"
OUTPUT="schema.json"

# Fetch all types
TYPES=$(curl -s -X POST "$TARGET" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ __schema { types { name kind } } }"}' \
  | jq -r '.data.__schema.types[] | select(.kind == "OBJECT" and (.name | startswith("__") | not)) | .name')

# Build schema JSON from per-type queries
echo '{"data":{"__schema":{"types":[' > "$OUTPUT.tmp"
FIRST=1
for TYPE in $TYPES; do
  FIELDS=$(curl -s -X POST "$TARGET" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"{ __type(name: \\\"$TYPE\\\") { name kind fields(includeDeprecated:true) { name isDeprecated args { name description defaultValue type { name kind ofType { name kind } } } type { name kind ofType { name kind } } } } }\"}" \
    | jq '.data.__type')
  [ "$FIRST" -eq 0 ] && printf ',' >> "$OUTPUT.tmp"
  printf '%s' "$FIELDS" >> "$OUTPUT.tmp"
  FIRST=0
done
echo ']}}}'  >> "$OUTPUT.tmp"
mv "$OUTPUT.tmp" "$OUTPUT"
echo "Schema written to $OUTPUT"
jq '.data.__schema.types | length' "$OUTPUT"
```

---

## Step 4 — When Introspection Is Truly Disabled (Clairvoyance Target)

```bash
TARGET="https://target-with-no-introspection.com/graphql"

# Confirm field suggestions work first
curl -s -X POST "$TARGET" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"query":"{ zzz }"}' | jq '.errors[].message'
# Must show "Did you mean X?" — otherwise clairvoyance won't work

# If suggestions work, run clairvoyance
python3 -m clairvoyance \
  "$TARGET" \
  -H "Authorization: Bearer TOKEN" \
  -x http://127.0.0.1:8080 \
  -k \
  -w /tmp/combined-wordlist.txt \
  -o schema.json \
  -p fast \
  -c 8 \
  --progress
```

### Bypasses for suggestion-suppressed endpoints

Some servers disable field suggestions alongside introspection. Fallbacks:

```bash
# 1. Try alternate HTTP methods (GET with query param)
curl -sk "$TARGET?query={ __typename }" | jq .

# 2. Try multipart body
curl -sk -X POST "$TARGET" \
  -F 'operations={"query":"{ __typename }"}' \
  -F 'map={}' | jq .

# 3. Content-type variation
curl -sk -X POST "$TARGET" \
  -H "Content-Type: application/graphql" \
  -d '{ __typename }' | jq .

# 4. Try field suggestion with different type contexts
curl -sk -X POST "$TARGET" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation { zzz }"}' | jq '.errors[].message'
# Might suggest mutation fields even if query suggestions are suppressed

# 5. Mine JS bundles for hardcoded query strings
# (jxscout already running — check its output)
grep -rE '(query|mutation|subscription)\s+\w+\s*[({]|gql`|graphql`' \
  ~/jxscout/<target>/ 2>/dev/null | head -30

# 6. Check Caido HTTP history for POST bodies with query= param
# list_requests with HTTPQL: method == "POST" AND body contains "query"
```

---

## Step 5 — Read schema.json and Map Attack Surface

```bash
OUTPUT="schema.json"

# Show all query root fields
jq -r '
  .data.__schema.types[]
  | select(.name == "Query")
  | .fields[]
  | "\(.name)(\(.args | map(.name) | join(", ")))"
' "$OUTPUT" 2>/dev/null \
|| jq -r '
  .types[]
  | select(.name == "Query")
  | .fields[]
  | "\(.name)(\(.args | map(.name) | join(", ")))"
' "$OUTPUT"

# Show all mutations (highest priority — these change state)
jq -r '
  .data.__schema.types[]
  | select(.name == "Mutation")
  | .fields[]
  | "\(.name)(\(.args | map(.name) | join(", ")))"
' "$OUTPUT" 2>/dev/null || echo "No mutations found"

# Find fields that take an ID argument (IDOR surface)
jq -r '
  .data.__schema.types[]
  | select(.kind == "OBJECT")
  | .name as $type
  | .fields[]?
  | select(.args[]?.name == "id")
  | "[\($type)] \(.name)(id)"
' "$OUTPUT" 2>/dev/null

# Find fields that return sensitive type names
jq -r '
  .data.__schema.types[]
  | select(.kind == "OBJECT")
  | .fields[]?
  | select(.name | test("password|token|secret|key|email|phone|ssn|credit|billing|admin";"i"))
  | .name
' "$OUTPUT" 2>/dev/null
```

---

## Step 6 — graphql-cop Misconfig Scan

```bash
# graphql-cop is a script, not a module — find it and run it
GCOP=$(python3 -c "import graphql_cop, os; print(os.path.dirname(graphql_cop.__file__))")

python3 "$GCOP/app.py" -t "$TARGET" -H "Authorization: Bearer TOKEN" 2>/dev/null \
  || python3 -c "
import sys; sys.argv = ['graphql-cop','-t','$TARGET']
from graphql_cop import app; app.main()
" 2>/dev/null \
  || echo "graphql-cop: try: python3 \$(find ~/.local -name 'app.py' -path '*graphql_cop*') -t $TARGET"
```

graphql-cop checks for:
- Introspection enabled
- Field suggestions enabled
- Batch query support (amplification)
- Aliases allowed (alias-batching DoS)
- No depth/complexity limits
- GET-based mutations
- No CSRF protections

---

## Appendix A — Standard Introspection (When ON)

```bash
TARGET="https://rickandmortyapi.com/graphql"

# Full schema in one query (works if no depth limit)
curl -s -X POST "$TARGET" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ __schema { queryType { name } mutationType { name } subscriptionType { name } types { name kind description fields(includeDeprecated: true) { name description isDeprecated args { name description defaultValue type { name kind ofType { name kind } } } type { name kind ofType { name kind } } } inputFields { name type { name kind ofType { name kind } } } enumValues(includeDeprecated: true) { name isDeprecated } } } }"
  }' -o schema.json

jq '.data.__schema.types | length' schema.json
```

---

## Appendix B — WAF / Depth-Limit Bypasses for Introspection

```bash
# Alias the __schema field (bypasses naive keyword filters)
curl -s -X POST "$TARGET" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ s: __schema { t: types { n: name k: kind } } }"}' | jq .

# Fragment to avoid keyword in the query body
curl -s -X POST "$TARGET" \
  -H "Content-Type: application/json" \
  -d '{"query":"fragment F on __Schema { types { name kind } } { s: __schema { ...F } }"}' | jq .

# GET introspection (some WAFs only block POST)
curl -sk -G "$TARGET" \
  --data-urlencode 'query={ __schema { types { name kind } } }' | jq .

# Split over multiple requests (depth-limit workaround — see Step 3)
# Query shallow first (__schema → types → name/kind), then __type(name:) per type
```

---

## Quick Reference Card

```
# Check: is introspection on?
curl -s -X POST $URL -H "Content-Type: application/json" \
  -d '{"query":"{ __schema { queryType { name } } }"}' | jq .

# Check: are field suggestions on? (clairvoyance prerequisite)
curl -s -X POST $URL -H "Content-Type: application/json" \
  -d '{"query":"{ zzz }"}' | jq '.errors[].message'

# Run clairvoyance (no auth, through Caido)
python3 -m clairvoyance $URL -x http://127.0.0.1:8080 -k -o schema.json --progress

# Run clairvoyance (with auth, fast, custom wordlist)
python3 -m clairvoyance $URL \
  -H "Authorization: Bearer TOKEN" \
  -x http://127.0.0.1:8080 -k \
  -w /tmp/combined-wordlist.txt \
  -p fast -c 8 \
  -o schema.json --progress

# Incremental (resume / supplement existing output)
python3 -m clairvoyance $URL -i schema.json -o schema.json --progress

# List query root fields from schema.json
jq -r '.data.__schema.types[] | select(.name=="Query") | .fields[].name' schema.json

# List mutations from schema.json
jq -r '.data.__schema.types[] | select(.name=="Mutation") | .fields[].name' schema.json
```
