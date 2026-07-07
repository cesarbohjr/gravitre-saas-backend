"""Hierarchical domain classification — industry, department, subdomain, objectives."""
from __future__ import annotations

import json
import re
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.loader import (
    load_domain_profile,
    load_taxonomy,
    resolve_department_key,
    resolve_industry_key,
)
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

DOMAIN_CONFIDENCE_THRESHOLD = 0.55
HIGH_CONFIDENCE_THRESHOLD = 0.75


class DomainIntelligenceService:
    """
    Classifies requests into hierarchical domain context.
    Uses org profile hints first, rule/keyword taxonomy second, LLM fallback last.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def classify(
        self,
        org_id: str,
        message: str,
        conversation_history: list[dict] | None = None,
        *,
        understanding: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = conversation_history
        org_hints = await self._load_org_domain_hints(org_id)
        rule_result = self._classify_by_rules(message, org_hints, understanding=understanding)
        org_boosted = self._apply_org_profile(rule_result, org_hints)

        if float(org_boosted.get("confidence") or 0) >= HIGH_CONFIDENCE_THRESHOLD:
            return self._finalize(org_boosted)

        if float(org_boosted.get("confidence") or 0) >= DOMAIN_CONFIDENCE_THRESHOLD:
            return self._finalize(org_boosted)

        llm_result = await self._classify_by_llm(message, org_hints, org_boosted)
        merged = self._merge_results(org_boosted, llm_result)
        return self._finalize(merged)

    async def _load_org_domain_hints(self, org_id: str) -> dict[str, Any]:
        try:
            row = (
                get_supabase_client(self.settings)
                .table("organizations")
                .select("settings")
                .eq("id", org_id)
                .limit(1)
                .execute()
            )
            if not row.data:
                return {}
            settings = row.data[0].get("settings") or {}
            if not isinstance(settings, dict):
                return {}
            industry_raw = settings.get("industry") or settings.get("vertical")
            department_raw = settings.get("department") or settings.get("primary_department")
            domain_profile = settings.get("domain_profile") or settings.get("domainProfile")
            return {
                "industry_raw": industry_raw,
                "industry": resolve_industry_key(str(industry_raw) if industry_raw else None),
                "department_raw": department_raw,
                "department": resolve_department_key(str(department_raw) if department_raw else None),
                "profile_id": str(domain_profile).lower() if domain_profile else None,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("domain_org_hints_skipped org_id=%s error=%s", org_id, exc)
            return {}

    def _classify_by_rules(
        self,
        message: str,
        org_hints: dict[str, Any],
        *,
        understanding: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        taxonomy = load_taxonomy()
        lowered = message.lower()
        departments = taxonomy.get("departments") or {}
        industries = taxonomy.get("industries") or {}

        best_dept: str | None = None
        best_sub: str | None = None
        best_dept_score = 0.0
        best_sub_score = 0.0

        for dept_key, dept_meta in departments.items():
            if not isinstance(dept_meta, dict):
                continue
            dept_keywords = [str(k).lower() for k in (dept_meta.get("keywords") or [])]
            dept_hits = sum(1 for kw in dept_keywords if kw in lowered)
            dept_score = dept_hits / max(len(dept_keywords), 1)
            if dept_score > best_dept_score:
                best_dept_score = dept_score
                best_dept = dept_key

            for sub_key, sub_meta in (dept_meta.get("subdomains") or {}).items():
                if not isinstance(sub_meta, dict):
                    continue
                sub_keywords = [str(k).lower() for k in (sub_meta.get("keywords") or [])]
                sub_hits = sum(1 for kw in sub_keywords if kw in lowered)
                sub_score = sub_hits / max(len(sub_keywords), 1)
                if sub_score > best_sub_score:
                    best_sub_score = sub_score
                    best_sub = sub_key
                    if sub_score >= dept_score:
                        best_dept = dept_key

        if understanding and understanding.get("department_inference"):
            inferred = resolve_department_key(str(understanding["department_inference"]))
            if inferred and best_dept_score < 0.2:
                best_dept = inferred
                best_dept_score = 0.35

        best_industry: str | None = org_hints.get("industry")
        best_industry_score = 0.4 if best_industry else 0.0
        for ind_key, ind_meta in industries.items():
            if not isinstance(ind_meta, dict):
                continue
            ind_keywords = [str(k).lower() for k in (ind_meta.get("keywords") or [])]
            ind_hits = sum(1 for kw in ind_keywords if kw in lowered)
            ind_score = ind_hits / max(len(ind_keywords), 1)
            if ind_score > best_industry_score:
                best_industry_score = ind_score
                best_industry = ind_key

        execution_type = self._infer_execution_type(lowered, taxonomy, understanding)
        business_objective = self._infer_business_objective(lowered, taxonomy)

        confidence = max(best_dept_score, best_sub_score, best_industry_score * 0.9)
        if best_sub and best_sub_score >= 0.15:
            confidence = max(confidence, 0.55 + min(0.35, best_sub_score))
        elif best_dept and best_dept_score >= 0.15:
            confidence = max(confidence, 0.5 + min(0.3, best_dept_score))

        return {
            "industry": best_industry,
            "department": best_dept,
            "subdomain": best_sub,
            "business_objective": business_objective,
            "execution_type": execution_type,
            "confidence": round(min(0.95, confidence), 3),
            "source": "rules",
            "profile_id": None,
        }

    def _apply_org_profile(self, result: dict[str, Any], org_hints: dict[str, Any]) -> dict[str, Any]:
        merged = dict(result)
        if org_hints.get("industry") and not merged.get("industry"):
            merged["industry"] = org_hints["industry"]
            merged["confidence"] = max(float(merged.get("confidence") or 0), 0.65)
            merged["source"] = "org_profile"
        if org_hints.get("department"):
            if not merged.get("department") or float(merged.get("confidence") or 0) < 0.6:
                merged["department"] = org_hints["department"]
                merged["confidence"] = max(float(merged.get("confidence") or 0), 0.7)
                merged["source"] = "org_profile"
        if org_hints.get("profile_id"):
            merged["profile_id"] = org_hints["profile_id"]
        return merged

    async def _classify_by_llm(
        self,
        message: str,
        org_hints: dict[str, Any],
        rule_result: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            from app.services.model_router import TaskType, get_model_router

            taxonomy = load_taxonomy()
            dept_labels = {
                key: meta.get("label")
                for key, meta in (taxonomy.get("departments") or {}).items()
                if isinstance(meta, dict)
            }
            rule_guess = {
                key: rule_result.get(key) for key in ("industry", "department", "subdomain")
            }
            prompt = (
                "Classify the business domain of this user message. "
                "Return JSON only with keys: industry, department, subdomain, "
                "business_objective, execution_type, confidence (0-1 float).\n"
                f"Allowed departments: {list(dept_labels.keys())}\n"
                f"Org hints: {json.dumps(org_hints)}\n"
                f"Rule guess: {json.dumps(rule_guess)}\n"
                f"Message: {message[:1200]}"
            )
            response = await get_model_router(self.settings).complete(
                task_type=TaskType.CLASSIFICATION,
                prompt=prompt,
                system_prompt="Domain classifier. JSON only. No chain of thought.",
                org_id=None,
                temperature=0.0,
                max_tokens=220,
            )
            clean = (response.content or "").strip()
            if clean.startswith("```"):
                clean = re.sub(r"^```(?:json)?\s*", "", clean)
                clean = re.sub(r"\s*```$", "", clean)
            parsed = json.loads(clean)
            if not isinstance(parsed, dict):
                return rule_result
            confidence = float(parsed.get("confidence") or 0.5)
            return {
                "industry": resolve_industry_key(str(parsed.get("industry") or "")) or parsed.get("industry"),
                "department": resolve_department_key(str(parsed.get("department") or "")) or parsed.get("department"),
                "subdomain": str(parsed.get("subdomain") or "").lower().replace(" ", "_") or None,
                "business_objective": parsed.get("business_objective"),
                "execution_type": parsed.get("execution_type"),
                "confidence": round(min(0.95, confidence), 3),
                "source": "llm",
                "profile_id": None,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("domain_llm_classify_skipped error=%s", exc)
            return rule_result

    @staticmethod
    def _merge_results(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
        merged = dict(primary)
        for key in ("industry", "department", "subdomain", "business_objective", "execution_type"):
            if not merged.get(key) and secondary.get(key):
                merged[key] = secondary[key]
        merged["confidence"] = max(float(primary.get("confidence") or 0), float(secondary.get("confidence") or 0))
        if secondary.get("source") == "llm" and float(secondary.get("confidence") or 0) >= float(primary.get("confidence") or 0):
            merged["source"] = "llm"
        return merged

    def _finalize(self, result: dict[str, Any]) -> dict[str, Any]:
        profile_id = result.get("profile_id")
        department = result.get("department")
        if not profile_id and department:
            profile_id = str(department).lower()
        if profile_id and not load_domain_profile(str(profile_id)):
            if department:
                profile_id = str(department).lower()
        profile = load_domain_profile(str(profile_id)) if profile_id else None
        if profile and not result.get("department"):
            result["department"] = profile.get("department")
        labels = self._resolve_labels(result)
        return {
            "industry": labels.get("industry_label") or result.get("industry"),
            "industry_key": result.get("industry"),
            "department": labels.get("department_label") or result.get("department"),
            "department_key": result.get("department"),
            "subdomain": labels.get("subdomain_label") or result.get("subdomain"),
            "subdomain_key": result.get("subdomain"),
            "business_objective": result.get("business_objective"),
            "execution_type": result.get("execution_type"),
            "confidence": float(result.get("confidence") or 0.0),
            "source": result.get("source") or "default",
            "profile_id": profile.get("profile_id") if profile else profile_id,
            "routing_active": float(result.get("confidence") or 0) >= DOMAIN_CONFIDENCE_THRESHOLD,
        }

    @staticmethod
    def _resolve_labels(result: dict[str, Any]) -> dict[str, str | None]:
        taxonomy = load_taxonomy()
        labels: dict[str, str | None] = {
            "industry_label": None,
            "department_label": None,
            "subdomain_label": None,
        }
        industries = taxonomy.get("industries") or {}
        departments = taxonomy.get("departments") or {}
        ind_key = result.get("industry")
        dept_key = result.get("department")
        sub_key = result.get("subdomain")
        if ind_key and ind_key in industries:
            labels["industry_label"] = str(industries[ind_key].get("label") or ind_key)
        if dept_key and dept_key in departments:
            labels["department_label"] = str(departments[dept_key].get("label") or dept_key)
            subdomains = departments[dept_key].get("subdomains") or {}
            if sub_key and sub_key in subdomains:
                labels["subdomain_label"] = str(subdomains[sub_key].get("label") or sub_key)
        return labels

    @staticmethod
    def _infer_execution_type(
        lowered: str,
        taxonomy: dict[str, Any],
        understanding: dict[str, Any] | None,
    ) -> str | None:
        if understanding:
            fmt = understanding.get("expected_output_format")
            if fmt == "action":
                return "action"
            if fmt in {"report", "data", "summary"}:
                return "analysis"
        for key, meta in (taxonomy.get("execution_types") or {}).items():
            if not isinstance(meta, dict):
                continue
            keywords = [str(k).lower() for k in (meta.get("keywords") or [])]
            if any(kw in lowered for kw in keywords):
                return key
        return None

    @staticmethod
    def _infer_business_objective(lowered: str, taxonomy: dict[str, Any]) -> str | None:
        for key, meta in (taxonomy.get("business_objectives") or {}).items():
            if not isinstance(meta, dict):
                continue
            keywords = [str(k).lower() for k in (meta.get("keywords") or [])]
            if any(kw in lowered for kw in keywords):
                return key
        return None


_service: DomainIntelligenceService | None = None


def get_domain_intelligence_service(settings: Settings | None = None) -> DomainIntelligenceService:
    global _service
    if _service is None or settings is not None:
        _service = DomainIntelligenceService(settings)
    return _service
