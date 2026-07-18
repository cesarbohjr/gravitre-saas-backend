# Phase 0 — CF / Churn ML (both sequenced)

**Date:** 2026-07-18  
**Decision:** Cesar started CF/churn ML after 12-pack rollup. Sequence locked: **churn first**, then **CF**.  
**Parent:** `docs/delivery/ml-stack-phase0-findings.json` (Recommendation: heuristic first; churn was OOS — superseded here for sequenced build)  
**Program:** `docs/delivery/master-knowledge-intelligence-packs-program.md`

---

## Sequence lock

| Step | Track | This pass |
|------|--------|-----------|
| 1 | **Churn** advisory productionization | **START** — feature/label contract, gates, advisory API, predictive UI fix |
| 2 | **CF** collaborative filtering | **Phase 0 design only** — no CF ranker code until churn advisory path ships + volume gate |

Hard rules (both tracks):

- **Advisory only** — never auto-contact, never auto-execute, never bypass `execute_plan` / approval gates  
- Suggest-only cards may use **navigation hrefs** only (STA-314 contract)  
- STA-124 integration health ≠ account churn  
- Evidence bar for Done: prod tip / audit / HTTP artifact — pytest alone is not enough  

---

## A. Churn ML (build now)

### Existing

- Model: `backend/app/ml/churn_scoring.py` (`ChurnRiskScorer`, `MIN_TRAINING_EXAMPLES=30`, `advisory_only=True`)  
- Train: `train_churn_risk_scorer` in `intelligence_training.py`  
- Surfaces: predictive ops packs (sales/support/marketing), admin predictive-ops domain API  

### Gaps closed in start slice

1. **Labeled feature contract** — `metric_name=churn_customer_signal`, `target_entity_type=customer`, FEATURE_KEYS in `outcome_payload`, label via `outcome_success` (false = churned)  
2. **Strict volume gate** — count FEATURE_KEYS-bearing labeled rows (≥30), not raw AAO row count  
3. **Advisory API** — `GET /api/intelligence/churn-risk/advisory` (suggest-only account cards)  
4. **CS domain pack** — `customer_success` in predictive ops  
5. **Predictive UI** — render domain `predictions` dict as cards  

### Label definition (locked)

| Label | Meaning | `outcome_success` |
|-------|---------|-------------------|
| churned | cancel / non-renew / closed-lost account | `false` |
| retained | still active / renewed | `true` |

Do **not** treat generic agent `outcome_success` failures as churn unless written through the churn ingest helper.

### FEATURE_KEYS (unchanged)

`days_since_last_activity`, `open_support_tickets`, `failed_payments_30d`, `deal_stage_regressions`, `email_engagement_score`

### Non-goals (churn start)

- Auto email / Slack / dialer  
- Claiming CS dashboard KPI DONE without live tip evidence  
- HubSpot live bulk backfill without Cesar-named smoke-org run  

---

## B. CF (Phase 0 only — after churn)

### Existing (not CF)

- STA-314 heuristics: `recommendation_heuristics_service` + `GET /api/intelligence/recommendations/heuristics`  
- Phase 5.2 soft-rank: `recommendation_quality_engine` via CRM / outcome events  
- Feedback: dismissals, assistant recommendation feedback, `crm_recommendation_outcomes`  

### CF v1 design (when unlocked)

| Item | Spec |
|------|------|
| Interaction matrix | org × (connector \| pack \| heuristic card_id) from usage + accept/dismiss/CRM |
| Cold start | Keep heuristics; CF re-ranks only when volume gate met |
| Contract | Same STA-314 bans — no execute payloads |
| Volume gate (proposed) | ≥50 scored interactions / org in 30d before CF rank enabled |
| Placement | Soft-rank layer after heuristics, before dismiss filter |

### Non-goals (CF Phase 0)

- No matrix-factorization code this pass  
- No auto-execute from CF scores  
- Does not replace Phase 5.2 outcome soft-rank until CF tip PASSes  

---

## Evidence

| Artifact | Role |
|----------|------|
| `docs/delivery/phase5-cf-churn-ml-start.json` | Start tip / status |
| Unit tests | ingest gate, advisory no-execute, UI dict→list |
| Future live tip | train readiness + advisory HTTP on smoke org after deploy |

---

## Program updates

- Lift “CF/churn ML” from blank hold → **STARTED (churn first)**  
- CF remains deferred for code until churn advisory slice evidence lands  
