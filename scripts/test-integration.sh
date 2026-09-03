#!/bin/bash
# Gravitre Integration Test
# Usage: BACKEND_URL=http://localhost:8000 bash scripts/test-integration.sh

set -e
BACKEND_URL=${BACKEND_URL:-http://localhost:8000}
# Every curl below is bounded. None of them were, and this script runs in a CI
# step that had no timeout either, so a single unanswered request could hang the
# job indefinitely. Measured locally: each of these returns in ~1.2s.
MAXT=30
echo "Testing backend at $BACKEND_URL"

# 1. Health check
echo "→ Health check..."
curl -sf --max-time $MAXT "$BACKEND_URL/health" | grep -qE '"status"\s*:\s*"(ok|degraded)"' && \
  echo "✅ Backend healthy" || \
  (echo "❌ Backend unreachable" && exit 1)

# 2. Auth check (expect 401, not 000/connection refused)
echo "→ Auth check..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time $MAXT \
  -X POST "$BACKEND_URL/api/assistant/chat" \
  -H "Content-Type: application/json" \
  -d '{"messages":[],"org_id":"test"}')
[ "$STATUS" = "401" ] && \
  echo "✅ Auth gate working (got 401)" || \
  echo "⚠️  Expected 401, got $STATUS"

# 4. Marketplace browse auth gate
echo "→ Marketplace browse auth gate..."
MKT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time $MAXT \
  "$BACKEND_URL/api/marketplace/assets?limit=1")
[ "$MKT_STATUS" = "401" ] && \
  echo "✅ Marketplace assets auth gate working (got 401)" || \
  echo "⚠️  Expected 401 for marketplace/assets, got $MKT_STATUS"

# 3. Killswitch check (informational)
echo "→ Checking killswitch status..."
curl -sf --max-time $MAXT "$BACKEND_URL/health" | python3 -c \
  "import sys,json; h=json.load(sys.stdin); \
   print('✅ AI enabled' if not h.get('ai_disabled') \
   else '⚠️  AI killswitch is ON')" 2>/dev/null || \
  echo "  (health endpoint doesn't report AI status — ok)"

echo ""
echo "Integration test complete."
echo "To test with auth, set JWT and run:"
echo "  curl -X POST $BACKEND_URL/api/assistant/chat \\"
echo "    -H 'Authorization: Bearer <jwt>' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}],\"org_id\":\"<org-id>\"}'"
