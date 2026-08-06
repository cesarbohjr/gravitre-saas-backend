# G.5.9 Phase 1 — Apollo/Marketo population-verify close

**Status:** CLOSED (Apollo+HubSpot live; Marketo follow-up wired, live NOT_RUN)  
**Code tip (this ship):** pending deploy after commit  
**Live evidence (local verify against smoke connectors):** `f6-collection-population-verify-live.json` @ `2026-08-06T09:57:22Z`

## Pre-flight (Prompt 3)

| Gate | Tip `45ae7d05` result |
|------|------------------------|
| Prompt 1 TTFT | Fresh battery wall p50 **735** / max **1840** (`unified-turn-task-ttft-prompt3-preflight.json`). 200ms aspirational still FAIL (honest). Not 3568/20904 class. |
| Prompt 2 enrichment | Tip-matched **95.06%** top-k, 690/690 coverage (`catalog-enrichment-nl-variance-live.json`) |

## Gap confirmed

| Vendor | Before | After |
|--------|--------|-------|
| HubSpot | Long backoff + settle | Unchanged (shared helper) |
| Apollo | Shorter `(2,3,5,8,8)`, **no** settle read | **Equalized** to HubSpot `_SETTLE_BACKOFF_S` + `_SETTLE_FINAL_SLEEP_S` |
| Marketo | No follow-up → `follow_up_unavailable_or_async` | **Decision (a):** wire `marketo.lists.get_leads` (GET `/lists/{id}/leads.json`) via same settle helper |

## Live evidence

| Vendor | Result | IDs |
|--------|--------|-----|
| Apollo | `follow_up_membership_confirmed` | list `6a745a5453956d0010a1e55f`, contact `6a745a5a4e8a3200102de75c`, connector `8992743f…` |
| HubSpot | `follow_up_membership_confirmed` | list `45`, contact `270287894506`, connector `41175658…` |
| Marketo | **NOT_RUN** | Zero prod Marketo connectors; decision (a) still ships code + unit settle tests |

## Standing tests

`backend/tests/services/test_f6_hubspot_follow_up_membership.py` — HubSpot + Apollo settle parity + Marketo follow-up.
