"""Which in-process learning schedulers the API lifespan starts.

Temporal mode (TEMPORAL_HOST set) replaces the company-intelligence loop with
CompanyIntelligenceWorkflow (started via /api/internal/ops/company-intelligence-run).

The memory-promotion tick is different: it is the only periodic driver of
memory promotion evaluation AND ``outcome_attribution_service.measure_outcomes_due``
(Play measurement / objective replanning). Nothing starts MemoryPromotionWorkflow
in Temporal mode (``app.temporal.starters.start_memory_promotion_workflow`` has
no caller and there is no Temporal schedule), so skipping the in-process tick
there meant outcomes were never measured. It therefore starts in both modes —
exactly once, so there is no double-run in either mode.
"""
from __future__ import annotations


def learning_scheduler_plan(*, use_temporal: bool) -> dict[str, bool]:
    return {
        "company_intelligence": not use_temporal,
        "memory_promotion": True,
    }
