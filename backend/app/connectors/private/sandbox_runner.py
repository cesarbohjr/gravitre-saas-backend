"""Isolated subprocess runner for private connector handlers (STA-98).

Executed as ``python -m app.connectors.private.sandbox_runner`` with JSON on stdin.
"""
from __future__ import annotations

import builtins
import json
import sys
from types import MappingProxyType
from typing import Any

FORBIDDEN_NAMES = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
    }
)

SAFE_BUILTINS: dict[str, Any] = {
    name: getattr(builtins, name)
    for name in (
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "float",
        "int",
        "isinstance",
        "len",
        "list",
        "max",
        "min",
        "range",
        "repr",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
    )
}


class SandboxContext:
    """Minimal tool context exposed to private connector handlers."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.org_id = str(payload.get("orgId") or "")
        self.user_id = payload.get("userId")
        self.connector_id = payload.get("connectorId")
        self.run_id = payload.get("runId")


def _validate_source(source: str) -> None:
    lowered = source.lower()
    for name in FORBIDDEN_NAMES:
        if name in lowered:
            raise ValueError(f"Forbidden construct in handler source: {name}")


def _execute_handler(source: str, function_name: str, ctx: SandboxContext, params: dict[str, Any]) -> dict[str, Any]:
    _validate_source(source)
    namespace: dict[str, Any] = {
        "__builtins__": MappingProxyType(SAFE_BUILTINS),
        "SandboxContext": SandboxContext,
    }
    exec(compile(source, "<private_handlers.py>", "exec"), namespace, namespace)  # noqa: S102
    handler = namespace.get(function_name)
    if handler is None or not callable(handler):
        raise ValueError(f"Handler function {function_name!r} not found in handlers.py")
    result = handler(ctx, params)
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump()
    raise ValueError("Handler must return a dict or NormalizedResult-like object")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        source = str(payload.get("handlerSource") or "")
        function_name = str(payload.get("functionName") or "")
        action = str(payload.get("action") or "")
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        ctx = SandboxContext(payload.get("context") or {})
        data = _execute_handler(source, function_name, ctx, params)
        if "action" not in data:
            data["action"] = action
        if "success" not in data:
            data["success"] = True
        json.dump({"ok": True, "result": data}, sys.stdout)
        return 0
    except Exception as exc:  # noqa: BLE001
        json.dump({"ok": False, "error": str(exc)}, sys.stdout)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
