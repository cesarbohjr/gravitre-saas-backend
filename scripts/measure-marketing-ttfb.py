#!/usr/bin/env python3
"""Cold multi-sample TTFB for marketing pages (production or local).

Usage:
  python scripts/measure-marketing-ttfb.py --url https://gravitre.app/pricing
  python scripts/measure-marketing-ttfb.py --url http://127.0.0.1:3000/ --samples 5 --label pricing-before
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLES = 5


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def measure(url: str, samples: int) -> dict[str, Any]:
    values: list[float] = []
    statuses: list[int] = []
    for i in range(samples):
        cache_bust = f"{url}{'&' if '?' in url else '?'}_cb={uuid.uuid4().hex}"
        started = time.perf_counter()
        resp = httpx.get(
            cache_bust,
            headers={
                "Cache-Control": "no-cache, no-store",
                "Pragma": "no-cache",
            },
            follow_redirects=True,
            timeout=60,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        values.append(elapsed_ms)
        statuses.append(resp.status_code)
        # brief gap to avoid single-connection warm reuse dominating
        if i + 1 < samples:
            time.sleep(0.35)

    ordered = sorted(values)
    return {
        "url": url,
        "samples": samples,
        "statuses": statuses,
        "ttfb_ms": {
            "min": round(min(values), 1),
            "p50": round(statistics.median(ordered), 1),
            "p90": round(ordered[max(0, int(len(ordered) * 0.9) - 1)], 1),
            "max": round(max(values), 1),
            "all": [round(v, 1) for v in values],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--label", default="marketing-ttfb")
    parser.add_argument(
        "--out",
        default="",
        help="Output JSON path (default docs/delivery/marketing-ttfb-<label>.json)",
    )
    args = parser.parse_args()

    result = measure(args.url, args.samples)
    payload: dict[str, Any] = {
        "feature": "marketing_ttfb",
        "label": args.label,
        "measured_at": utcnow(),
        **result,
    }
    out_path = Path(args.out) if args.out else ROOT / "docs" / "delivery" / f"marketing-ttfb-{args.label}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**payload, "out": str(out_path)}, indent=2))
    return 0 if all(s == 200 for s in result["statuses"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
