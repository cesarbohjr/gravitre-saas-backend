"""Governed CodeAct — sandboxed transform/glue logic for agent turns (Tier 3)."""
from __future__ import annotations

import re
from types import MappingProxyType
from typing import Any

from app.connectors.private.sandbox_runner import FORBIDDEN_NAMES, SAFE_BUILTINS
from app.core.logging import get_logger

logger = get_logger(__name__)

_MAX_CODE_CHARS = 8_000
_MAX_INPUT_JSON_CHARS = 100_000

_IMPORT_PATTERN = re.compile(r"^\s*(?:from|import)\s+", re.MULTILINE)


class GovernedCodeActError(ValueError):
    """Raised when governed code execution is rejected or fails."""


class GovernedCodeActService:
    """Execute short Python transforms over JSON inputs inside a restricted namespace."""

    def validate_code(self, code: str) -> None:
        source = (code or "").strip()
        if not source:
            raise GovernedCodeActError("Code is required")
        if len(source) > _MAX_CODE_CHARS:
            raise GovernedCodeActError(f"Code exceeds {_MAX_CODE_CHARS} characters")
        lowered = source.lower()
        for name in FORBIDDEN_NAMES:
            if name in lowered:
                raise GovernedCodeActError(f"Forbidden construct: {name}")
        if _IMPORT_PATTERN.search(source):
            raise GovernedCodeActError("Imports are not allowed")

    def execute_transform(
        self,
        *,
        code: str,
        inputs: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Run user code that must assign a ``result`` variable."""
        self.validate_code(code)
        data = dict(inputs or {})
        serialized = str(data)
        if len(serialized) > _MAX_INPUT_JSON_CHARS:
            raise GovernedCodeActError("Input payload too large")

        namespace: dict[str, Any] = {
            "__builtins__": MappingProxyType(SAFE_BUILTINS),
            "data": data,
            "inputs": data,
            "result": None,
        }
        try:
            exec(compile(code, "<governed_codeact>", "exec"), namespace, namespace)  # noqa: S102
        except Exception as exc:  # noqa: BLE001
            logger.debug("governed_codeact_exec_failed desc=%s err=%s", description, exc)
            raise GovernedCodeActError(f"Transform failed: {exc}") from exc

        result = namespace.get("result")
        if result is None:
            raise GovernedCodeActError("Code must assign a `result` variable")

        preview = repr(result)
        if len(preview) > 500:
            preview = preview[:497] + "..."
        return {
            "success": True,
            "description": (description or "").strip() or None,
            "result": result,
            "preview": preview,
            "inputKeys": sorted(data.keys()),
        }


_service: GovernedCodeActService | None = None


def get_governed_codeact_service() -> GovernedCodeActService:
    global _service
    if _service is None:
        _service = GovernedCodeActService()
    return _service
