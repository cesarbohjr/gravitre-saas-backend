"""Operator package: repository imports must not eagerly initialize HTTP routes."""
from __future__ import annotations

from importlib import import_module

__all__ = ["router"]


def __getattr__(name: str):
    # Preserve `from app.operators import router` and attribute access while
    # allowing workflow services to import repositories during initialization.
    if name == "router":
        router = import_module("app.operators.router")
        globals()[name] = router
        return router
    raise AttributeError(name)
