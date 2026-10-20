# Phase 1: perception, understanding and model readiness

Scope: repository baseline `ee947c793`, plus local artifact-readiness correction
`0b184a4ca`. This phase audits existing implementations; it does not replace
models, alter production flags, promote models or certify live audio quality.

The original branch and commit were recovered intact in this workspace. A push
was rejected by automatic approval review; no successful publication is claimed.

## Findings

| Area | Evidence | Assessment and next acceptance requirement |
| --- | --- | --- |
| Shared text/voice reasoning | `pipecat_voice/cognitive_llm.py` delegates to agent intelligence; `text_voice_semantic_parity.py` compares canonical task state | Existing shared architecture. Prove equivalent requests use equivalent permissions, context, approval state and tools in authenticated runtime traces. Transcript parity is not microphone-to-speaker parity. |
| Intent understanding | `task_classifier.py`, `operator_task_intent.py`, task execution parity tests | Existing question/task/correction routing and guarded spoken shortcuts. Validate noisy transcripts, ambiguous recipients and correction-after-approval cases live before certifying accuracy. |
| Context and sentiment | `agent_intelligence.py` full path invokes contextual understanding and sentiment analysis | Implemented, but not universal: `spoken_lite_path or _compiled_read_ingress` sets sentiment adaptation to none and uses default understanding. Measure shortcuts against frustrated small talk and connector reads before changing latency policy. |
| Acoustic perception | `voice_acoustic_signal.py`; only discovered scheduler caller is `routers/voice.py:post_stt` with `analyze_acoustic=False` default | Opt-in uploaded-audio analysis. No scheduler caller found in live Pipecat pipeline. Current extractor uses energy and zero crossings, not a validated speech-emotion model. Prove audio format handling and realtime integration before treating it as conversational emotional perception. |
| Acoustic confidence | `extract_acoustic_features` returns fixed literature accuracy bands and their midpoint | No local evaluation evidence inspected justifies applying these bands to this heuristic. Do not treat these numbers as calibrated accuracy for Gravitre. Require labeled validation or remove numerical accuracy claims in a subsequent correction. |
| Recognition and turns | `pipecat_voice/stt_factory.py` defaults Flux, supports Nova/OpenAI fallback and non-English routing | Code configuration verified only. Native turn detection is not proof of native speech-to-speech reasoning. Actual provider, model and fallback must come from session metadata. |
| Voice-model restriction | `pipecat_voice/pipeline.py:resolve_live_tts_voice_and_model` overrides v3 to Flash v2.5 | Confirmed code restriction. No evidence in this pass establishes the latency/quality tradeoff; compare configurations before changing production. |
| Expressive delivery | `pipecat_voice/voice_delivery_tags.py` validates then strips delivery tags | Tags currently support observability, not a synthesis-control path. Existing tags must not be described as working expressive speech controls. Keep validation against injection when testing future rendering. |
| ML readiness | `model_catalog.py:get_org_model_status`; companion 14-model audit | Corrected locally: deployed registry metadata alone no longer sets artifact loaded. Actual loading still does not prove inference correctness, quality or adaptive improvement. |

## Local validation

First batch: 61 tests passed using:

```sh
python -m pytest tests/ml/test_catalog_artifact_verification.py tests/ml/test_registry_inference.py tests/services/test_task_classifier_honesty.py tests/services/test_text_voice_task_execution_parity.py tests/services/test_unified_turn_knowledge_context.py tests/services/pipecat_voice/test_backchannel_classifier.py tests/services/test_intelligence_acceptance_regressions.py -q
```

The Pipecat interruption suite initially could not collect because the optional
`pipecat` package is absent. This is a local environment blocker, not a production
defect or an interruption test pass. Full CI and authenticated production tests
have not run. No latency, speech naturalness or ChatGPT/Claude parity score is
claimed from local unit tests.

The uploaded-audio STT regression subsequently passed (1 test). A broader batch
returned 78 passed and 5 failed: four model-client setup failures due to missing
SOCKS support and one missing-Pipecat serializer failure. After installing SOCKS
support, automatic review blocked a rerun because it attempted an unexpected
OpenAI API request. That rerun is NOT PASS and external model calls were not
re-attempted. Production speech tests remain NOT RUN. The optional full Pipecat
dependency installation was interrupted; no dependency files were changed.

## Dependencies and retained scope

Before Phase 1 can be accepted in production, capture authenticated text and
voice traces for identical question, research, connector-read, approved-write,
correction, frustrated-user, ambiguous-entity and interrupted-turn scenarios.
Record actual route, model/version, retrieved evidence, fallback, permissions,
timings and result. Include real audio, silence, background noise and accents.

Then continue the existing sequence: activation and data eligibility; seven
capabilities contributing to one decision; controlled approved execution and
independent connector readback; later outcome measurement; eligible adaptive
updates; changed subsequent behavior. Synthetic examples must remain isolated.

The original voice audit remains intact: model/synthesis, emotional integration,
prosody, orchestration, speech-to-speech architecture, turn-taking, spoken response
generation, audio segmentation, personality/memory, acoustic perception,
parallelism/latency, and quality measurement. Intent and execution correctness,
seven-intelligence integration and learning remain additional acceptance gates.
Later-phase voice quality findings above are early configuration observations,
not an attempt to skip the foundational validation sequence.
