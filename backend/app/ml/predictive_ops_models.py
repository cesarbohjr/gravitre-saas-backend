"""PLANNED predictive ops scaffolds with honest org data gate reporting."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel
from app.workflows.repository import get_supabase_client

MIN_SLA_TICKET_SAMPLES = 60
MIN_DEAL_LOSS_LABELS = 25
MIN_CAPACITY_SERIES = 21


class SlaBreachPredictor(CatalogScaffoldModel):
    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.PLANNED
    advisory_only = True
    catalog_name = "sla_breach_predictor"

    async def _count_ticket_signals(self, org_id: str, settings: Settings) -> int:
        client = get_supabase_client(settings)
        try:
            resp = (
                client.table("agent_action_outcomes")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("metric_name", "ticket_volume")
                .execute()
            )
            return int(resp.count or 0)
        except Exception:  # noqa: BLE001
            return 0

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        org_id = str(kwargs.get("org_id") or "")
        settings = kwargs.get("settings") or get_settings()
        count = await self._count_ticket_signals(org_id, settings) if org_id else 0
        return {
            "status": "not_available",
            "model": self.catalog_name,
            "reason": (
                f"PLANNED — requires {MIN_SLA_TICKET_SAMPLES}+ Zendesk/support SLA history rows "
                "with resolution timestamps before training."
            ),
            "data_gate": {
                "current": count,
                "required": MIN_SLA_TICKET_SAMPLES,
                "met": count >= MIN_SLA_TICKET_SAMPLES,
            },
            "fallback": "optimization_suggestion_service support backlog detector",
            "advisory_only": True,
        }


class DealLossScorer(CatalogScaffoldModel):
    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.PLANNED
    advisory_only = True
    catalog_name = "deal_loss_scorer"

    async def _count_labeled_deals(self, org_id: str, settings: Settings) -> int:
        client = get_supabase_client(settings)
        try:
            resp = (
                client.table("agent_action_outcomes")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("target_entity_type", "deal")
                .not_.is_("measured_at", "null")
                .execute()
            )
            return int(resp.count or 0)
        except Exception:  # noqa: BLE001
            return 0

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        org_id = str(kwargs.get("org_id") or "")
        settings = kwargs.get("settings") or get_settings()
        count = await self._count_labeled_deals(org_id, settings) if org_id else 0
        return {
            "status": "not_available",
            "model": self.catalog_name,
            "reason": (
                f"PLANNED — requires {MIN_DEAL_LOSS_LABELS}+ measured deal outcomes "
                "(won/lost) from CRM attribution windows."
            ),
            "data_gate": {
                "current": count,
                "required": MIN_DEAL_LOSS_LABELS,
                "met": count >= MIN_DEAL_LOSS_LABELS,
            },
            "fallback": "stalled_deal correlational detector",
            "advisory_only": True,
        }


class CapacityForecaster(CatalogScaffoldModel):
    model_type = ModelType.REGRESSOR
    catalog_status = ModelStatus.PLANNED
    advisory_only = True
    catalog_name = "capacity_forecaster"

    async def _count_capacity_series(self, org_id: str, settings: Settings) -> int:
        client = get_supabase_client(settings)
        try:
            resp = (
                client.table("agent_action_outcomes")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("metric_name", "ticket_volume")
                .execute()
            )
            return int(resp.count or 0)
        except Exception:  # noqa: BLE001
            return 0

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        org_id = str(kwargs.get("org_id") or "")
        settings = kwargs.get("settings") or get_settings()
        count = await self._count_capacity_series(org_id, settings) if org_id else 0
        return {
            "status": "not_available",
            "model": self.catalog_name,
            "reason": (
                f"PLANNED — requires {MIN_CAPACITY_SERIES}+ daily capacity/ticket volume "
                "observations before forecasting."
            ),
            "data_gate": {
                "current": count,
                "required": MIN_CAPACITY_SERIES,
                "met": count >= MIN_CAPACITY_SERIES,
            },
            "fallback": "business_digital_twin support_capacity domain",
            "advisory_only": True,
        }
