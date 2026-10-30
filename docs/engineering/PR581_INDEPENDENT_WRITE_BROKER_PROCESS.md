# Independent effect counter and broker-process recovery

Prerequisite source: 6d65a9ee9ec657f4c117512b32f2f5e50a4847a8, previously certified by full CI 40992287907 and native run 40992287810. This addition requires fresh exact-source execution.

## Implemented workload

Each real Chromium comparison trial now uses an owned loopback HTTP fixture in a separate OS process. Only that server commits the SQLite write counter; reads, mutation controls and counter reads do not increment it. The parent observes the server count through a private pipe, independently of SDK replies, browser DOM text and the journal. Positive click must commit exactly one write; denied, cancelled and stale actions must leave it at one. The engine never receives the pipe or a counter-reset endpoint.

For trial zero of each adapter, obtain a fresh exact snapshot, start a separate broker process using the actual encrypted Journal, persist one approved action, and SIGKILL that broker. Wait for the real one-second lease to expire, start a new broker PID against the same private SQLite path and encryption key, and require uncertain state, the same idempotent job ID, one persisted action and zero replay claims. The actual browser dispatch wrapper asks the restarted broker for current journal authority and must receive false. The independent server count must remain unchanged. The fresh snapshot safety checks and original zero-write assertions remain active, with no retries or relaxed thresholds.

This process test runs within the isolated gVisor comparison image with networking disabled, bounded resources and both actual browser adapters. The new crypto dependency and test helper enter only the derived comparison image, not application or production worker images. No production setting, runtime default, gateway destination restriction or tenant grant changes.

## Evidence requirements

Rows include independent_server_process, unauthorized_writes and, for each adapter's first trial, broker_process_recovery with SIGKILL/new-PID booleans, uncertain state, one persisted action, zero replay claims, before/after server counts and unauthorized write delta. Evidence binds the source SHA and helper hash; no payload, key, raw DOM or process log is exported.

Local validation: both real process contracts passed (independent HTTP/SQLite counter and broker SIGKILL/new PID/encrypted-journal replay rejection). Changed Python sources compile. The current local runtime has no pytest installation; the full existing pytest suite is delegated to CI, not claimed locally.

## Limits

This is an owned guest-local HTTP fixture and a real journal-owning broker child process, not independent remote-production write telemetry, the configured production worker entrypoint lifecycle, live tenant revocation or full production gateway parity. Existing real DockerRunner/gVisor runtime certification remains a separate mandatory gate. Representative reliability/cost and historical Browser Use evidence drift remain open. New exact-source certification is pending until actual workflow results are inspected.

Browser Use remains the default. PR581 remains draft and unmerged. No deployment or adapter switch is performed.
