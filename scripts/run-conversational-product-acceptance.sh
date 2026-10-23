#!/usr/bin/env bash
# One reproducible local/CI entrypoint. Offline contracts are not physical voice acceptance.
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && python -m pytest -q -p tests.offline_network_guard \
 tests/services/test_react_bounded_loop_dispatch_gate.py \
 tests/services/test_cancelled_plan_observation_reconciliation.py \
 tests/services/test_execution_context_kernel_projection.py \
 tests/services/test_hubspot_count_incident.py \
 tests/services/pipecat_voice/test_echo_correction_guard.py \
 tests/services/pipecat_voice/test_cognitive_llm_tool_narration.py \
 tests/marketplace/test_marketplace3_publish_gate.py \
 tests/marketplace/test_marketplace3_certification_store.py \
 tests/marketplace/test_marketplace3_production_evidence.py)
(cd apps/web && node node_modules/vitest/vitest.mjs run \
 __tests__/lib/gravitre-ai-runtime-state.test.ts \
 __tests__/lib/lifecycle-envelope.test.ts \
 __tests__/lib/consolidation-verification-boundary.test.ts \
 __tests__/lib/voice-audio-output.test.ts)
node scripts/check-gravitre-brand.mjs
node scripts/check-user-facing-status-leak.mjs
node scripts/check-chat-surface-drift.mjs
