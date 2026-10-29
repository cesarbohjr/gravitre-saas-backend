# Paired Chromium adapter experiment

The first experiment is a real Chromium **microbenchmark**, not a replacement
production adapter or a completed selection gate. Browser Use remains the runtime
implementation while the required comparison is incomplete.

## First measured checkpoint (2026-10-29)

[Run 40901461342](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/40901461342)
passed the original real native runtime certification and all ten adapter trials.
PR587 head `a1b0b76aed29854ca6d3e380d3f8dfa8c922d9a1` was tested as merge
commit `70fa2ca2c5b37bc832ec7df665372fd2fc0be390` against main
`147da7f0c6a17f1964aa828f9c1ac88dc9b99bc1`.
The checked artifact ZIP SHA-256 is
`d6e921e83f71cd275b7303955e3eb2ec54d12ffb4b1eec994fc497b640c3518e`;
the derived image ID is
`sha256:01df64d311afebc3dde1f00d594d4423a7fa9c3a00e02720b9992180c9bf73ef`.
The original sanitized report is preserved at
`docs/delivery/pr581-browser-adapter-experiment-2026-10-29.json`.

| Median, milliseconds | Browser Use 0.13.14 | Playwright 1.64.1 |
| --- | ---: | ---: |
| Setup | 1160.09 | 1712.42 |
| Redirect navigation and DOM readiness | 369.15 | 261.65 |
| Stable snapshot | 728.79 | 534.92 |
| Approved click and independent readback | 1412.71 | 625.18 |

Both adapters completed 5/5 trials. This first capture also exposed a harness
confound: repeatedly configuring the SDK could wrap the snapshot method more
than once across trials. The follow-up makes configuration idempotent and adds
an actual SDK contract assertion. These numbers remain a historical diagnostic
checkpoint and **must be rerun after that correction before comparative
selection**. They do not establish statistical reliability or production parity.

Separately, the same-checkpoint PR581 run
[40901421117](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/40901421117)
failed before any browser model request or approval. The sanitized stack reached
the rejecting dialog handler's `Page.enable` while the SDK connection handshake
was awaiting tab-created handlers. A follow-up defers Page-domain activation out
of that event, then requires successful activation before model execution,
approval snapshots and completion. Failure still denies execution; dialogs are
never implicitly accepted. A blocked-handshake regression proves setup can
return while the readiness gate remains blocked. Exact-head real certification
after this candidate correction remains required.

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
