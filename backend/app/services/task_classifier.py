"""Task classification with pipeline routing flags — wraps IntentClassifier / classify_query."""
from __future__ import annotations

import re
from typing import Any

from app.config import Settings, get_settings
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_HEURISTIC,
    CONFIDENCE_SOURCE_MODEL,
    LIVE_PATH_HEURISTIC,
    LIVE_PATH_LOADED_ARTIFACT,
)
from app.services.user_intelligence import classify_query

REVENUE_PATTERN = re.compile(r"revenue|mrr|arr|churn|forecast|pipeline|deal", re.I)
WORKFLOW_PATTERN = re.compile(r"workflow|run|execute|automation|approve", re.I)
CRM_PATTERN = re.compile(r"contact|deal|account|hubspot|salesforce|crm", re.I)

TASK_TYPE_PIPELINE_MAP: dict[str, dict[str, Any]] = {
    "question_answering": {
        "requires_prediction": False,
        "requires_causal": False,
        "requires_graph": False,
        "requires_action": False,
        "requires_web_search": False,
        "risk_level": "low",
        "latency_target": "tier_1",
    },
    "data_analysis": {
        "requires_prediction": True,
        "requires_causal": True,
        "requires_graph": False,
        "requires_action": False,
        "requires_web_search": False,
        "risk_level": "low",
        "latency_target": "tier_2",
    },
    "workflow_execution": {
        "requires_prediction": False,
        "requires_causal": False,
        "requires_graph": False,
        "requires_action": True,
        "requires_approval": True,
        "requires_web_search": False,
        "risk_level": "medium",
        "latency_target": "tier_3",
    },
    "crm_lookup": {
        "requires_prediction": False,
        "requires_causal": False,
        "requires_graph": True,
        "requires_action": False,
        "requires_web_search": False,
        "risk_level": "low",
        "latency_target": "tier_1",
    },
    "analytics": {
        "requires_prediction": True,
        "requires_causal": True,
        "requires_graph": False,
        "requires_action": False,
        "requires_web_search": False,
        "risk_level": "low",
        "latency_target": "tier_2",
    },
    "general": {
        "requires_prediction": False,
        "requires_causal": False,
        "requires_graph": False,
        "requires_action": False,
        "requires_web_search": False,
        "risk_level": "low",
        "latency_target": "tier_1",
    },
    "workflow_planning": {
        "requires_prediction": False,
        "requires_causal": False,
        "requires_graph": False,
        "requires_action": False,
        "requires_web_search": False,
        "risk_level": "low",
        "latency_target": "tier_2",
    },
}

_CATEGORY_TO_INTENT = {
    "workflow_status": "workflow_execution",
    "analytics": "data_analysis",
    "connector_health": "crm_lookup",
    "help": "question_answering",
    "general": "question_answering",
}


def _intent_artifact_ready(classifier: Any) -> bool:
    """True only when a real trained text artifact is loaded (not an empty catalog shell)."""
    return (
        getattr(classifier, "vectorizer", None) is not None
        and getattr(classifier, "model", None) is not None
    )


def _confidence_from_probs(probs: list[dict[str, float]] | None, label: str) -> float:
    if not probs:
        return 0.0
    row = probs[0] or {}
    if label in row:
        return float(row[label])
    if row:
        return float(max(row.values()))
    return 0.0


