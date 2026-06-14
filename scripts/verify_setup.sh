#!/usr/bin/env bash
# Verify local AityUahn forge is running and optional cloud SaaS is healthy.
set -euo pipefail

FORGE_URL="${FORGE_URL:-http://127.0.0.1:8765}"
SAAS_URL="${SAAS_URL:-}"
FAIL=0

echo "=== AityUahn setup verification ==="
echo "Forge URL: $FORGE_URL"

if command -v aityuahn >/dev/null 2>&1; then
  echo "CLI: $(aityuahn version 2>/dev/null || echo 'unknown')"
else
  echo "CLI: not in PATH (activate venv or reinstall)"
  FAIL=$((FAIL + 1))
fi

forge_health="$FORGE_URL/api/health"
if body="$(curl -fsS "$forge_health" 2>/dev/null)"; then
  echo "Forge health: OK"
  echo "$body" | python -m json.tool 2>/dev/null || echo "$body"
  if ! echo "$body" | grep -q '"role".*"forge"'; then
    echo "ERROR: expected role=forge at $FORGE_URL"
    FAIL=$((FAIL + 1))
  fi
else
  echo "ERROR: forge not reachable at $forge_health"
  echo "       Start: aityuahn serve --demo"
  FAIL=$((FAIL + 1))
fi

if [ -n "$SAAS_URL" ]; then
  SAAS_URL="${SAAS_URL%/}"
  saas_health="$SAAS_URL/api/health"
  echo ""
  echo "SaaS URL: $SAAS_URL"
  if body="$(curl -fsS "$saas_health" 2>/dev/null)"; then
    echo "$body" | python -m json.tool 2>/dev/null || echo "$body"
    if echo "$body" | grep -q '"ok".*false'; then
      echo "ERROR: SaaS health ok=false — check Vercel env (DATABASE_URL, JWT secret)"
      FAIL=$((FAIL + 1))
    fi
  else
    echo "ERROR: SaaS not reachable at $saas_health"
    FAIL=$((FAIL + 1))
  fi
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "All checks passed."
  exit 0
fi
echo "$FAIL check(s) failed."
exit 1
