"""Wave E — decision transparency and visibility envelope schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AlternativePathsConsidered(BaseModel):
    alternative_strategy_count: int = 0
    selected_strategy: str | None = None
    guidance_strength: float | None = None


class LearningConfidenceView(BaseModel):
    level: str
    sample_count: int | None = None
    noise: str | None = None
    insufficient_data: bool = False


class DomainHealthEntry(BaseModel):
    domain: str
    department: str | None = None
    subdomain: str | None = None
    health_score: float | None = None
    health_label: str = "unknown"
    learning_confidence: str = "insufficient_data"
    freshness: str = "unknown"
    retrieval_effectiveness: float | None = None
    optimization_recommendations: int = 0


class IntelligenceMaturityView(BaseModel):
    level: int = 1
    label: str = "Connected"
    description: str = ""
    factors: dict[str, Any] = Field(default_factory=dict)


class DecisionTransparencyEnvelope(BaseModel):
    decision_type: str = "unknown"
    confidence: float = 0.0
    confidence_band: str = "insufficient"
    evidence_used: list[dict[str, Any]] = Field(default_factory=list)
    sources_used: list[dict[str, Any]] = Field(default_factory=list)
    freshness_status: str | None = None
    domain_context: dict[str, Any] | None = None
    optimization_signals: list[dict[str, Any]] = Field(default_factory=list)
    learning_confidence: LearningConfidenceView | None = None
    known_gaps: list[str] = Field(default_factory=list)
    alternative_paths_considered: AlternativePathsConsidered | None = None
    retrieval_summary: dict[str, Any] | None = None
    trust_health: dict[str, Any] | None = None
    advisory_only: bool = True
    summary: str | None = None
    missing_context: list[str] = Field(default_factory=list)
    extension_points: dict[str, Any] = Field(
        default_factory=lambda: {
            "wave_f_multi_agent_explainability": None,
            "wave_g_simulation_transparency": None,
            "wave_h_autonomous_research_visibility": None,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class ExecutiveIntelligenceSummary(BaseModel):
    org_id: str
    intelligence_score: float | None = None
    score_label: str = "insufficient_data"
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    score_weights: dict[str, float] = Field(default_factory=dict)
    maturity: IntelligenceMaturityView | None = None
    domain_health: list[DomainHealthEntry] = Field(default_factory=list)
    top_performing_domains: list[str] = Field(default_factory=list)
    weak_domains: list[str] = Field(default_factory=list)
    missing_knowledge_areas: list[str] = Field(default_factory=list)
    optimization_opportunities: int = 0
    advisory_only: bool = True
