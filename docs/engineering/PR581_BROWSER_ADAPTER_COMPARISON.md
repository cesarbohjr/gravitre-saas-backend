# Paired Chromium adapter experiment

The first experiment is a real Chromium **microbenchmark**, not a replacement
production adapter or a completed selection gate. Browser Use remains the runtime
implementation while the required comparison is incomplete.

## Declared workload and thresholds

Five fresh-browser trials per adapter, alternating the starting adapter. Each
uses the same Chromium executable, 1280×720 viewport, unprivileged user, gVisor,
read-only root, dropped capabilities, no-new-privileges, CPU/memory/process bounds
and exact derived image. Each trial is limited to 90 seconds. The guest-local
HTTP fixture runs on loopback with Docker networking disabled; no host mounts,
customer sessions, credentials, model calls or external page writes are present.

Every trial must pass redirect navigation, dynamic rendered DOM readiness,
observed URL/title, actual viewport screenshot, approved click with independent
effect readback, denied action/no write, cancelled action/no write and stale
page/no write. All trials must pass; no retry converts a failed trial to a pass.
The current benchmark reuses production stable/fresh snapshot functions and
decoded-pixel/DOM evidence. Its comparison-only review dispatcher is explicitly
not an alternative authoritative execution/authorization path.

Record setup, navigation/readiness, snapshot and approved-click/readback latency
individually, including all failed rows. These five paired trials are diagnostic
evidence, not a reliability or cost study. No adoption rule is inferred from a
small median difference. A later selection requires all safety checks plus the
same gateway/runtime/recovery workload and a predeclared representative sample;
no framework choice is made from this microbenchmark alone.

## Reproducibility and dependency review

The existing native CI job exports the exact image that passed SDK contracts,
then runs the original real-service certification unchanged. A derived image
adds the isolated hash-pinned Playwright 1.64.1 comparison dependencies. Both
adapter arms use that same image. CI uploads its image ID and the sanitized
report, which binds the Git SHA, fixture/harness/engine hashes, Chromium/library
versions, thresholds, per-trial outcomes and timings. Raw screenshots, page text,
SDK exception bodies and model data are not report fields.

The four downloaded distributions identify licenses as follows: Playwright
Apache-2.0; greenlet MIT AND PSF-2.0; pyee MIT; typing_extensions PSF-2.0. The
Linux CPython 3.12 comparison lock uses typing_extensions 4.15.0 to preserve the
pinned Browser Use requirement. `pip check` must pass in the derived image.
Full candidate dependency vulnerability/reachability review remains required
before any production adoption. No application or production image requirement
changes. The enclosing CI job timeout increases only to accommodate the new
bounded trials; existing runtime assertions and isolation requirements remain.

## Evidence still required

The local page isolates SDK behavior from external DNS/TLS/gateway failure. It
does **not** compare the full production egress gateway, canonical tenant/action
authorization, worker crash recovery, model task quality, operational cost or
maintenance burden. Those are explicit report gaps. The existing canonical
Browser Use runtime still requires its own real gateway certification. A future
direct Playwright runtime candidate must meet the same gates before selection.
Stagehand remains optional. No production selection, merge or activation is
authorized by a passing microbenchmark.
