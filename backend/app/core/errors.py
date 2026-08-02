from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.config import SettingsNotConfiguredError

ERROR_CODE_BY_STATUS = {
    status.HTTP_400_BAD_REQUEST: "VALIDATION_ERROR",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "UNAUTHORIZED",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "VALIDATION_ERROR",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
}


def error_detail(message: str, code: str, details: dict | None = None) -> dict:
    return {
        "error": message,
        "code": code,
        "details": details or {},
    }


def _normalize_detail(detail: Any) -> tuple[str, str, dict]:
    if isinstance(detail, dict) and "code" in detail and "error" in detail:
        nested = detail.get("details") if isinstance(detail.get("details"), dict) else {}
        extras = {
            key: value
            for key, value in detail.items()
            if key not in {"error", "code", "details", "message"} and value is not None
        }
        return (
            str(detail.get("error") or "Request failed"),
            str(detail.get("code") or "VALIDATION_ERROR"),
            {**extras, **(nested or {})},
        )
    if isinstance(detail, dict):
        # Structured HTTPException detail (e.g. active_run_conflict_detail).
        # Never str(dict) — that becomes a Python repr toast in the UI.
        raw_message = detail.get("message") or detail.get("detail") or detail.get("error")
        message = str(raw_message).strip() if raw_message is not None else ""
        if not message:
            message = "Request failed"
        nested = detail.get("details") if isinstance(detail.get("details"), dict) else {}
        extras = {
            key: value
            for key, value in detail.items()
            if key not in {"message", "detail", "error", "code", "details"} and value is not None
        }
        code = str(detail.get("code") or "VALIDATION_ERROR")
        return message, code, {**extras, **(nested or {})}
    if isinstance(detail, list):
        first = detail[0] if detail else None
        if isinstance(first, dict):
            msg = first.get("msg") or first.get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip(), "VALIDATION_ERROR", {"errors": detail}
        return "Validation error", "VALIDATION_ERROR", {"errors": detail}
    message = str(detail or "Request failed")
    code = "VALIDATION_ERROR"
    return message, code, {}


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 402 and isinstance(exc.detail, dict) and exc.detail.get("error") in {
        "plan_required",
        "plan_limit_exceeded",
    }:
        return JSONResponse(status_code=402, content=exc.detail)
    message, code, details = _normalize_detail(exc.detail)
    code = ERROR_CODE_BY_STATUS.get(exc.status_code, code)
    # Keep FastAPI-shaped `detail` for clients that read active_run_id there,
    # plus flat `error` for toast copy.
    detail_out: Any = message
    if details:
        detail_out = {"message": message, **details}
    payload = {
        "success": False,
        "error": message,
        "code": code,
        "details": details,
        "detail": detail_out,
    }
    return JSONResponse(status_code=exc.status_code, content=payload)


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    payload = {
        "success": False,
        "error": "Validation error",
        "code": "VALIDATION_ERROR",
        "details": {"errors": exc.errors()},
    }
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)


async def settings_not_configured_handler(_: Request, exc: SettingsNotConfiguredError) -> JSONResponse:
    payload = {
        "success": False,
        "error": "Backend configuration is incomplete",
        "code": "CONFIGURATION_ERROR",
        "details": {"missing": exc.missing_fields},
    }
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)
