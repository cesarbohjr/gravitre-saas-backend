"""G1 — Canonical Intelligence State contract (projection, not a new database)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# --- Semantic node / edge kinds (lenses filter the same graph) ---

IntelligenceNodeType = Literal[
    "core",
    "domain",
    "objective",
    "entity",
    "knowledge",
    "memory",
    "learning",
    "signal",
    "evidence",
    "prediction",
    "model",
    "agent",
    "workflow",
    "action",
    "connector",
    "approval",
    "outcome",
]

IntelligenceEdgeType = Literal[
    "KNOWS",
    "RELATED_TO",
    "LEARNED_FROM",
    "EVIDENCE_FOR",
    "PREDICTS",
    "AFFECTS",
    "USED_BY",
    "ASSIGNED_TO",
    "EXECUTED",
    "READ_FROM",
    "WROTE_TO",
    "REQUIRES_APPROVAL",
    "PRODUCED",
    "CONTRIBUTED_TO",
    "IMPROVED",
    "CONTRADICTS",
]

IntelligenceLensId = Literal["knows", "learns", "predicts", "acts", "improves"]

IntelligenceQualityFlag = Literal[
    "INSUFFICIENT_EVIDENCE",
    "STALE_DATA",
    "UNSCOPED_PREDICTION",
    "CONFLICTING_STATUS",
    "MISSING_RELATIONSHIP",
    "UNKNOWN_BUSINESS_OBJECT",
    "NO_OUTCOME_ATTRIBUTION",
    "NO_BUSINESS_LEARNING_YET",
]

AgentConfiguredStatus = Literal["active", "idle", "processing", "error"]
AgentExecutionStatus = Literal["running", "idle"]


class IntelligenceProvenance(BaseModel):
    system: str
    recordId: str | None = None
    fetchedAt: str | None = None


class CanonicalAgent(BaseModel):
    id: str
    name: str
    role: str | None = None
    department: str | None = None
    businessLabel: str
    technicalLabel: str | None = None
    configuredStatus: AgentConfiguredStatus
    executionStatus: AgentExecutionStatus
    isConfiguredActive: bool
    isCurrentlyRunning: bool
    source: IntelligenceProvenance
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalPrediction(BaseModel):
    id: str
    type: str
    businessStatement: str
    subject: str | None = None
    objective: str | None = None
    department: str | None = None
    horizon: str | None = None
    confidence: float | None = None
    evidence: list[str] = Field(default_factory=list)
    sourceModel: str | None = None
    createdAt: str | None = None
    freshness: str | None = None
    status: str = "active"
    recommendedActions: list[str] = Field(default_factory=list)
    qualityFlags: list[IntelligenceQualityFlag] = Field(default_factory=list)
    source: IntelligenceProvenance
    semanticKey: str


class LearningInsight(BaseModel):
    id: str
    businessStatement: str
    learnedFrom: list[str] = Field(default_factory=list)
    affectedEntities: list[str] = Field(default_factory=list)
    affectedObjectives: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: str | None = None
    learnedAt: str | None = None
    usedByAgents: list[str] = Field(default_factory=list)
    usedByModels: list[str] = Field(default_factory=list)
    resultingChanges: list[str] = Field(default_factory=list)
    source: IntelligenceProvenance


class IntelligenceMetrics(BaseModel):
    knowledge: dict[str, int | float | None] = Field(default_factory=dict)
    learning: dict[str, int | float | None] = Field(default_factory=dict)
    predictions: dict[str, int | float | None] = Field(default_factory=dict)
    execution: dict[str, int | float | None] = Field(default_factory=dict)
    outcomes: dict[str, int | float | None] = Field(default_factory=dict)


class IntelligenceGraphNode(BaseModel):
    id: str
    type: IntelligenceNodeType
    businessLabel: str
    technicalLabel: str | None = None
    status: str | None = None
    source: IntelligenceProvenance
    freshness: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntelligenceGraphEdge(BaseModel):
    id: str
    type: IntelligenceEdgeType
    fromId: str
    toId: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntelligenceGraph(BaseModel):
    nodes: list[IntelligenceGraphNode] = Field(default_factory=list)
    edges: list[IntelligenceGraphEdge] = Field(default_factory=list)


class IntelligenceSnapshot(BaseModel):
    generatedAt: str
    tenantId: str
    timeWindowHours: int
    coreState: str
    agents: list[CanonicalAgent] = Field(default_factory=list)
    predictions: list[CanonicalPrediction] = Field(default_factory=list)
    learnings: list[LearningInsight] = Field(default_factory=list)
    metrics: IntelligenceMetrics
    qualityFlags: list[IntelligenceQualityFlag] = Field(default_factory=list)
    departments: list[dict[str, Any]] = Field(default_factory=list)
    models: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    workflows: list[dict[str, Any]] = Field(default_factory=list)
    outcomes: list[dict[str, Any]] = Field(default_factory=list)


class AssistantVisualization(BaseModel):
    lens: IntelligenceLensId | None = None
    focusNodeIds: list[str] = Field(default_factory=list)
    highlightNodeIds: list[str] = Field(default_factory=list)
    dimNodeIds: list[str] = Field(default_factory=list)
    expandNodeIds: list[str] = Field(default_factory=list)
    edgeTypes: list[IntelligenceEdgeType] = Field(default_factory=list)
    timeWindowHours: int | None = None


class IntelligencePageContext(BaseModel):
    """Scoped VIEW over canonical IntelligenceSnapshot — not a separate source of truth."""

    snapshot: IntelligenceSnapshot
    graph: IntelligenceGraph
    activeLens: IntelligenceLensId = "knows"
    availableLenses: list[IntelligenceLensId] = Field(
        default_factory=lambda: ["knows", "learns", "predicts", "acts", "improves"]
    )
    metrics: IntelligenceMetrics
    qualityFlags: list[IntelligenceQualityFlag] = Field(default_factory=list)
    suggestedQuestions: list[str] = Field(default_factory=list)
