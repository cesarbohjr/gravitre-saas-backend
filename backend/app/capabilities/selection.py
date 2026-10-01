"""Lazy capability selection for portable skills.

Only metadata is retrieved here. Skill instructions/resources may be loaded by
the caller after selection; tool execution is never performed by this module.
"""
from __future__ import annotations

import re
from typing import Any

_STOP = {
    "the","a","an","and","or","to","of","in","for","on","with","from","this","that",
    "use","using","help","me","my","our","your","is","are","be","as","at","it",
}


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9][a-z0-9_-]+", str(value or "").lower())
        if token not in _STOP and len(token) > 2
    }


def select_relevant_packages(
    prompt: str,
    packages: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank installed packages lexically without injecting every skill into context."""
    wanted = _tokens(prompt)
    if not wanted:
        return []
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for package in packages:
        if str(package.get("status") or "") != "installed":
            continue
        inspection = package.get("inspection") if isinstance(package.get("inspection"), dict) else {}
        components = inspection.get("components") if isinstance(inspection.get("components"), list) else []
        haystack = " ".join(
            [
                str(package.get("name") or ""),
                str(package.get("description") or ""),
                " ".join(str(c.get("name") or "") for c in components if isinstance(c, dict)),
            ]
        )
        overlap = wanted & _tokens(haystack)
        if not overlap:
            continue
        score = len(overlap)
        if str(package.get("package_format") or "") == "agent_skill":
            score += 1
        ranked.append((score, str(package.get("name") or ""), package))
    ranked.sort(key=lambda row: (-row[0], row[1].lower()))
    return [row[2] for row in ranked[: max(1, min(limit, 10))]]
