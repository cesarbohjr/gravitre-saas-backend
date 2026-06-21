"""Live workflow context channel for agent handoffs and swarm subtasks (STA-270)."""
from __future__ import annotations

from typing import Any

from app.services.handoff_service import build_handoff_briefing

MAX_STEP_SUMMARY_CHARS = 500


class SequentialContext:
    """Workflow step_outputs + parameters exposed as a shared coordination channel."""

    def __init__(
        self,
        *,
        run_id: str,
        step_outputs: dict[str, Any] | None = None,
        parameters: dict[str, Any] | None = None,
        current_step_id: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.step_outputs = step_outputs or {}
        self.parameters = parameters or {}
        self.current_step_id = current_step_id

    def _summarize_step_outputs(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for step_id, output in self.step_outputs.items():
            if not isinstance(output, dict):
                continue
            summary = str(output.get("summary") or output.get("finding") or "")[:MAX_STEP_SUMMARY_CHARS]
            summaries.append(
                {
                    "stepId": step_id,
                    "summary": summary,
                    "confidence": output.get("confidence"),
                    "branch": output.get("branch"),
                }
            )
        return summaries

    def to_channel_payload(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "currentStepId": self.current_step_id,
            "priorSteps": self._summarize_step_outputs(),
            "parameterKeys": sorted(self.parameters.keys()),
        }

    def to_briefing(
        self,
        *,
        source_output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        briefing = build_handoff_briefing(
            parameters=self.parameters,
            source_output=source_output,
            step_outputs=self.step_outputs,
        )
        briefing["coordination_channel"] = self.to_channel_payload()
        return briefing

    def to_swarm_subtask_context(self, *, objective: str, swarm_run_id: str) -> dict[str, Any]:
        return {
            "objective": objective,
            "swarmRunId": swarm_run_id,
            "channel": self.to_channel_payload(),
        }

    @classmethod
    def from_job_payload(cls, payload: dict[str, Any]) -> SequentialContext | None:
        raw = payload.get("coordinationContext")
        if not isinstance(raw, dict):
            return None
        channel = raw.get("channel") if isinstance(raw.get("channel"), dict) else raw
        run_id = str(channel.get("runId") or raw.get("runId") or payload.get("swarmRunId") or "")
        if not run_id:
            return None
        prior = channel.get("priorSteps") if isinstance(channel.get("priorSteps"), list) else []
        step_outputs = {
            str(item.get("stepId") or f"step-{idx}"): {"summary": item.get("summary"), "confidence": item.get("confidence")}
            for idx, item in enumerate(prior)
            if isinstance(item, dict)
        }
        return cls(
            run_id=run_id,
            step_outputs=step_outputs,
            current_step_id=str(channel.get("currentStepId") or "") or None,
        )
