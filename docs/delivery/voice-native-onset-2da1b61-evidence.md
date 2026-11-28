# Voice reference evidence — exact SHA 2da1b61f7c7ac455397b88f3babc31b13c461f0d

## Provenance
Hosted run: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/46111210710
Artifact: 15249054208; ZIP SHA-256: 6114874fd7401982c5344a3ca5b18a3fac165297e3f08798119af2b3c5b4f260.
Reconstructed independently from all 40 raw trial records in native-onset-paired.json (20 three-frame control; 20 two-frame candidate).
Percentiles below use nearest-rank method, 20 samples per mode.

| Metric | Three-frame control p50 / p95 | Two-frame candidate p50 / p95 |
|---|---|---|
| Interruption residual | 325.3 / 354.7 ms | 306.7 / 330.7 ms |
| First audio | 576.0 / 589.3 ms | 557.3 / 560.0 ms |
| Subsequent response | 349.3 / 378.7 ms | 333.3 / 360.0 ms |
| Acoustic gap | 5.3 / 8.0 ms | 8.0 / 8.0 ms |

Both modes: 20/20 exact marker sequence (1,2); 0 reported receiver stats errors; no cross-reply leakage in screening records.
The candidate has 16/20 legacy residual failures and 14/20 passive AudioWorklet screening failures. The control has 20/20 of each. Both remain rejected by the unchanged sub-300 ms threshold.
The one-frame experiment at 8fe781b was rejected because premature/repeated marker commits occurred; commit 2da1b61 removed it.

## Interpretation and constraints
- AudioWorklet uses a passive 480-sample analysis window. Its results corroborate the failed interruption screening; it does not directly timestamp physical speaker output.
- Browser inbound RTP jitterBufferDelay, jitterBufferTargetDelay and jitterBufferEmittedCount are cumulative. Their raw totals are NOT per-packet residence. To estimate a window mean, calculate delta(jitterBufferDelay)/delta(jitterBufferEmittedCount) between two receiver snapshots for the same stats id, with strictly increasing emitted count. Do not confuse this with exact interruption playout delay.
- Pipecat native sender queue clearing was previously confirmed, but the majority of remaining residual is outside the unsent sender queue. Do not claim the receiver jitter buffer alone explains the residual.
- The synthetic marker detector is not production speech onset, backchannel detection or naturalness evidence.

## Certification mapping
This is supporting evidence for the **existing 12 final end-to-end QA workflows**, not a new gate or an additional workflow. Attach exact-SHA raw artifacts and screening outcomes to the appropriate Voice / conversation / interruption and cross-system governance acceptance cases in the existing 12-workflow master matrix. Do not certify any of the 43 findings solely from this synthetic experiment.
No production deployment, merge, live-provider activation or model-router promotion is authorized by these results.

## Next engineering gate
Measure receiver delta residence and correlate with clock-aligned track dequeue and AudioWorklet observations, then reproduce any corrective change against the same 20+20 control under matched conditions. Preserve interruption <300 ms, continuity, no cross-reply leakage and false-interruption rejection. Only integrate canonical model routing into the accepted reference once these gates pass.
