# Voice identity regression evidence

The Voice Identity Regression workflow checks out the exact PR head, not the
synthetic merge commit. It runs targeted backend, Vitest and synthetic Chromium
HTTP/Pipecat tests without live provider or production credentials.

The latency test records 20 cold and 20 warm first-audio event measurements
through the HTTP service, with a mocked 10 ms guard and 40 ms TTS delay.
Percentiles use nearest rank. Warmup is excluded from measured turn latency.
These measurements are not provider, physical-device, or production SLO evidence.

The SHA-named artifact contains JUnit reports, raw latency samples and a
manifest with execution outcomes and SHA-256 file digests. Missing evidence
or a failed/skipped test step fails the workflow. A successful workflow is
synthetic regression evidence only, not Voice 3.0 candidate certification.

A branch-scoped push trigger also runs synthetic CI on the Voice 3.0 engineering
branch independently of PR mergeability. Both triggers pin the actual source
commit. PR-only API clients may not list push-triggered runs; consult Actions.
