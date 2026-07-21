"""BusinessOutcome projection — single customer-facing shape over Module A."""

from app.services.business_outcome.models import BusinessOutcome
from app.services.business_outcome.pipeline import PipelineContext, run_business_outcome_pipeline
from app.services.business_outcome.projector import project_business_outcome

__all__ = [
    "BusinessOutcome",
    "PipelineContext",
    "project_business_outcome",
    "run_business_outcome_pipeline",
]
