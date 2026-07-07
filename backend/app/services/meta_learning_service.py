"""Org-local meta-learning — strategy-family guidance per domain segment (Wave D3)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.learning_confidence_service import get_learning_confidence_service
from app.services.learning_strategy_keys import parse_base_segment_key_from_segment
from app.services.strategy_performance_ledger import get_strategy_performance_ledger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

TABLE = "domain_segment_learning_state"
MAX_GUIDANCE_INFLUENCE = 0.25
SOFT_PRIOR_CENTER = 1.0

STRATEGY_FAMILIES = frozenset(
    {"model", "agent", "retrieval", "workflow", "connector_combo", "consensus"}
)


class MetaLearningService:
    """
    Learns which strategies work best per org + domain segment.
    Influences selectors through soft priors only — never hard overrides.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._confidence = get_learning_confidence_service(self.settings)
        self._ledger = get_strategy_performance_ledger(self.settings)

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def is_enabled(self) -> bool:
        return bool(getattr(self.settings, "domain_adaptive_learning_enabled", False))

    async def is_enabled_for_org(self, org_id: str) -> bool:
        from app.services.org_learning_profile_service import get_org_learning_profile_service

        return await get_org_learning_profile_service(self.settings).is_adaptive_learning_enabled(org_id)

    @staticmethod
    def build_agent_strategy_key(persona_key: str) -> str:
        return f"agent:{persona_key}"

    @staticmethod
    def build_retrieval_strategy_key(strategy_key: str) -> str:
        return f"retrieval:{strategy_key}"

    @staticmethod
    def build_connector_combo_key(connectors: list[str]) -> str:
        cleaned = sorted({str(item).lower() for item in connectors if item})
        return f"connectors:{'+'.join(cleaned) if cleaned else 'none'}"

    @staticmethod
    def build_workflow_strategy_key(workflow_id: str) -> str:
        return f"workflow:{workflow_id}"

    async def record_strategy_outcome(
        self,
        org_id: str,
        segment_key: str,
        strategy_family: str,
        strategy_key: str,
        polarity: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_enabled():
            return {"status": "disabled"}
        family = str(strategy_family or "route").lower()
        key = str(strategy_key or "").strip()
        if not key:
            return {"status": "skipped", "reason": "empty_strategy_key"}
        if family not in STRATEGY_FAMILIES and family != "route":
            family = "route"

        if polarity == "positive":
            outcome = "win"
        elif polarity == "negative":
            outcome = "loss"
        else:
            outcome = "neutral"

        await self._ledger.record(
            org_id,
            key,
            outcome,
            strategy_family=family,
            segment_key=segment_key,
            metadata=metadata or {},
        )

        state = await self._load_segment_state(org_id, segment_key)
        meta_state = dict(state.get("meta_learning_state") or {})
        family_bucket = dict(meta_state.get(family) or {})
        entry = dict(family_bucket.get(key) or {"wins": 0, "losses": 0, "neutral": 0, "samples": 0})
        entry["samples"] = int(entry.get("samples") or 0) + 1
        if outcome == "win":
            entry["wins"] = int(entry.get("wins") or 0) + 1
        elif outcome == "loss":
            entry["losses"] = int(entry.get("losses") or 0) + 1
        else:
            entry["neutral"] = int(entry.get("neutral") or 0) + 1
        decided = int(entry.get("wins") or 0) + int(entry.get("losses") or 0)
        entry["win_rate"] = round(int(entry.get("wins") or 0) / decided, 4) if decided else None
        family_bucket[key] = entry
        meta_state[family] = family_bucket
        await self._persist_meta_state(org_id, segment_key, state, meta_state)
        return {"status": "recorded", "strategy_family": family, "strategy_key": key}

    async def recommend_strategy(
        self,
        org_id: str,
        segment_key: str,
        strategy_family: str,
        candidate_keys: list[str],
        *,
        default_key: str | None = None,
        classification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        guidance = await self.get_selection_guidance(
            org_id,
            segment_key,
            strategy_family,
            candidate_keys,
            default_key=default_key or (candidate_keys[0] if candidate_keys else ""),
            classification=classification,
        )
        if guidance.get("status") == "insufficient_data":
            return guidance
        recommended = guidance.get("recommended_key")
        return {
            **guidance,
            "recommended_strategy": recommended,
            "guidance_mode": "weighted_soft_prior",
        }

    async def compare_strategies(
        self,
        org_id: str,
        segment_key: str,
        strategy_family: str,
        strategy_keys: list[str],
    ) -> dict[str, Any]:
        ranked = await self._rank_candidates(org_id, segment_key, strategy_family, strategy_keys)
        return {
            "segment_key": segment_key,
            "strategy_family": strategy_family,
            "comparisons": ranked,
        }

    async def get_best_strategy_for_segment(
        self,
        org_id: str,
        segment_key: str,
        strategy_family: str,
        candidate_keys: list[str],
        *,
        default_key: str | None = None,
    ) -> dict[str, Any]:
        guidance = await self.get_selection_guidance(
            org_id,
            segment_key,
            strategy_family,
            candidate_keys,
            default_key=default_key or (candidate_keys[0] if candidate_keys else ""),
        )
        if guidance.get("status") == "insufficient_data":
            return guidance
        return {
            "status": "ok",
            "segment_key": segment_key,
            "strategy_family": strategy_family,
            "best_strategy": guidance.get("recommended_key"),
            "win_rate": guidance.get("win_rate"),
            "sample_count": guidance.get("sample_count"),
            "guidance_strength": guidance.get("guidance_strength"),
        }

    async def explain_strategy_choice(
        self,
        org_id: str,
        segment_key: str,
        strategy_family: str,
        selected_key: str,
        *,
        default_key: str | None = None,
        candidate_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        guidance = await self.get_selection_guidance(
            org_id,
            segment_key,
            strategy_family,
            candidate_keys or [selected_key],
            default_key=default_key or selected_key,
        )
        if guidance.get("status") == "insufficient_data":
            return {
                "status": "insufficient_data",
                "segment_key": segment_key,
                "strategy_family": strategy_family,
                "selected_key": selected_key,
                "explanation": (
                    f"Insufficient segment evidence ({guidance.get('sample_count', 0)} samples). "
                    "Using domain routing defaults."
                ),
            }
        recommended = guidance.get("recommended_key")
        strength = float(guidance.get("guidance_strength") or 0)
        if recommended == selected_key:
            explanation = (
                f"Meta-learning soft prior aligns with {selected_key} for segment {segment_key} "
                f"(win_rate={guidance.get('win_rate')}, strength={strength:.2f})."
            )
        else:
            explanation = (
                f"Selected {selected_key} from domain/context routing. Meta-learning would softly prefer "
                f"{recommended} for this segment, but guidance is non-binding (strength={strength:.2f})."
            )
        return {
            "status": "ok",
            "segment_key": segment_key,
            "strategy_family": strategy_family,
            "selected_key": selected_key,
            "recommended_key": recommended,
            "guidance_strength": strength,
            "explanation": explanation,
            "soft_priors": guidance.get("soft_priors") or {},
        }

    async def get_meta_learning_summary(self, org_id: str) -> dict[str, Any]:
        if not self.is_enabled():
            return {"status": "disabled", "org_id": org_id}

        try:
            rows = (
                self._client()
                .table(TABLE)
                .select("segment_key, meta_learning_state, sample_count, learning_confidence, last_updated_at")
                .eq("org_id", org_id)
                .order("last_updated_at", desc=True)
                .limit(100)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            rows = []

        segment_summaries: list[dict[str, Any]] = []
        insufficient: list[str] = []
        best_models: list[dict[str, Any]] = []
        best_agents: list[dict[str, Any]] = []
        best_retrieval: list[dict[str, Any]] = []

        for row in rows:
            segment_key = str(row.get("segment_key") or "")
            meta_state = row.get("meta_learning_state") or {}
            total_samples = sum(
                int(entry.get("samples") or 0)
                for family in meta_state.values()
                if isinstance(family, dict)
                for entry in family.values()
                if isinstance(entry, dict)
            )
            assessment = self._confidence.assess(sample_count=total_samples)
            summary = {
                "segment_key": segment_key,
                "sample_count": total_samples,
                "learning_confidence": assessment.level,
                "families": list(meta_state.keys()),
            }
            segment_summaries.append(summary)
            if assessment.insufficient_data:
                insufficient.append(segment_key)
            for family, label, bucket in (
                ("model", "best_models", best_models),
                ("agent", "best_agents", best_agents),
                ("retrieval", "best_retrieval", best_retrieval),
            ):
                best = self._best_from_meta_state(meta_state, family, segment_key)
                if best:
                    bucket.append(best)

        return {
            "status": "ok",
            "org_id": org_id,
            "segment_summaries": segment_summaries,
            "insufficient_data_warnings": insufficient,
            "best_models": best_models[:10],
            "best_agents": best_agents[:10],
            "best_retrieval_strategies": best_retrieval[:10],
            "last_updated_at": rows[0].get("last_updated_at") if rows else None,
            "federated_learning": "disabled",
            "cross_tenant_learning": False,
            "guidance_mode": "weighted_soft_prior",
        }

    async def get_selection_guidance(
        self,
        org_id: str,
        segment_key: str,
        strategy_family: str,
        candidate_keys: list[str],
        *,
        default_key: str,
        classification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = classification
        if not self.is_enabled():
            return {"status": "disabled", "segment_key": segment_key}

        keys = list(dict.fromkeys([default_key, *candidate_keys]))
        ranked = await self._rank_candidates(org_id, segment_key, strategy_family, keys)
        total_decided = sum(int(item.get("decided_samples") or 0) for item in ranked)
        assessment = self._confidence.assess(sample_count=total_decided)
        if assessment.insufficient_data:
            return {
                "status": "insufficient_data",
                "segment_key": segment_key,
                "strategy_family": strategy_family,
                "sample_count": total_decided,
                "min_samples_required": assessment.min_samples_required,
                "soft_priors": {key: SOFT_PRIOR_CENTER for key in keys},
            }

        guidance_strength = min(MAX_GUIDANCE_INFLUENCE, assessment.learning_rate_multiplier * MAX_GUIDANCE_INFLUENCE)
        soft_priors = self._compute_soft_priors(ranked, default_key, guidance_strength)
        best = next((item for item in ranked if item.get("win_rate") is not None), ranked[0] if ranked else None)
        recommended = (best or {}).get("strategy_key") or default_key

        return {
            "status": "guidance",
            "segment_key": segment_key,
            "strategy_family": strategy_family,
            "recommended_key": recommended,
            "default_key": default_key,
            "guidance_strength": round(guidance_strength, 4),
            "win_rate": (best or {}).get("win_rate"),
            "sample_count": total_decided,
            "learning_confidence": assessment.level,
            "soft_priors": soft_priors,
            "ranked": ranked,
            "hard_override": False,
        }

    def apply_model_soft_prior(
        self,
        selection: dict[str, Any],
        guidance: dict[str, Any],
        *,
        ledger_reason: str | None = None,
    ) -> dict[str, Any]:
        """Nudge LLM tier at most one step — never replace ledger win-rate selection."""
        if guidance.get("status") != "guidance":
            return selection
        if ledger_reason == "ledger_win_rate":
            updated = dict(selection)
            updated["meta_learning_guidance"] = guidance
            updated["meta_learning_applied"] = False
            updated["meta_learning_reason"] = "ledger_evidence_preserved"
            return updated

        updated = dict(selection)
        tiers = ("fast", "standard", "reasoning")
        current_tier = str(updated.get("llm_tier") or "standard")
        recommended = str(guidance.get("recommended_key") or "")
        target_tier = recommended.split(":", 1)[1] if recommended.startswith("llm:") else current_tier
        if target_tier not in tiers:
            updated["meta_learning_guidance"] = guidance
            updated["meta_learning_applied"] = False
            return updated

        current_idx = tiers.index(current_tier)
        target_idx = tiers.index(target_tier)
        strength = float(guidance.get("guidance_strength") or 0)
        if strength <= 0 or current_idx == target_idx:
            updated["meta_learning_guidance"] = guidance
            updated["meta_learning_applied"] = False
            return updated

        step = 1 if target_idx > current_idx else -1
        if abs(target_idx - current_idx) > 1:
            target_idx = current_idx + step
        if strength < MAX_GUIDANCE_INFLUENCE * 0.5 and abs(target_idx - current_idx) >= 1:
            updated["meta_learning_guidance"] = guidance
            updated["meta_learning_applied"] = False
            updated["meta_learning_reason"] = "guidance_too_weak_for_tier_change"
            return updated

        updated["llm_tier"] = tiers[target_idx]
        updated["meta_learning_guidance"] = guidance
        updated["meta_learning_applied"] = True
        updated["meta_learning_reason"] = "soft_prior_one_tier_nudge"
        return updated

    def apply_agent_soft_prior(
        self,
        agent_selection: dict[str, Any],
        guidance: dict[str, Any],
    ) -> dict[str, Any]:
        """Never replace persona — annotate guidance and optional tie-break metadata only."""
        updated = dict(agent_selection)
        updated["meta_learning_guidance"] = guidance
        if guidance.get("status") != "guidance":
            updated["meta_learning_applied"] = False
            return updated

        recommended = str(guidance.get("recommended_key") or "")
        current = str(updated.get("persona_key") or "")
        recommended_persona = recommended.split(":", 1)[1] if recommended.startswith("agent:") else recommended
        strength = float(guidance.get("guidance_strength") or 0)
        updated["meta_learning_recommended_persona"] = recommended_persona or None
        updated["meta_learning_applied"] = False
        updated["meta_learning_reason"] = (
            "weighted_guidance_only"
            if recommended_persona and recommended_persona != current
            else "aligned_with_current_persona"
        )
        if recommended_persona and recommended_persona != current and strength >= MAX_GUIDANCE_INFLUENCE:
            updated["meta_learning_tie_break_hint"] = recommended_persona
        return updated

    def apply_tool_soft_prior(
        self,
        tool_selection: dict[str, Any],
        guidance: dict[str, Any],
    ) -> dict[str, Any]:
        if guidance.get("status") != "guidance":
            return tool_selection
        priors = guidance.get("soft_priors") or {}
        strength = float(guidance.get("guidance_strength") or 0)
        if strength <= 0:
            return tool_selection

        def boost_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
            scored: list[tuple[float, dict[str, Any]]] = []
            for tool in tools:
                fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
                name = str(fn.get("name") or tool.get("name") or "")
                connector = name.split("_", 1)[0].lower() if "_" in name else name.lower()
                multiplier = 1.0
                for key, prior in priors.items():
                    if key.startswith("connectors:") and connector in key:
                        multiplier = max(multiplier, float(prior))
                scored.append((multiplier, tool))
            scored.sort(key=lambda item: (-item[0], str(item[1].get("name") or "")))
            return [tool for _, tool in scored]

        updated = dict(tool_selection)
        updated["read_tools"] = boost_tools(list(updated.get("read_tools") or []))
        updated["write_tools"] = boost_tools(list(updated.get("write_tools") or []))
        updated["meta_learning_guidance"] = guidance
        updated["meta_learning_applied"] = True
        updated["meta_learning_reason"] = "connector_soft_reorder"
        return updated

    async def apply_to_retrieval_plan(
        self,
        plan: Any,
        org_id: str,
        segment_key: str,
        *,
        default_retrieval_key: str = "retrieval:domain_v1",
        candidate_retrieval_keys: list[str] | None = None,
    ) -> Any:
        from app.services.domain_retrieval_policy import RetrievalPlan

        if not isinstance(plan, RetrievalPlan) or not self.is_enabled():
            return plan

        candidates = candidate_retrieval_keys or [default_retrieval_key, "retrieval:assignment_aligned"]
        guidance = await self.get_selection_guidance(
            org_id,
            segment_key,
            "retrieval",
            candidates,
            default_key=default_retrieval_key,
        )
        plan.meta_learning_guidance = guidance
        if guidance.get("status") != "guidance":
            return plan

        priors = guidance.get("soft_priors") or {}
        default_prior = float(priors.get(default_retrieval_key, SOFT_PRIOR_CENTER))
        plan.meta_learning_delta = round(max(0.75, min(1.25, default_prior)), 4)
        return plan

    async def _rank_candidates(
        self,
        org_id: str,
        segment_key: str,
        strategy_family: str,
        candidate_keys: list[str],
    ) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        state = await self._load_segment_state(org_id, segment_key)
        meta_state = (state.get("meta_learning_state") or {}).get(strategy_family) or {}
        for key in candidate_keys:
            ledger_stats = await self._ledger.get_strategy_stats(
                org_id,
                key,
                segment_key=segment_key,
            )
            local = meta_state.get(key) or {}
            decided = int(ledger_stats.get("decided_samples") or 0)
            wins = int(local.get("wins") or 0) + int(ledger_stats.get("wins") or 0)
            losses = int(local.get("losses") or 0) + int(ledger_stats.get("losses") or 0)
            combined_decided = wins + losses
            ranked.append(
                {
                    "strategy_key": key,
                    "sample_size": int(ledger_stats.get("sample_size") or 0) + int(local.get("samples") or 0),
                    "decided_samples": max(decided, combined_decided),
                    "wins": wins,
                    "losses": losses,
                    "win_rate": round(wins / combined_decided, 4) if combined_decided else ledger_stats.get("win_rate"),
                    "ucb_score": ledger_stats.get("ucb_score"),
                }
            )
        ranked.sort(
            key=lambda item: (
                item.get("win_rate") is not None,
                item.get("win_rate") or 0.0,
                item.get("decided_samples") or 0,
            ),
            reverse=True,
        )
        return ranked

    def _compute_soft_priors(
        self,
        ranked: list[dict[str, Any]],
        default_key: str,
        guidance_strength: float,
    ) -> dict[str, float]:
        priors: dict[str, float] = {}
        default_rate = next(
            (float(item.get("win_rate") or 0.5) for item in ranked if item.get("strategy_key") == default_key),
            0.5,
        )
        for item in ranked:
            key = str(item.get("strategy_key") or "")
            win_rate = float(item.get("win_rate") or default_rate)
            delta = (win_rate - default_rate) * guidance_strength
            priors[key] = round(max(0.75, min(1.25, SOFT_PRIOR_CENTER + delta)), 4)
        if default_key not in priors:
            priors[default_key] = SOFT_PRIOR_CENTER
        return priors

    async def _load_segment_state(self, org_id: str, segment_key: str) -> dict[str, Any]:
        try:
            rows = (
                self._client()
                .table(TABLE)
                .select("*")
                .eq("org_id", org_id)
                .eq("segment_key", segment_key)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                return rows[0]
        except Exception as exc:  # noqa: BLE001
            logger.debug("meta_learning_load_skipped org=%s segment=%s error=%s", org_id, segment_key, exc)
        industry, department, subdomain, task_type = self._parse_segment_parts(segment_key)
        return {
            "org_id": org_id,
            "segment_key": segment_key,
            "industry": industry,
            "department": department,
            "subdomain": subdomain,
            "task_type": task_type,
            "meta_learning_state": {},
        }

    async def _persist_meta_state(
        self,
        org_id: str,
        segment_key: str,
        state: dict[str, Any],
        meta_state: dict[str, Any],
    ) -> None:
        industry, department, subdomain, task_type = self._parse_segment_parts(segment_key)
        row = {
            "id": state.get("id") or str(uuid4()),
            "org_id": org_id,
            "segment_key": segment_key,
            "industry": industry,
            "department": department,
            "subdomain": subdomain,
            "task_type": task_type,
            "meta_learning_state": meta_state,
            "meta_learning_delta": float(state.get("meta_learning_delta") or 1.0),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        for field in (
            "source_weight_deltas",
            "assignment_boost_deltas",
            "adaptive_weight_delta",
            "outcome_multiplier",
            "sample_count",
            "positive_count",
            "negative_count",
            "noise_score",
            "learning_confidence",
        ):
            if field in state:
                row[field] = state[field]
        try:
            self._client().table(TABLE).upsert(row, on_conflict="org_id,segment_key").execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("meta_learning_persist_skipped org=%s segment=%s error=%s", org_id, segment_key, exc)

    @staticmethod
    def _parse_segment_parts(segment_key: str) -> tuple[str | None, str | None, str | None, str | None]:
        base = parse_base_segment_key_from_segment(segment_key)
        parts = str(base).split(":")
        if len(parts) >= 4:
            return parts[0], parts[1], parts[2], parts[3]
        if len(parts) == 2:
            return None, parts[0], None, parts[1]
        return None, None, None, None

    @staticmethod
    def _best_from_meta_state(
        meta_state: dict[str, Any],
        family: str,
        segment_key: str,
    ) -> dict[str, Any] | None:
        bucket = meta_state.get(family)
        if not isinstance(bucket, dict) or not bucket:
            return None
        best_key = None
        best_rate = -1.0
        best_samples = 0
        for key, entry in bucket.items():
            if not isinstance(entry, dict):
                continue
            decided = int(entry.get("wins") or 0) + int(entry.get("losses") or 0)
            if decided <= 0:
                continue
            rate = float(entry.get("win_rate") or (int(entry.get("wins") or 0) / decided))
            if rate > best_rate or (rate == best_rate and decided > best_samples):
                best_key = key
                best_rate = rate
                best_samples = decided
        if not best_key:
            return None
        return {
            "segment_key": segment_key,
            "strategy_key": best_key,
            "win_rate": round(best_rate, 4),
            "sample_count": best_samples,
        }


_service: MetaLearningService | None = None


def get_meta_learning_service(settings: Settings | None = None) -> MetaLearningService:
    global _service
    if _service is None or settings is not None:
        _service = MetaLearningService(settings)
    return _service
