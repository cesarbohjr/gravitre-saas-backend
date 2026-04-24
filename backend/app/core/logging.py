"""BE-00: Structured logging with request_id, user_id, org_id."""
import logging
import sys
from contextvars import ContextVar
from typing import Any

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="")
org_id_ctx: ContextVar[str] = ContextVar("org_id", default="")


class StructuredLogger(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.get("extra") or {}
        extra.setdefault("request_id", request_id_ctx.get())
        extra.setdefault("user_id", user_id_ctx.get())
        extra.setdefault("org_id", org_id_ctx.get())
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> StructuredLogger:
    base = logging.getLogger(name)
    if not base.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s request_id=%(request_id)s user_id=%(user_id)s org_id=%(org_id)s %(message)s"
            )
        )
        base.addHandler(h)
        base.setLevel(logging.INFO)
    return StructuredLogger(base, {})
