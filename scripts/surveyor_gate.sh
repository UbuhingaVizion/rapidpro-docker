#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# surveyor_gate.sh
#
# Acceptance gate for the "surveyor-modern" RapidPro stack.
#
# Verifies that a running stack still supports the RapidPro Surveyor (Android)
# app end-to-end, at the HTTP layer:
#   1. authenticate  -> role=S returns surveyor org tokens
#   2. surveyor API v2 endpoints respond (org, fields, groups, flows, boundaries)
#   3. survey flows exist (type=survey) and definitions are fetchable (spec <=13.x)
#   4. Mailroom still serves POST /mr/surveyor/submit (NOT 404)
#
# Usage:
#   export RAPIDPRO_EMAIL=surveyor@example.org
#   export RAPIDPRO_PASSWORD=********
#   export BASE_URL=http://localhost            # optional (default below)
#   ./scripts/surveyor_gate.sh
#
# Exit code 0 = gate passed. Non-zero = a requirement is missing.
# ----------------------------------------------------------------------------
set -u

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${RAPIDPRO_EMAIL:-}"
PASSWORD="${RAPIDPRO_PASSWORD:-}"
FAILED=0

say()  { printf '\n== %s\n' "$*"; }
pass() { printf '   OK   %s\n' "$*"; }
fail() { printf '   FAIL %s\n' "$*"; FAILED=1; }

if [ -z "$EMAIL" ] || [ -z "$PASSWORD" ]; then
  echo "Missing credentials: set RAPIDPRO_EMAIL and RAPIDPRO_PASSWORD" >&2
  exit 2
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required" >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for JSON parsing" >&2
  exit 2
fi

say "1) Authenticating with role=S at $BASE_URL"
AUTH_JSON=$(curl -sS -X POST "$BASE_URL/api/v2/authenticate" \
  --data-urlencode "username=$EMAIL" \
  --data-urlencode "password=$PASSWORD" \
  --data-urlencode "role=S")
TOKEN=$(printf '%s' "$AUTH_JSON" | python3 -c \
  "import sys,json
try:
    d=json.load(sys.stdin)
    ts=d.get('tokens') or []
    print(ts[0]['token'] if ts else '')
except Exception:
    print('')")
if [ -z "$TOKEN" ]; then
  fail "authenticate role=S returned no surveyor token (is the account a Surveyor?)"
  echo "   raw response: $AUTH_JSON" >&2
else
  pass "got surveyor token"
fi

if [ -z "$TOKEN" ]; then
  echo; echo "GATE FAILED - no surveyor access."; exit 1
fi

AUTH="Authorization: Token $TOKEN"

say "2) Surveyor API v2 endpoints"
for path in org.json fields.json groups.json flows.json?type=survey\&archived=false boundaries.json; do
  code=$(curl -sS -o /dev/null -w "%{http_code}" -H "$AUTH" "$BASE_URL/api/v2/$path")
  if [ "$code" = "200" ]; then
    pass "/api/v2/$path -> 200"
  else
    fail "/api/v2/$path -> $code (expected 200)"
  fi
done

say "3) Survey flows present and exportable"
FLOWS=$(curl -sS -H "$AUTH" "$BASE_URL/api/v2/flows.json?type=survey&archived=false")
FLOW_UUID=$(printf '%s' "$FLOWS" | python3 -c \
  "import sys,json
try:
    d=json.load(sys.stdin); rs=d.get('results') or []
    print(rs[0]['uuid'] if rs else '')
except Exception:
    print('')")
if [ -z "$FLOW_UUID" ]; then
  fail "no surveyor flows found (create/enable a flow of type survey and refresh)"
else
  pass "survey flow present: $FLOW_UUID"
  DEFS=$(curl -sS -H "$AUTH" "$BASE_URL/api/v2/definitions.json?flow=$FLOW_UUID&dependencies=none")
  SPEC=$(printf '%s' "$DEFS" | python3 -c \
    "import sys,json
try:
    d=json.load(sys.stdin); fs=d.get('flows') or []
    print(fs[0].get('spec_version','?') if fs else 'none')
except Exception:
    print('?')")
  case "$SPEC" in
    13.*|11.*) pass "flow spec_version $SPEC (supported)" ;;
    *) fail "flow spec_version '$SPEC' not known-supported (keep <=13.x)" ;;
  esac
fi

say "4) Mailroom surveyor submit endpoint"
CODE=$(curl -sS -o /dev/null -w "%{http_code}" -X POST \
  -H "$AUTH" -H "Content-Type: application/json" -d '{}' \
  "$BASE_URL/mr/surveyor/submit")
if [ "$CODE" = "404" ]; then
  fail "/mr/surveyor/submit -> 404 (mailroom has no surveyor support - upgrade mailroom!)"
else
  pass "/mr/surveyor/submit present (responded $CODE; 400/401/403 expected for empty payload)"
fi

echo
if [ "$FAILED" = "0" ]; then
  echo "GATE PASSED - stack is Surveyor-ready."
  exit 0
else
  echo "GATE FAILED - see failures above."
  exit 1
fi
