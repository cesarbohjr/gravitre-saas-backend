"""Per-stage, per-tier voice turn latency percentiles (read-only).

Reads the one-row-per-turn voice traces that
``app.services.turn_latency_trace.record_voice_turn_critical_path`` writes to
``audit_events`` (action ``runtime.turn_latency.critical_path``, metadata
``voice_transport = pipecat_duplex``) for a date range and prints p50/p95/p99
per stage per tier. A percentile is printed only when the stage has enough
samples (p50 >= 5, p95 >= 20, p99 >= 100); otherwise "-".

It only ever SELECTs. ``--input`` reads the same payloads from a JSON-lines
file instead (one metadata object per line), e.g. a synthetic bench's output.

    python scripts/voice_latency_report.py --start 2026-10-01 --end 2026-10-08
    python scripts/voice_latency_report.py --input traces.jsonl --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.turn_latency_trace import AUDIT_ACTION, aggregate_stage_percentiles  # noqa: E402

PAGE_SIZE = 1000
TIER_ORDER = ("light", "medium", "deep", "unknown", "all")
# Headline stages first, in pipeline order; brain checkpoints after.
STAGE_ORDER = (
    "eot_detection_ms",
    "stt_finalization_ms",
    "eager_eot_ms",
    "durable_context_ms",
    "prompt_assembly_ms",
    "moderation_guard_ms",
    "intent_tier_classification_ms",
    "brain_pre_llm_ms",
    "model_ttft_ms",
    "first_speakable_ms",
    "tts_ttfb_ms",
    "server_audio_out_ms",
    "transport_est_ms",
    "browser_playback_startup_ms",
    "speech_end_to_first_token_ms",
    "speech_end_to_server_audio_ms",
    "speech_end_to_playback_ms",
    "observer_e2e_ms",
)


def _parse_day(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def fetch_payloads(
    client: Any,
    *,
    start: datetime,
    end: datetime,
    org_id: str | None = None,
    limit: int = 50_000,
) -> list[dict[str, Any]]:
    """SELECT voice critical-path payloads in [start, end). Read-only, paged."""
    rows: list[dict[str, Any]] = []
    offset = 0
    while len(rows) < limit:
        query = (
            client.table("audit_events")
            .select("metadata,created_at")
            .eq("action", AUDIT_ACTION)
            .eq("metadata->>voice_transport", "pipecat_duplex")
            .gte("created_at", start.isoformat())
            .lt("created_at", end.isoformat())
        )
        if org_id:
            query = query.eq("org_id", org_id)
        page = query.order("created_at").range(offset, offset + PAGE_SIZE - 1).execute().data or []
        rows.extend(r.get("metadata") or {} for r in page if isinstance(r, dict))
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows[:limit]


def read_jsonl(path: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _ordered_stages(stages: Iterable[str]) -> list[str]:
    present = set(stages)
    head = [s for s in STAGE_ORDER if s in present]
    return head + sorted(present - set(head))


def format_table(summary: dict[str, dict[str, dict[str, Any]]], *, include_brain: bool = True) -> str:
    lines: list[str] = []
    for tier in [t for t in TIER_ORDER if t in summary] + sorted(set(summary) - set(TIER_ORDER)):
        per_stage = summary[tier]
        lines.append(f"\n== tier: {tier} ==")
        lines.append(f"{'stage':<40} {'n':>5} {'p50':>7} {'p95':>7} {'p99':>7}")
        for stage in _ordered_stages(per_stage):
            if not include_brain and stage.startswith("brain."):
                continue
            row = per_stage[stage]

            def cell(key: str) -> str:
                return "-" if row.get(key) is None else str(row[key])

            lines.append(f"{stage:<40} {row['n']:>5} {cell('p50'):>7} {cell('p95'):>7} {cell('p99'):>7}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Voice turn latency percentiles (read-only)")
    parser.add_argument("--start", help="Range start, ISO date/time (default: 7 days before --end)")
    parser.add_argument("--end", help="Range end, exclusive (default: now)")
    parser.add_argument("--org", help="Only this org_id")
    parser.add_argument("--input", help="Read payloads from a JSON-lines file instead of the database")
    parser.add_argument("--no-brain", action="store_true", help="Hide per-checkpoint brain.* rows")
    parser.add_argument("--json", action="store_true", help="Print the summary as JSON")
    args = parser.parse_args(argv)

    if args.input:
        payloads = read_jsonl(args.input)
    else:
        from supabase import create_client

        from app.config import get_settings

        end = _parse_day(args.end) if args.end else datetime.now(timezone.utc)
        start = _parse_day(args.start) if args.start else end - timedelta(days=7)
        settings = get_settings()
        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        payloads = fetch_payloads(client, start=start, end=end, org_id=args.org)

    summary = aggregate_stage_percentiles(payloads)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"voice turns: {len(payloads)}")
        print(format_table(summary, include_brain=not args.no_brain))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
