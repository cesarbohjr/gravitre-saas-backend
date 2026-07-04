"""BE-00: Structured logging with request_id, user_id, org_id."""
import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="")
org_id_ctx: ContextVar[str] = ContextVar("org_id", default="")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        extra = getattr(record, "__dict__", {})
        for key in ("request_id", "user_id", "org_id", "event_type"):
            value = extra.get(key)
            if value:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class StructuredLogger(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.get("extra") or {}
        extra.setdefault("request_id", request_id_ctx.get())
        extra.setdefault("user_id", user_id_ctx.get())
        extra.setdefault("org_id", org_id_ctx.get())
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(level: str | None = None) -> None:
    """Configure root logging once at startup."""
    log_level = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    use_json = (os.environ.get("LOG_FORMAT") or "").strip().lower() == "json"
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level)
    handler = logging.StreamHandler(sys.stdout)
    if use_json:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s request_id=%(request_id)s "
                "user_id=%(user_id)s org_id=%(org_id)s %(message)s",
                defaults={"request_id": "", "user_id": "", "org_id": ""},
            )
        )
    root.addHandler(handler)
    for name in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> StructuredLogger:
    base = logging.getLogger(name)
    if not base.handlers and not logging.getLogger().handlers:
        setup_logging()
    return StructuredLogger(base, {})
