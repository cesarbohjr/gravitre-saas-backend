from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context
from app.core.logging import get_logger
from app.services.model_router import TaskType, get_model_router
from app.services.rag_service import get_rag_service

router = APIRouter(prefix="/api", tags=["ai-system"])
logger = get_logger(__name__)


class TestAIRequest(BaseModel):
    prompt: str = Field(default="Say hello from Gravitre", min_length=1)


class TestRAGRequest(BaseModel):
    query: str = Field(default="What do we know about workflow failures?", min_length=1)


class TestAgentRequest(BaseModel):
    task: str = Field(default="Diagnose sync failures and propose next steps", min_length=1)


@router.post("/test-ai")
async def test_ai_route(
    body: TestAIRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
) -> dict[str, Any]:
    key_present = bool((os.getenv("OPENAI_API_KEY") or "").strip())
    if not key_present:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured",
        )
    model_router = get_model_router()
    try:
        response = await model_router.complete(
            task_type=TaskType.CONTENT_GENERATION,
            prompt=body.prompt,
            system_prompt="You are Gravitre AI.",
            org_id=org_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("test-ai fallback org_id=%s error=%s", org_id, str(exc))
        return {
            "status": "ok",
            "response": "Hello from Gravitre",
            "taskType": TaskType.CONTENT_GENERATION.value,
            "model": "gpt-4.1",
            "keyPresent": key_present,
            "fallback": True,
        }
    return {
        "status": "ok",
        "response": response.content,
        "taskType": TaskType.CONTENT_GENERATION.value,
        "model": response.model,
        "keyPresent": key_present,
        "fallback": False,
    }


@router.post("/test-rag")
async def test_rag_route(
    body: TestRAGRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    rag_service = get_rag_service()
    try:
        result = await rag_service.query(org_id=org_id, query=body.query, top_k=5)
    except Exception as exc:  # noqa: BLE001
        logger.warning("test-rag fallback org_id=%s error=%s", org_id, str(exc))
        return {
            "status": "ok",
            "response": "RAG pipeline reachable but no indexed data is currently available.",
            "chunks": [],
            "fallback": True,
        }
    if not result.chunks:
        return {
            "status": "ok",
            "response": "No indexed context found yet. Ingest documents to enable grounded answers.",
            "chunks": [],
            "fallback": True,
        }
    return {
        "status": "ok",
        "response": result.answer,
        "chunks": [chunk.model_dump() for chunk in result.chunks],
        "metrics": result.metrics,
        "fallback": False,
    }


@router.post("/test-agent")
async def test_agent_route(
    body: TestAgentRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
) -> dict[str, Any]:
    model_router = get_model_router()
    prompt = (
        "Generate a short execution plan in JSON with keys: summary, steps, risk.\n"
        f"Task: {body.task}\n"
        "Keep it concise and operational."
    )
    try:
        result = await model_router.complete(
            task_type=TaskType.WORKFLOW_PLANNING,
            prompt=prompt,
            system_prompt="You are Gravitre AI Operator.",
            org_id=org_id,
        )
        return {
            "status": "ok",
            "agent": {
                "summary": result.content,
                "simulated": False,
                "model": result.model,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("test-agent simulated fallback error=%s", str(exc))
        return {
            "status": "ok",
            "agent": {
                "summary": "Generated fallback operator plan: inspect run logs, retry connector action, notify owner.",
                "steps": ["Inspect latest failed run", "Retry once with backoff", "Escalate if failure persists"],
                "risk": "medium",
                "simulated": True,
            },
        }
