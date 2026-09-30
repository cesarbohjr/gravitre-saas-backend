#!/usr/bin/env bash
set -euo pipefail

echo "== Gravitre conversational product acceptance =="

echo "[1/4] Backend action + dialogue semantics"
cd backend
python -m pytest -q \
  tests/services/test_chat_connector_execution.py::test_new_write_same_action_after_prior_success_stages_fresh_approval \
  tests/test_response_composer.py::test_bare_lifecycle_words_are_detected_as_system_state_only \
  tests/test_response_composer.py::test_stopped_reply_never_surfaces_bare_system_state \
  tests/test_response_composer.py::test_bare_failed_canned_reply_is_composed_into_natural_language \
  tests/services/test_pending_reply_classifier.py::test_pending_copy_humanizes_raw_catalog_action_key

echo "[2/4] Voice lifecycle + synthesis contracts"
python -m pytest -q \
  tests/services/pipecat_voice/test_cognitive_llm_text_streaming.py::test_completed_pipecat_turn_emits_explicit_browser_completion_marker \
  tests/services/pipecat_voice/test_voice_natural_prosody_contract.py \
  tests/services/pipecat_voice/test_pipecat_voice_tts_model_guard.py

cd ../apps/web
echo "[3/4] Web state truth + voice delivery ownership"
pnpm exec vitest run \
  __tests__/gravitre/ai-mission-spine.test.ts \
  __tests__/lib/gravitre-ai-runtime-state.test.ts \
  __tests__/lib/voice-audio-output.test.ts

cd ../..
echo "[4/4] Static conversational surface guards"
node scripts/check-user-facing-status-leak.mjs
node scripts/check-chat-surface-drift.mjs

echo "CONVERSATIONAL_PRODUCT_ACCEPTANCE=PASS"
