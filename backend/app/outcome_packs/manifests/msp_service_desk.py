"""MSP Service Desk Outcome Pack (declared by the Marketplace 3.0 builder)."""
from __future__ import annotations

from typing import Any


def build() -> dict[str, Any]:
    from app.marketplace.marketplace3.msp_service_desk import build_msp_service_desk_outcome_pack_config

    return {
        "marketplace": {
            "slug": "msp-service-desk-3",
            "title": "MSP Service Desk 3.0",
            "department_label": "MSP Service Desk",
            "managed_by": "app.marketplace.marketplace3.msp_service_desk",
        },
        "config": build_msp_service_desk_outcome_pack_config(),
    }
