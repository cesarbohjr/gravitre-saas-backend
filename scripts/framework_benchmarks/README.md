# Isolated framework experiments

These tools do not enter application requirements, activate an alternative
brain, or supply production quality certification. Framework decisions follow
measured capability comparisons, not package availability.

## DeepEval exact tool traces

Use a separate Linux/Python 3.12 environment and the complete hash-pinned lock:

```
python -m pip install --require-hashes -r scripts/framework_benchmarks/requirements-deepeval.lock
python scripts/framework_benchmarks/deepeval_tools.py --output /absolute/scratch/deepeval-tools.json
```

This executes DeepEval 4.3.2's actual `ToolCorrectnessMetric` with strict exact
matching, ordered calls and input-parameter comparison. Twelve synthetic labeled
traces cover valid reads/corrections, wrong tenant/amount, missing/extra/duplicate
calls, ordering and cancelled writes. The reference is simple strict trace
equality. It is **not** the existing conversational judge baseline. Tool-trace
agreement cannot prove that canonical tenant authorization or execution worked.

An explicit custom model forbids inference; socket and gRPC hooks forbid
network access even if an error is caught. Telemetry is disabled and the SDK's
read-only filesystem mode is set before import. Raw traces, metric explanations,
SDK errors, credentials and identity data are omitted from the report. The
report binds dataset/harness/lock/metric hashes and library version. CI reruns
the real SDK and audits all 66 resolved packages, without advisory exclusions.
DeepEval's package declares Apache-2.0. Full license/reachability review is still
required before any broader use or adoption.

First actual local result: both the strict reference and SDK detect all **12/12**
labels; zero inference calls and zero network attempts. The reference median
was 0.00088 ms; SDK measurement median was 0.08811 ms in this microexperiment.
These tiny local timings are diagnostic, not provider latency or operating-cost
measurements. The complete 66-package dependency audit found no known
vulnerabilities at this checkpoint. Sanitized evidence and audit are preserved
under `docs/delivery/pr587-deepeval-*-2026-10-29.json`.

No tool-trace accuracy gain was demonstrated, so this experiment provides no
reason to add DeepEval to the application for exact trace matching. Overall
DeepEval selection remains **BLOCKED** pending comparison against the existing
fixed conversational evaluator, independently reviewed examples, provider
judgment validity and representative quality/cost/reliability evidence.

## Voice and memory gates

The voice aggregate comparator now reports native duplex, Pipecat and LiveKit
sample counts and diagnostic metrics separately. Raw aggregate rows cannot
recommend an engine: they lack matched tasks, recording integrity, environment
and source provenance, quality review and functional candidate certification.
Booleans masquerading as numeric latency/cost and nonboolean outcome flags are
rejected. There is no runtime transport-default change.

This is not a completed functional LiveKit/Pipecat audio comparison. Real audio
interruptions, turn-taking, corrections, reconnect, channel transition and
revocation/cancelled-write scenarios remain required. Provider roundtrip and
physical microphone/speaker evidence are distinct gates. The local execution
environment exposes no OpenAI, Anthropic, Deepgram or ElevenLabs credentials.
Existing acceptance CI has isolated voice-provider secret references, but that
does not supply candidate-adapter or physical-audio evidence automatically.

Mem0's pinned root-cause/storage audit remains a complete-erasure **FAIL**.
Neither its controlled CPU embedder lifecycle suite nor these tool traces prove
semantic memory quality. The native/Mem0 matched extraction/retrieval/correction
quality and efficiency study, supported scoped erasure remedy and independently
reviewed evidence remain open. Native memory stays selected.
