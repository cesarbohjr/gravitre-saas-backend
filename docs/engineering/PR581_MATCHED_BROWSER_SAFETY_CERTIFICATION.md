# PR581 matched browser safety certification

Source prerequisite: 4362ec0f0e7154331849d8fc2d3e8fa9da0abcb4.
Full CI: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/40976107046 — all applicable jobs passed, including backend pytest and integration smoke; conditional Billing E2E skipped. All 13 PR-triggered workflow runs for that head succeeded.
Native certification: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/40976106972 — all five jobs passed. Tested synthetic merge eb040cfb0ef6617ea0cdba8defbe594cca02d2f4.

Downloaded and inspected runtime artifact 12943650258 (ZIP SHA256 7841bbd5a962721738e1e042f7e8bce9a4d2ba99013cf4a525b4b679d4a0fbe5) and comparison artifact 12942972922 (ZIP SHA256 e65bb7e41f6f4d0658e085a14c23d93ce3beec8768c51e2ec885b5b1fb772ec6).

Both real gVisor runners passed approved navigation/click/readback, revocation fencing, engine kill, journal reopen after simulated lease expiry, idempotent resubmission and rejected replay. The existing runtime cancellation case used OpenHands, and denied navigation used only Playwright. Do not call those matched browser runtime tests.

The local guest-only microbenchmark passed 5/5 per adapter. Median elapsed milliseconds: Browser Use 5949.84; Playwright 5172.81. It asserts zero unauthorized fixture writes after denied, cancelled and stale requests. It is not a production reliability, authorization or cost study. Historical Browser Use evidence drift in run 40975143658 remains a reliability investigation; a later green sample does not establish its cause or resolution.

## Added execution matrix — pending exact-source CI

For each actual Browser Use and Playwright DockerRunner, approve navigation to the public Selenium test form, request the submit click through a separate encrypted journal, then either deny the click or cancel the journal after approval but before dispatch reauthorization. Require the exact request sequence [0,1], execution failure, cancelled state, no new claim, rejection of the stale action lease, erased action material and complete container/network cleanup. Both images, gateway, isolation and production default remain unchanged.

The emitted scenario rows contain only adapter, scenario, sequence and fixed state/boolean results. No task, DOM, screenshot, token, credential or exception body is added to evidence.

## Scope limits / blockers

- New matched denial/cancellation runtime cases require a green exact-source gVisor run before PASS.
- Real-runtime fences do not provide an independently observed remote server write counter; zero unauthorized writes are directly counted only by the owned local benchmark.
- Revocation uses host-owned fixture authorization, not live tenant membership or grant revocation.
- Durable restart reopens SQLite with a fresh Journal after engine kill and advances the claim clock; it is not an operating-system broker power-loss test or live tenant replay.
- Representative reliability/cost, broader task quality, and the historical evidence-drift cause remain unresolved.
- No production adapter selection, merge, deployment, native activation or live customer action is performed.
