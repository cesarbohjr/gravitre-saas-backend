"""Optional OpenTelemetry tracing for model and agent pipeline calls."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, contextmanager
from typing import Any, TypeVar

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

_tracer = None
_tracer_initialized = False


def _init_tracer() -> Any:
    global _tracer, _tracer_initialized
    if _tracer_initialized:
        return _tracer
    _tracer_initialized = True
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        service_name = os.getenv("OTEL_SERVICE_NAME", "gravitre-intelligence-engine")
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")))
        )
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("gravitre.intelligence")
        logger.info("OpenTelemetry tracing enabled service=%s", service_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenTelemetry tracing unavailable: %s", exc)
        _tracer = None
    return _tracer


def get_tracer() -> Any:
    return _init_tracer()


@contextmanager
def trace_span(name: str, **attributes: Any):
    tracer = get_tracer()
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)
        yield span


@asynccontextmanager
async def trace_span_async(name: str, **attributes: Any):
    with trace_span(name, **attributes) as span:
        yield span


def trace_async(span_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attrs: dict[str, Any] = {}
            if len(args) > 1 and hasattr(args[1], "value"):
                attrs["task_type"] = getattr(args[1], "value", str(args[1]))
            org_id = kwargs.get("org_id")
            if org_id:
                attrs["org_id"] = org_id
            async with trace_span_async(span_name, **attrs):
                return await fn(*args, **kwargs)

        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper

    return decorator
