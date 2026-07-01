"""Unified evaluation across ML predictions, agent runs, workflows, and responses."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.model_selector import get_model_selector
from app.services.outcome_learning_service import get_outcome_learning_service
from app.services.response_evaluation_service import consolidate_evaluation
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

MIN_EVALUATIONS = 5


class IntelligenceEvaluationService:
    """
    Extends v7 response_evaluation_service with ML prediction accuracy, agent run quality,
    workflow success, and cross-model comparison. Does not replace response_evaluation_service.
    """

    DEPARTMENT_BENCHMARKS: dict[str, list[dict[str, Any]]] = {
        "marketing": [],
        "sales": [],
        "support": [],
        "operations": [],
        "finance": [],
        "hr": [],
        "engineering": [],
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._outcomes = get_outcome_learning_service(self.settings)

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def evaluate_model_response(
        self,
        org_id: str,
        message_id: str,
        model_name: str,
    ) -> dict[str, Any]:
        evaluation = await consolidate_evaluation(self.settings, org_id, message_id)
        if not evaluation:
            return {
                "evaluation_status": "pending_feedback",
                "message_id": message_id,
                "model_name": model_name,
            }
        return {
            "evaluation_status": "complete",
            "message_id": message_id,
            "model_name": model_name,
            "composite_score": evaluation.get("composite_score"),
            "user_feedback": evaluation.get("user_feedback"),
            "surface": evaluation.get("surface"),
        }

    async def evaluate_ml_prediction(
        self,
        org_id: str,
        model_name: str,
        predicted_value: float,
        actual_value: float | None,
        prediction_type: str,
    ) -> dict[str, Any]:
        if actual_value is None:
            return {
                "evaluation_status": "pending_measurement",
                "model_name": model_name,
                "prediction_type": prediction_type,
            }
        error = abs(float(predicted_value) - float(actual_value))
        denom = max(abs(float(actual_value)), 1.0)
        accuracy = max(0.0, 1.0 - error / denom)
        return {
            "evaluation_status": "complete",
            "model_name": model_name,
            "prediction_type": prediction_type,
            "accuracy": round(accuracy, 4),
            "predicted_value": predicted_value,
            "actual_value": actual_value,
        }

    async def evaluate_agent_run(self, org_id: str, agent_id: str, job_id: str) -> dict[str, Any]:
        try:
            row = (
                self._client()
                .table("agent_jobs")
                .select("id, status, org_id, agent_id")
                .eq("org_id", org_id)
                .eq("id", job_id)
                .limit(1)
                .execute()
            )
            if not row.data:
                return {"evaluation_status": "not_found", "job_id": job_id}
            job = row.data[0]
            if str(job.get("agent_id") or "") != agent_id:
                return {"evaluation_status": "org_scoped_mismatch", "job_id": job_id}
            status = str(job.get("status") or "")
            success = status in {"completed", "succeeded", "done"}
            return {
                "evaluation_status": "complete",
                "job_id": job_id,
                "agent_id": agent_id,
                "success": success,
                "status": status,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("evaluate_agent_run_skipped job_id=%s error=%s", job_id, exc)
            return {"evaluation_status": "insufficient_data", "job_id": job_id}

    async def evaluate_workflow_run(self, org_id: str, workflow_run_id: str) -> dict[str, Any]:
        try:
            row = (
                self._client()
                .table("workflow_runs")
                .select("id, status, org_id")
                .eq("org_id", org_id)
                .eq("id", workflow_run_id)
                .limit(1)
                .execute()
            )
            if not row.data:
                return {"evaluation_status": "not_found", "workflow_run_id": workflow_run_id}
            status = str(row.data[0].get("status") or "")
            success = status in {"completed", "succeeded", "success"}
            return {
                "evaluation_status": "complete",
                "workflow_run_id": workflow_run_id,
                "success": success,
                "status": status,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("evaluate_workflow_run_skipped run_id=%s error=%s", workflow_run_id, exc)
            return {"evaluation_status": "insufficient_data", "workflow_run_id": workflow_run_id}

    async def evaluate_recommendation(self, org_id: str, recommendation_id: str) -> dict[str, Any]:
        score = await self._outcomes.calculate_outcome_score(org_id, "recommendation", recommendation_id)
        if score.get("status") == "insufficient_data":
            return {"evaluation_status": "insufficient_data", "recommendation_id": recommendation_id}
        return {
            "evaluation_status": "complete",
            "recommendation_id": recommendation_id,
            "outcome_score": score.get("score"),
        }

    async def compare_models_for_task(
        self,
        org_id: str,
        task_type: str,
        department: str | None = None,
    ) -> dict[str, Any]:
        rows = await self._outcomes._fetch_events(org_id)
        filtered = [
            r
            for r in rows
            if str(r.get("task_type") or "") == task_type
            and (not department or str(r.get("department") or "").lower() == department.lower())
            and r.get("model_name")
        ]
        by_model: dict[str, list[dict[str, Any]]] = {}
        for row in filtered:
            name = str(row["model_name"])
            by_model.setdefault(name, []).append(row)
        comparisons: dict[str, Any] = {}
        for model_name, events in by_model.items():
            if len(events) < MIN_EVALUATIONS:
                comparisons[model_name] = {"status": "insufficient_data", "evaluations": len(events)}
                continue
            positive = sum(1 for e in events if e.get("outcome_event") in {"user_feedback_positive", "prediction_validated"})
            comparisons[model_name] = {
                "status": "ok",
                "score": round(positive / len(events), 4),
                "evaluations": len(events),
            }
        if not comparisons or all(v.get("status") == "insufficient_data" for v in comparisons.values()):
            return {"status": "insufficient_data", "task_type": task_type, "department": department}
        return {"status": "ok", "task_type": task_type, "department": department, "models": comparisons}

    async def recommend_best_model_for_task(
        self,
        org_id: str,
        task_type: str,
        department: str | None = None,
    ) -> dict[str, Any]:
        comparison = await self.compare_models_for_task(org_id, task_type, department)
        if comparison.get("status") == "insufficient_data":
            selector = get_model_selector(self.settings)
            fallback = await selector.select(org_id, {"intent": task_type, "department": department})
            return {
                "status": "insufficient_data",
                "fallback": fallback,
                "task_type": task_type,
            }
        models = comparison.get("models") or {}
        ranked = sorted(
            ((name, data) for name, data in models.items() if data.get("status") == "ok"),
            key=lambda item: float(item[1].get("score") or 0),
            reverse=True,
        )
        if not ranked:
            return {"status": "insufficient_data", "task_type": task_type}
        best_name, best_data = ranked[0]
        return {
            "status": "ok",
            "recommended_model": best_name,
            "score": best_data.get("score"),
            "evaluations": best_data.get("evaluations"),
            "task_type": task_type,
        }

    async def get_evaluation_summary(self, org_id: str, since_days: int = 7) -> dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        try:
            eval_rows = (
                self._client()
                .table("response_evaluations")
                .select("composite_score, user_feedback, surface")
                .eq("org_id", org_id)
                .gte("evaluated_at", since)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            eval_rows = []
        scores = [float(r["composite_score"]) for r in eval_rows if r.get("composite_score") is not None]
        helpful = sum(1 for r in eval_rows if r.get("user_feedback") == "helpful")
        return {
            "period_days": since_days,
            "response_evaluations": len(eval_rows),
            "avg_composite_score": round(sum(scores) / len(scores), 4) if scores else None,
            "helpful_rate": round(helpful / len(eval_rows), 4) if eval_rows else None,
        }

    async def get_model_performance_by_department(self, org_id: str, model_name: str) -> dict[str, Any]:
        rows = await self._outcomes._fetch_events(org_id)
        by_dept: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if str(row.get("model_name") or "") != model_name:
                continue
            dept = str(row.get("department") or "unknown")
            by_dept.setdefault(dept, []).append(row)
        result: dict[str, Any] = {}
        for dept, events in by_dept.items():
            if len(events) < MIN_EVALUATIONS:
                result[dept] = {"status": "insufficient_data", "count": len(events)}
            else:
                positive = sum(1 for e in events if e.get("outcome_event") in {"user_feedback_positive"})
                result[dept] = {"status": "ok", "score": round(positive / len(events), 4), "count": len(events)}
        return {"model_name": model_name, "by_department": result}

    async def get_model_performance_by_task_type(self, org_id: str, model_name: str) -> dict[str, Any]:
        rows = await self._outcomes._fetch_events(org_id)
        by_task: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if str(row.get("model_name") or "") != model_name:
                continue
            task = str(row.get("task_type") or "unknown")
            by_task.setdefault(task, []).append(row)
        result: dict[str, Any] = {}
        for task, events in by_task.items():
            if len(events) < MIN_EVALUATIONS:
                result[task] = {"status": "insufficient_data", "count": len(events)}
            else:
                positive = sum(1 for e in events if e.get("outcome_event") in {"user_feedback_positive"})
                result[task] = {"status": "ok", "score": round(positive / len(events), 4), "count": len(events)}
        return {"model_name": model_name, "by_task_type": result}

    async def run_benchmark(self, org_id: str, department: str) -> dict[str, Any]:
        items = self.DEPARTMENT_BENCHMARKS.get(department, [])
        if not items:
            return {
                "benchmark_status": "not_configured",
                "department": department,
                "message": "No benchmark items configured for this department yet.",
            }
        return {
            "benchmark_status": "planned",
            "department": department,
            "items_configured": len(items),
            "message": "Benchmark execution requires department pack test cases — not yet wired.",
        }

    async def load_admin_evaluations_summary(self, org_id: str, *, period_days: int = 7) -> dict[str, Any]:
        summary = await self.get_evaluation_summary(org_id, since_days=period_days)
        agents = (
            self._client()
            .table("agents")
            .select("id")
            .eq("org_id", org_id)
            .limit(50)
            .execute()
            .data
            or []
        )
        agent_rates: dict[str, Any] = {}
        for agent in agents[:10]:
            agent_id = str(agent.get("id") or "")
            if agent_id:
                agent_rates[agent_id] = await self._outcomes.get_agent_success_rate(org_id, agent_id)
        workflows = (
            self._client()
            .table("workflows")
            .select("id")
            .eq("org_id", org_id)
            .limit(20)
            .execute()
            .data
            or []
        )
        workflow_rates: dict[str, Any] = {}
        for wf in workflows[:10]:
            wf_id = str(wf.get("id") or "")
            if wf_id:
                workflow_rates[wf_id] = await self._outcomes.get_workflow_success_rate(org_id, wf_id)
        rec_rows = await self._outcomes._fetch_events(org_id)
        rec_events = [r for r in rec_rows if r.get("entity_type") == "recommendation"]
        approved = sum(1 for r in rec_events if r.get("outcome_event") == "recommendation_approved")
        approval_rate = round(approved / len(rec_events), 4) if rec_events else None
        benchmark_status = {
            dept: (await self.run_benchmark(org_id, dept)).get("benchmark_status")
            for dept in self.DEPARTMENT_BENCHMARKS
        }
        return {
            "model_performance": summary,
            "agent_success_rates": agent_rates,
            "workflow_success_rates": workflow_rates,
            "recommendation_approval_rate": approval_rate,
            "benchmark_status_by_department": benchmark_status,
            "period_days": period_days,
        }


_intelligence_evaluation_service: IntelligenceEvaluationService | None = None


def get_intelligence_evaluation_service(settings: Settings | None = None) -> IntelligenceEvaluationService:
    global _intelligence_evaluation_service
    if _intelligence_evaluation_service is None or settings is not None:
        _intelligence_evaluation_service = IntelligenceEvaluationService(settings)
    return _intelligence_evaluation_service
