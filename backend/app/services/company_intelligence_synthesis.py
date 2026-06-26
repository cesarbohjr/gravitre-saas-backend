"""Markdown synthesis for learned company intelligence prompt blocks."""
from __future__ import annotations

from typing import Any

_MAX_CHARS = 4000


def synthesize_company_intelligence(
    *,
    category_distribution: dict[str, int],
    recent_anomalies: list[dict[str, Any]] | None = None,
    forecast_summary: list[dict[str, Any]] | None = None,
    success_predictions: list[dict[str, Any]] | None = None,
    memory_digest: list[dict[str, Any]] | None = None,
    org_deltas: dict[str, Any] | None = None,
    knowledge_gaps: list[dict[str, Any]] | None = None,
    glossary_terms: list[dict[str, Any]] | None = None,
) -> str:
    sections: list[str] = []

    if category_distribution:
        top = sorted(category_distribution.items(), key=lambda item: item[1], reverse=True)[:5]
        lines = [f"- {cat}: {count} queries" for cat, count in top]
        sections.append("### Recurring query themes (last 90 days)\n" + "\n".join(lines))

    anomalies = [a for a in (recent_anomalies or []) if a.get("is_anomaly")]
    if anomalies:
        lines = []
        for item in anomalies[:3]:
            metrics = item.get("metrics") or {}
            reason = item.get("reason") or "unusual workflow run pattern"
            lines.append(f"- {reason} (score={item.get('anomaly_score', 0):.2f})")
        sections.append("### Recent workflow anomalies\n" + "\n".join(lines))

    if forecast_summary:
        lines = []
        for item in forecast_summary[:2]:
            ts = item.get("timestamp") or "upcoming"
            pred = item.get("predicted_duration_ms")
            interval = item.get("confidence_interval") or {}
            if pred is not None:
                lines.append(
                    f"- {ts}: ~{int(float(pred) / 1000)}s expected duration "
                    f"(range {int(float(interval.get('lower_bound', pred)) / 1000)}–"
                    f"{int(float(interval.get('upper_bound', pred)) / 1000)}s)"
                )
        if lines:
            sections.append("### Workflow duration outlook\n" + "\n".join(lines))

    at_risk = sorted(
        success_predictions or [],
        key=lambda row: float(row.get("success_probability") or 1.0),
    )
    if at_risk:
        lines = []
        for item in at_risk[:2]:
            wf_id = item.get("workflow_id") or "workflow"
            prob = float(item.get("success_probability") or 0.0)
            if prob >= 0.5:
                continue
            lines.append(f"- Workflow {wf_id}: elevated failure risk ({prob:.0%} predicted success)")
        if lines:
            sections.append("### Workflows at elevated failure risk\n" + "\n".join(lines))

    if memory_digest:
        lines = [f"- ({row.get('category')}) {str(row.get('content') or '')[:120]}" for row in memory_digest[:3]]
        sections.append("### Frequently used agent memories\n" + "\n".join(lines))

    deltas = org_deltas or {}
    delta_bits: list[str] = []
    failed = int(deltas.get("failed_workflows") or 0)
    if failed:
        delta_bits.append(f"{failed} workflow failure(s) in the last 24h")
    pending = int(deltas.get("pending_auth_connectors") or 0)
    if pending:
        delta_bits.append(f"{pending} connector(s) need authentication")
    if delta_bits:
        sections.append("### Recent operational changes\n" + "\n".join(f"- {bit}" for bit in delta_bits))

    open_gaps = [g for g in (knowledge_gaps or []) if g.get("status") == "open"]
    if open_gaps:
        lines = []
        for gap in open_gaps[:3]:
            desc = str(gap.get("description") or "").strip()
            suggestion = str(gap.get("suggested_content") or "").strip()
            if desc:
                line = f"- {desc}"
                if suggestion:
                    line += f" Suggestion: {suggestion[:160]}"
                lines.append(line)
        if lines:
            sections.append("### Knowledge gaps (failed search clusters)\n" + "\n".join(lines))

    top_glossary = sorted(
        glossary_terms or [],
        key=lambda row: int(row.get("frequency") or 0),
        reverse=True,
    )
    if top_glossary:
        lines = []
        for term in top_glossary[:3]:
            label = str(term.get("term") or "")
            dept = term.get("associated_department")
            if not label:
                continue
            suffix = f" ({dept})" if dept else ""
            lines.append(f"- {label}{suffix}")
        if lines:
            sections.append("### Company vocabulary (candidate terms)\n" + "\n".join(lines))

    if not sections:
        return ""

    body = "\n\n".join(sections)
    if len(body) > _MAX_CHARS:
        body = body[: _MAX_CHARS - 3].rstrip() + "..."
    return body
