"""Phase D — structured AssistantResponse blocks (metrics, trends, prose)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.safe_dict import safe_normalize_stored_dict

BlockType = Literal["metrics", "trend", "prose", "callout"]


@dataclass(frozen=True)
class ResponseBlock:
    type: BlockType
    title: str
    lines: tuple[str, ...] = ()
    metrics: tuple[tuple[str, str, str | None], ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "title": self.title,
            "lines": list(self.lines),
            "metrics": [
                {"label": label, "value": value, "change": change}
                for label, value, change in self.metrics
            ],
            "meta": dict(self.meta),
        }


def blocks_from_execution_observations(
    observations: list[dict[str, Any] | Any] | None,
) -> list[ResponseBlock]:
    blocks: list[ResponseBlock] = []
    for row in observations or []:
        if isinstance(row, dict):
            connector_id = str(row.get("connector_id") or "")
            summary = str(row.get("summary") or "")
            structured = row.get("structured") if isinstance(row.get("structured"), dict) else {}
            success = bool(row.get("success"))
        else:
            connector_id = str(getattr(row, "connector_id", "") or "")
            summary = str(getattr(row, "summary", "") or "")
            structured = getattr(row, "structured", {}) or {}
            success = bool(getattr(row, "success", False))
        if not success:
            continue
        metrics: list[tuple[str, str, str | None]] = []
        if connector_id == "google_analytics":
            users = structured.get("active_users")
            sessions = structured.get("sessions")
            if users is not None:
                metrics.append(("Active users", f"{int(users):,}", None))
            if sessions is not None:
                metrics.append(("Sessions", f"{int(sessions):,}", None))
        elif connector_id == "google_search_console":
            page = structured.get("top_page")
            clicks = structured.get("top_clicks")
            if page:
                metrics.append(("Top page", str(page), None))
            if clicks is not None:
                metrics.append(("Clicks (28d)", f"{int(clicks):,}", None))
        if metrics:
            title = "Google Analytics" if connector_id == "google_analytics" else "Search Console"
            blocks.append(ResponseBlock(type="metrics", title=title, metrics=tuple(metrics)))
        elif summary:
            blocks.append(ResponseBlock(type="prose", title=connector_id.replace("_", " ").title(), lines=(summary,)))
    return blocks


def blocks_from_ga4_reports(
    *,
    property_name: str,
    current: dict[str, Any],
    previous: dict[str, Any],
    timeframe_label: str | None = None,
) -> list[ResponseBlock]:
    from app.services.analytics_traffic_overview_service import _metric_total, _pct_change

    metrics: list[tuple[str, str, str | None]] = []
    for key, label in (
        ("activeUsers", "Active users"),
        ("sessions", "Sessions"),
        ("screenPageViews", "Views"),
    ):
        cur = _metric_total(current, key)
        prev = _metric_total(previous, key)
        if cur is None:
            continue
        change = _pct_change(cur, prev)
        metrics.append((label, f"{int(cur):,}", change))
    if not metrics:
        return []
    return [
        ResponseBlock(
            type="metrics",
            title=f"{property_name} ({timeframe_label or 'last 30 days'})",
            metrics=tuple(metrics),
            meta={"source": "google_analytics"},
        )
    ]


def render_response_blocks(blocks: list[ResponseBlock]) -> str:
    parts: list[str] = []
    for block in blocks:
        if block.title:
            parts.append(f"**{block.title}**")
        for label, value, change in block.metrics:
            suffix = f" ({change})" if change else ""
            parts.append(f"- **{label}:** {value}{suffix}")
        for line in block.lines:
            parts.append(line)
        parts.append("")
    return "\n".join(parts).strip()


def blocks_from_dicts(raw: list[Any] | None) -> list[ResponseBlock]:
    out: list[ResponseBlock] = []
    for row in raw or []:
        if not isinstance(row, dict):
            continue
        metrics = tuple(
            (str(m.get("label") or ""), str(m.get("value") or ""), m.get("change"))
            for m in (row.get("metrics") or [])
            if isinstance(m, dict)
        )
        out.append(
            ResponseBlock(
                type=row.get("type") or "prose",
                title=str(row.get("title") or ""),
                lines=tuple(str(x) for x in (row.get("lines") or [])),
                metrics=metrics,
                meta=safe_normalize_stored_dict(row.get("meta")),
            )
        )
    return out


def merge_blocks_with_prose(blocks: list[ResponseBlock], prose: str) -> str:
    rendered = render_response_blocks(blocks)
    body = (prose or "").strip()
    if rendered and body:
        return f"{rendered}\n\n{body}"
    return rendered or body
