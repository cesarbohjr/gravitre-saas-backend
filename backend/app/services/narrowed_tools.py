"""Standing guard — model tool attachment must pass through narrowing.

G5-RISK-UNNARROWED-FALLTHROUGH: any path that calls the model with tools
must wrap them in ``NarrowedTools`` (produced only by
``narrow_tools_for_turn`` / ``embed_narrow_tools_for_turn``).
"""
from __future__ import annotations

from typing import Any


class NarrowedTools(list):
    """list[tool_def] that carries proof of narrowing for attach-time asserts."""

    gravitre_narrowed: bool = True

    def __init__(
        self,
        tools: list[dict[str, Any]] | None = None,
        *,
        stats: dict[str, Any] | None = None,
        source: str = "narrow_tools_for_turn",
    ) -> None:
        super().__init__(list(tools or []))
        self.stats = dict(stats or {})
        self.source = source
        self.gravitre_narrowed = True

    def as_openai_tools(self) -> list[dict[str, Any]]:
        """Plain list for provider SDKs that reject subclasses."""
        return list(self)


def mark_narrowed(
    tools: list[dict[str, Any]],
    *,
    stats: dict[str, Any] | None = None,
    source: str = "narrow_tools_for_turn",
) -> NarrowedTools:
    if isinstance(tools, NarrowedTools):
        if stats:
            tools.stats = {**(tools.stats or {}), **stats}
        if source:
            tools.source = source
        return tools
    return NarrowedTools(tools, stats=stats, source=source)


def assert_tools_narrowed(tools: list[dict[str, Any]] | None, *, where: str) -> None:
    """Raise if a non-empty tool list was not produced by narrowing."""
    if not tools:
        return
    if getattr(tools, "gravitre_narrowed", False):
        return
    raise RuntimeError(
        f"unnarrowed_tool_attach_blocked at {where}: tools must come from "
        f"narrow_tools_for_turn / embed_narrow_tools_for_turn (NarrowedTools). "
        f"count={len(tools)}"
    )
