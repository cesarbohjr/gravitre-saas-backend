from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

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
        return (
            str(detail.get("error") or "Request failed"),
            str(detail.get("code") or "VALIDATION_ERROR"),
            detail.get("details") or {},
        )
    message = str(detail or "Request failed")
    code = "VALIDATION_ERROR"
    return message, code, {}


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    message, code, details = _normalize_detail(exc.detail)
    code = ERROR_CODE_BY_STATUS.get(exc.status_code, code)
    payload = {
        "success": False,
        "error": message,
        "code": code,
        "details": details,
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
