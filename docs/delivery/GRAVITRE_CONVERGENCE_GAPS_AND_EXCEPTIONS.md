# GRAVITRE CONVERGENCE GAPS AND EXCEPTIONS

**Program:** H0 approved 2026-09-22. Amendments applied. Current production `d90b2838`. Product not accepted.

| ID | Type | Severity | Affected | Impact | Root cause | Attempted | Remaining | Why not now |
|----|------|----------|----------|--------|------------|-----------|-----------|-------------|
| GAP-001 | Closed | — | H0 | — | Approved | Spec amended | — | — |
| GAP-002 | External credentials | P1 | REQ-P4-002, EV-J-004 | Traffic sources honest-blocked | Isolated GA/GSC pending_auth | P4 pending_auth in evidence plan | H2, H3 | Must not invent analytics |
| GAP-003 | HUMAN_EXPERIENCE_PENDING | P0 product | REQ-PX-003, REQ-P3-002, EV-J-005 physical | Driving/hands-free LIVE_PROVEN not run | Physical mic / WebRTC deny | SAPI origin `probe_pcm` + user_mic unit | Independent acceptance audit; H9 | Not optional disappearance |
| GAP-004 | Eval keys | P2 | REQ-M-001, REQ-PX-002 | No signed tier bake-off | No local OPENAI_API_KEY | Harness `scripts/audit-model-tier-benchmark.py`; prod stays `low` | H7 then H8 | Do not silent-upgrade |
| GAP-005 | Partial live | P1 | REQ-P5-001, EV-J-007 | CIM itself still not terminal | CIM leftover `5f7f9ef6` running; class-level EAGAIN retry shipped | Two noop fixtures completed on `d90b2838` (Alpha `08:16:43Z`, Beta `08:13:44Z`) | Human fail/cancel of `5f7f9ef6`; independent acceptance | Do not mutate CIM |
| GAP-006 | Closed this SHA | — | EV-J-008 | — | — | conv `1bb45907` spoken_first_text_ms=161 audio_ms=164 on `d90b2838` | Independent acceptance | — |
| GAP-007 | Deferred Section 0 | P1 product | REQ-PX-011, REQ-PX-012, REQ-P7-001 | Visible computer / richer artifacts | Out of this cycle by spec | Freeze only; eval note kept | Later program | Not satisfied by being out of cycle |
| GAP-008 | Baseline defect (engineering addressed) | P1 | EV-J-005 | PCM false barge-in | Probe PCM treated as user_mic | Origin policy + probe scripts tag `probe_pcm` | Live SAPI on new SHA | IMPLEMENTED_PROOF_PENDING |
| GAP-009 | Baseline defect (engineering addressed) | P1 | EV-J-004 | CEO internals-only | No evidence plan | P4 pin HubSpot/Ads; KF not substitute; P1 one-shot | Live CEO on new SHA | IMPLEMENTED_PROOF_PENDING |
| GAP-010 | Closed this SHA | — | REQ-OP-001 | — | — | `d90b2838` on Railway `/health` | Independent acceptance | — |
| GAP-012 | Closed this SHA | — | P5 blocked WRITE | — | — | Sales Automation conv `85ef1f0d` pending_approval @ `2026-09-23T08:19:15.742858Z` not claimed complete | Independent acceptance | — |
| GAP-013 | Mitigated | P1 | CIM graph | Leftover CIM run still `running` | `[Errno 11]` on older SHA | Node/finalize retry + wrapped EAGAIN text on `d90b2838`; Alpha/Beta completed | Human CIM disposition | Do not CIM-special-case |
| GAP-011 | H11 | P2 | REQ-P6-002 | No labeled BUSINESS_IMPACT in 7d sample | Zero impact events | Unit consume path; TOOL_SUCCESS still not bias | Human-authorized label | Wiring complete |

**Deferred Section 0 (must remain in independent audit):** visible computer/browser execution; richer artifact productivity; physical-mic / driving hands-free; campaign asset factory.

No Computer Use implementation. No 3.0 rewrite. No silent H13 Cesar-stop. No material architecture diversion.
