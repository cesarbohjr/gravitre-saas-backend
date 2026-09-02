"""Per-org Gravitre Intelligence Engine settings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


@dataclass(frozen=True)
class IntelligenceEngineSettings:
    validation_enabled: bool = True
    reranking_enabled: bool = True
    confidence_threshold: float = 0.4
    max_chunks: int = 8
    connector_timeout_seconds: int = 30
    performance_mode: str = "balanced"
    standing_investigators_enabled: bool = True


DEFAULTS = IntelligenceEngineSettings()
PERFORMANCE_MODES = frozenset({"speed_priority", "balanced", "accuracy_priority"})


def tier0_enabled(settings: IntelligenceEngineSettings) -> bool:
    return settings.performance_mode != "accuracy_priority"


def tier0_ttl_seconds(settings: IntelligenceEngineSettings) -> int:
    if settings.performance_mode == "speed_priority":
        return 7200
    return 3600


def validation_enabled_for_mode(mode_key: str, settings: IntelligenceEngineSettings) -> bool:
    if not settings.validation_enabled:
        return False
    if settings.performance_mode == "accuracy_priority":
        return mode_key in {"fast", "standard", "reasoning", "agent"}
    if settings.performance_mode == "speed_priority":
        return mode_key in {"reasoning", "agent"}
    # agent is included, on the second attempt and for a different reason than
    # the first. History, because it explains the shape of the fix:
    #
    #   1e94e644 included agent while the validator could only see RAG chunks.
    #   Measured live: p50 9309ms / p95 10131ms added against a 3123ms
    #   generation baseline, and 3 of 3 agent answers REPLACED, one landing on
    #   SAFE_FALLBACK (docs/delivery/grounding-validator-latency.json).
    #   Reverted the same day.
    #
    # That failure was structural, not tuning. agent mode is where answers come
    # from TOOLS while RAG chunks are incidentally present, so a RAG-only
    # validator compared a tool-derived conclusion against unrelated knowledge
    # chunks and correctly found it unsupported.
    #
    # The validator is now tool-aware: executed tool results are first-class
    # evidence alongside retrieved documents, and the regeneration path sees the
    # same evidence (app/services/answer_validator.py:build_evidence). A
    # tool-derived answer now has something real to be grounded against.
    #
    # Excluding agent was not a small gap. resolve_effective_intelligence_mode
    # upgrades BOTH standard and reasoning to agent whenever a connector is
    # connected, and leaves fast as fast, so a connector-connected org can only
    # reach {fast, agent} — grounding validation was unreachable for every org
    # with a connector. That is why Cesar's decision was to build the
    # tool-aware validator rather than accept the exclusion.
    return mode_key in {"standard", "reasoning", "agent"}


async def load_intelligence_engine_settings(
    org_id: str,
    settings: Any,
    *,
    client: Any | None = None,
) -> IntelligenceEngineSettings:
    db = client or get_supabase_client(settings)
    try:
        result = db.table("org_intelligence_engine_settings").select("*").eq("org_id", org_id).limit(1).execute()
        if result.data:
            row = result.data[0]
            return IntelligenceEngineSettings(
                validation_enabled=bool(row.get("validation_enabled", True)),
                reranking_enabled=bool(row.get("reranking_enabled", True)),
                confidence_threshold=float(row.get("confidence_threshold") or DEFAULTS.confidence_threshold),
                max_chunks=int(row.get("max_chunks") or DEFAULTS.max_chunks),
                connector_timeout_seconds=int(
                    row.get("connector_timeout_seconds") or DEFAULTS.connector_timeout_seconds
                ),
                performance_mode=str(row.get("performance_mode") or DEFAULTS.performance_mode),
                standing_investigators_enabled=bool(
                    row.get("standing_investigators_enabled", True)
                    if row.get("standing_investigators_enabled") is not None
                    else True
                ),
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("intelligence engine settings load skipped org_id=%s error=%s", org_id, exc)
    return DEFAULTS


async def save_intelligence_engine_settings(
    org_id: str,
    settings: Any,
    payload: dict[str, Any],
    *,
    client: Any | None = None,
) -> IntelligenceEngineSettings:
    db = client or get_supabase_client(settings)
    current = await load_intelligence_engine_settings(org_id, settings, client=db)
    row = {
        "org_id": org_id,
        "validation_enabled": bool(payload.get("validation_enabled", current.validation_enabled)),
        "reranking_enabled": bool(payload.get("reranking_enabled", current.reranking_enabled)),
        "confidence_threshold": float(
            payload.get("confidence_threshold", current.confidence_threshold)
        ),
        "max_chunks": int(payload.get("max_chunks", current.max_chunks)),
        "connector_timeout_seconds": int(
            payload.get("connector_timeout_seconds", current.connector_timeout_seconds)
        ),
        "performance_mode": str(payload.get("performance_mode", current.performance_mode)),
        "standing_investigators_enabled": bool(
            payload.get(
                "standing_investigators_enabled",
                current.standing_investigators_enabled,
            )
        ),
    }
    row["confidence_threshold"] = max(0.0, min(1.0, row["confidence_threshold"]))
    row["max_chunks"] = max(1, min(50, row["max_chunks"]))
    row["connector_timeout_seconds"] = max(5, min(300, row["connector_timeout_seconds"]))
    if row["performance_mode"] not in PERFORMANCE_MODES:
        row["performance_mode"] = DEFAULTS.performance_mode
    db.table("org_intelligence_engine_settings").upsert(row, on_conflict="org_id").execute()
    return IntelligenceEngineSettings(**{k: v for k, v in row.items() if k != "org_id"})