class TaskClassifier:
    """
    Extends IntentClassifier output with pipeline routing flags.
    Does NOT replace IntentClassifier — wraps loaded artifact + rule fallback.

    Module C / STA-331: never treat catalog TRAINED as a live model score.
    Confidence and live_inference_path reflect the real inference path only.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def classify(
        self,
        org_id: str,
        request: str,
        conversation_history: list[dict] | None = None,
        understanding: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = conversation_history
        base = await self._classify_with_ml(org_id, request)
        intent = str(base.get("intent") or "question_answering")
        if understanding:
            dept = understanding.get("department_inference")
            if dept and not base.get("department"):
                base["department"] = dept
            if understanding.get("conversational_create"):
                intent = "workflow_planning"
            elif understanding.get("expected_output_format") == "plan":
                intent = "workflow_planning"
            elif understanding.get("expected_output_format") == "action":
                pipeline_action = TASK_TYPE_PIPELINE_MAP["workflow_execution"]
                base.update(pipeline_action)
                intent = "workflow_execution"
        pipeline_source = (
            TASK_TYPE_PIPELINE_MAP[intent]
            if intent in TASK_TYPE_PIPELINE_MAP
            else TASK_TYPE_PIPELINE_MAP["general"]
        )
        pipeline_flags = dict(pipeline_source)
        if understanding and understanding.get("conversational_create"):
            workflow_planning_flags = TASK_TYPE_PIPELINE_MAP["workflow_planning"]
            pipeline_flags = dict(workflow_planning_flags)
            intent = "workflow_planning"
        elif REVENUE_PATTERN.search(request):
            pipeline_flags.update(TASK_TYPE_PIPELINE_MAP["data_analysis"])
            intent = "data_analysis"
        elif WORKFLOW_PATTERN.search(request) and "what should" not in request.lower():
            if not (understanding and understanding.get("conversational_create")):
                pipeline_flags.update(TASK_TYPE_PIPELINE_MAP["workflow_execution"])
                intent = "workflow_execution"
        elif CRM_PATTERN.search(request):
            pipeline_flags.setdefault("requires_graph", True)
            if intent == "question_answering":
                intent = "crm_lookup"
                pipeline_flags.update(TASK_TYPE_PIPELINE_MAP["crm_lookup"])

        from app.services.assistant_availability import is_external_or_general_question, is_web_search_configured

        if is_external_or_general_question(request) and is_web_search_configured(self.settings):
            pipeline_flags["requires_web_search"] = True

        department = base.get("department")
        domain_context = (understanding or {}).get("domain") if understanding else None
        if domain_context:
            base["domain"] = domain_context
            if domain_context.get("routing_active") and domain_context.get("department_key"):
                department = domain_context.get("department_key")
            elif domain_context.get("department_key") and not department:
                department = domain_context.get("department_key")
        if not department and understanding:
            department = understanding.get("department_inference")
        if not department:
            lowered = request.lower()
            for dept in ("finance", "sales", "marketing", "hr", "engineering", "support"):
                if dept in lowered:
                    department = dept
                    break

        return {
            **base,
            **pipeline_flags,
            "intent": intent,
            "department": department,
            "request": request,
            "understanding": understanding or {},
            "domain": domain_context or base.get("domain"),
        }

    async def _classify_with_ml(self, org_id: str, request: str) -> dict[str, Any]:
        category = classify_query(request)
        intent = _CATEGORY_TO_INTENT.get(category, "question_answering")
        confidence = 0.55
        source = "rule_based_classify_query"
        confidence_is_estimate = True
        live_path = LIVE_PATH_HEURISTIC
        artifact_loaded = False

        try:
            from app.ml.model_catalog import load_org_trained_catalog_model

            classifier = await load_org_trained_catalog_model(
                org_id, "intent_classifier", settings=self.settings
            )
            if _intent_artifact_ready(classifier):
                artifact_loaded = True
                preds, probs = await classifier.predict_text(
                    [request], return_probabilities=True
                )
                if preds:
                    predicted = str(preds[0] or category)
                    category = predicted
                    intent = _CATEGORY_TO_INTENT.get(predicted, predicted)
                    if intent not in TASK_TYPE_PIPELINE_MAP:
                        intent = _CATEGORY_TO_INTENT.get(predicted, "question_answering")
                    confidence = _confidence_from_probs(probs, predicted)
                    if confidence <= 0:
                        confidence = 0.55
                    source = CONFIDENCE_SOURCE_MODEL
                    confidence_is_estimate = False
                    live_path = LIVE_PATH_LOADED_ARTIFACT
        except Exception:  # noqa: BLE001
            pass

        return {
            "intent": intent,
            "query_category": category,
            "classification_confidence": confidence,
            "classification_source": source,
            "confidence_is_estimate": confidence_is_estimate,
            "confidence_source": (
                CONFIDENCE_SOURCE_MODEL if artifact_loaded and not confidence_is_estimate
                else CONFIDENCE_SOURCE_HEURISTIC
            ),
            "live_inference_path": live_path,
            "artifact_loaded": artifact_loaded,
        }


_task_classifier: TaskClassifier | None = None


def get_task_classifier(settings: Settings | None = None) -> TaskClassifier:
    global _task_classifier
    if _task_classifier is None or settings is not None:
        _task_classifier = TaskClassifier(settings)
    return _task_classifier
