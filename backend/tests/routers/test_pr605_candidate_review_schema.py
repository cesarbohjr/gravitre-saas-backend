"""PR605: source-level request model and OpenAPI audit regression."""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_candidate_review_decision_is_strict():
    from app.routers.capabilities import CandidateReviewRequest
    assert CandidateReviewRequest(decision="approve", notes="verified").decision == "approve"
    assert CandidateReviewRequest(decision="reject").decision == "reject"
    with pytest.raises(ValidationError):
        CandidateReviewRequest(decision="approved")
    with pytest.raises(ValidationError):
        CandidateReviewRequest(decision="approve", notes="x" * 2001)


def test_marketplace_review_request_openapi_schema_resolves():
    from app.routers.capabilities import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    schema = app.openapi()
    paths = schema.get("paths") or {}
    path = "/api/capabilities/marketplace-candidates/{candidate_id}/review"
    assert path in paths
    assert "post" in paths[path]
