#!/usr/bin/env python3
"""Repeatable voice-latency measurement with an explicit noise floor.

Why this exists. Four separate optimizations were shipped against single-run
numbers in an environment where ``retrieval_gather`` ranged 1,983-49,313ms.
Every conclusion drawn from one sample was worthless, and two of them were
actively wrong: a 1,630ms->0ms stage win produced no end-to-end change, and a
thread-pool "fix" was justified by an assumed 6-worker executor that production
telemetry then reported as 32.

So this harness refuses to report a point estimate alone. It drives N turns,
pairs each with its server-side checkpoint log, and reports a bootstrap 95%
confidence interval on the median. Comparing two labelled runs reports
"indistinguishable" whenever the intervals overlap, because that is the honest
answer far more often than a percentage delta is.

Usage:
  python scripts/measure-voice-latency-harness.py --runs 12 --label before
  python scripts/measure-voice-latency-harness.py --runs 12 --label after
  python scripts/measure-voice-latency-harness.py --compare before after

Credentials from the environment only: SUPABASE_URL, SUPABASE_JWT_SECRET,
ELEVENLABS_API_KEY. Reading server checkpoints additionally needs the `railway`
CLI on PATH.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import json
import math
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _voice_probe_lib import (  # noqa: E402
    ISOLATED_ORG,
    REPO,
    drive_turn,
    service_token,
    synthesize,
)

UTTERANCE = "Did the HubSpot sync finish today?"
SERVICE = "gravitre-saas-backend"
OUT_DIR = REPO / "docs" / "delivery" / "voice-latency-samples"
# Above this the CLI returns "Error in limit - Invalid input" and exits 1.
_MAX_LOG_LINES = 5000

# Server-side checkpoint logs to attribute stage cost from.
_LOG_PATTERNS = {
    "prepare_assistant_turn": re.compile(
        r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ .*?"
        r"prepare_assistant_turn_breakdown_ms .*?org_id=(?P<org>\S+).*?"
        r"checkpoints=(?P<cp>\{[^}]*\})",
        re.S,
    ),
    "agent_intelligence_context": re.compile(
        r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ .*?"
        r"agent_intelligence_context_breakdown_ms .*?org_id=(?P<org>\S+).*?"
        r"checkpoints=(?P<cp>\{[^}]*\})",
        re.S,
    ),
}


def _percentile(values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile; small N makes interpolation false precision."""
    if not values:
        return None
    ordered = sorted(values)
    idx = math.ceil(pct / 100 * len(ordered)) - 1
    return round(ordered[min(len(ordered) - 1, max(0, idx))], 1)


def _median_ci(values: list[float], *, iters: int = 2000, seed: int = 7) -> dict:
    """Bootstrap 95% CI on the median.

    The width of this interval *is* the noise floor: any change smaller than it
    is not measurable with this many samples, no matter how it looks.
    """
    if len(values) < 3:
        return {"median": _percentile(values, 50), "ci95": None, "n": len(values)}
    rng = random.Random(seed)
    n = len(values)
    # Same median definition as the reported point estimate, so the interval and
    # the number it brackets cannot disagree.
    medians = [
        _percentile([rng.choice(values) for _ in range(n)], 50) for _ in range(iters)
    ]
    medians.sort()
    lo = medians[int(0.025 * iters)]
    hi = medians[int(0.975 * iters) - 1]
    return {
        "median": _percentile(values, 50),
        "ci95": [round(lo, 1), round(hi, 1)],
        "ci95_width": round(hi - lo, 1),
        "n": n,
    }


def _summarize(values: list[float]) -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"n": 0}
    out = {
        "n": len(clean),
        "min": round(min(clean), 1),
        "p50": _percentile(clean, 50),
        "p90": _percentile(clean, 90),
        "max": round(max(clean), 1),
        "spread_ratio": round(max(clean) / min(clean), 1) if min(clean) > 0 else None,
    }
    out.update(_median_ci(clean))
    return out


def _fetch_checkpoints(since: datetime, lines: int) -> dict[str, list[dict]]:
    """Parse breakdown logs emitted after ``since`` for the probe org."""
    # Railway rejects large values ("Error in limit - Invalid input") well below
    # what a 12-run pass generates, and it exits 1 with empty stdout when it does.
    capped = max(500, min(int(lines), _MAX_LOG_LINES))
    try:
        proc = subprocess.run(
            ["railway", "logs", "--service", SERVICE, "-n", str(capped)],
            capture_output=True,
            text=True,
            # Logs carry box-drawing and other non-cp1252 bytes; the Windows
            # default codec raises UnicodeDecodeError mid-read without this.
            encoding="utf-8",
            errors="replace",
            timeout=180,
            shell=sys.platform == "win32",
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"[harness] could not run `railway logs`: {exc}") from exc
    blob = proc.stdout or ""
    # Fail loudly. An earlier version swallowed this and printed "turns matched=0",
    # which reads like a measurement rather than a broken fetch.
    if proc.returncode != 0 or not blob.strip():
        raise SystemExit(
            f"[harness] `railway logs -n {capped}` failed (rc={proc.returncode}): "
            f"{(proc.stderr or '').strip()[:200] or 'empty output'}"
        )
    found: dict[str, list[dict]] = {}
    for name, pattern in _LOG_PATTERNS.items():
        rows = []
        for m in pattern.finditer(blob):
            if ISOLATED_ORG not in m.group("org"):
                continue
            try:
                ts = datetime.strptime(m.group("ts"), "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
            if ts < since:
                continue
            try:
                cp = ast.literal_eval(m.group("cp"))
            except Exception:  # noqa: BLE001
                continue
            if isinstance(cp, dict):
                rows.append({"at": ts.isoformat(), "checkpoints": cp})
        found[name] = rows
    return found


def _stage_deltas(rows: list[dict]) -> dict[str, list[float]]:
    """Convert cumulative checkpoints into per-stage costs."""
    per_stage: dict[str, list[float]] = {}
    for row in rows:
        cp = row["checkpoints"]
        prev = 0
        for name, value in cp.items():
            try:
                cur = float(value)
            except (TypeError, ValueError):
                continue
            per_stage.setdefault(name, []).append(round(cur - prev, 1))
            prev = cur
    return per_stage


def _collect(runs: int, label: str) -> dict:
    token = service_token()
    print(f"[harness] synthesizing {UTTERANCE!r}...", flush=True)
    speech = synthesize(UTTERANCE)
    # A minute of slack so the first turn's log is inside the window.
    since = datetime.now(timezone.utc) - timedelta(seconds=30)

    client_runs = []
    for i in range(runs):
        res = asyncio.run(drive_turn(token, speech))
        client_runs.append(res)
        print(
            f"[harness] run {i + 1}/{runs} ok={res.get('ok')} "
            f"first_delta={res.get('first_delta_ms')} "
            f"first_answer={res.get('first_answer_ms')}",
            flush=True,
        )
        time.sleep(2)

    ok = [r for r in client_runs if r.get("ok")]
    print(f"[harness] reading server checkpoints for {len(ok)} good runs...", flush=True)
    checkpoints = _fetch_checkpoints(since, lines=_MAX_LOG_LINES)
    matched = sum(len(rows) for rows in checkpoints.values())
    if ok and not matched:
        # Server-side attribution is the point of the harness; silently returning
        # only client numbers would repeat this phase's core mistake.
        print(
            "[harness] WARNING: no server checkpoints matched. Real traffic can push "
            f"probe lines past the {_MAX_LOG_LINES}-line window -- rerun with fewer "
            "runs, or during a quieter period.",
            flush=True,
        )

    snapshot = {
        "label": label,
        "utterance": UTTERANCE,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "runs_attempted": runs,
        "runs_ok": len(ok),
        "client": {
            "first_delta_ms": _summarize([r.get("first_delta_ms") for r in ok]),
            "first_answer_ms": _summarize([r.get("first_answer_ms") for r in ok]),
            "dead_air_covered_ms": _summarize(
                [r.get("dead_air_covered_ms") for r in ok]
            ),
        },
        "server": {},
        "raw_client_runs": client_runs,
    }
    for name, rows in checkpoints.items():
        snapshot["server"][name] = {
            "n_turns_matched": len(rows),
            "stages": {
                stage: _summarize(vals) for stage, vals in _stage_deltas(rows).items()
            },
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{label}.json"
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"\n[harness] wrote {path}", flush=True)
    return snapshot


def _report(snapshot: dict) -> None:
    print(f"\n=== {snapshot['label']} ===")
    print(f"runs ok: {snapshot['runs_ok']}/{snapshot['runs_attempted']}")
    for metric, stats in snapshot["client"].items():
        if stats.get("n"):
            print(
                f"  {metric}: p50={stats['p50']} p90={stats['p90']} "
                f"ci95={stats.get('ci95')} spread={stats.get('spread_ratio')}x n={stats['n']}"
            )
    for name, block in (snapshot.get("server") or {}).items():
        print(f"  [{name}] turns matched={block['n_turns_matched']}")
        ranked = sorted(
            block["stages"].items(),
            key=lambda kv: kv[1].get("p50") or 0,
            reverse=True,
        )
        for stage, stats in ranked[:6]:
            if stats.get("n"):
                print(
                    f"    {stage}: p50={stats['p50']} p90={stats['p90']} "
                    f"ci95={stats.get('ci95')} n={stats['n']}"
                )


def _compare(a_label: str, b_label: str) -> int:
    paths = [OUT_DIR / f"{lbl}.json" for lbl in (a_label, b_label)]
    for p in paths:
        if not p.exists():
            raise SystemExit(f"missing snapshot: {p}")
    a, b = (json.loads(p.read_text(encoding="utf-8")) for p in paths)

    print(f"\n=== {a_label} vs {b_label} ===")
    print(
        "A change is only claimable when the two 95% intervals do not overlap. "
        "Otherwise the samples cannot tell them apart."
    )

    def _cmp(metric: str, sa: dict, sb: dict) -> None:
        if not (sa.get("ci95") and sb.get("ci95")):
            print(f"  {metric}: too few samples (n={sa.get('n')} vs {sb.get('n')})")
            return
        (alo, ahi), (blo, bhi) = sa["ci95"], sb["ci95"]
        overlap = alo <= bhi and blo <= ahi
        delta = round((sb["median"] or 0) - (sa["median"] or 0), 1)
        verdict = (
            "INDISTINGUISHABLE (inside noise)"
            if overlap
            else ("IMPROVED" if delta < 0 else "REGRESSED")
        )
        print(
            f"  {metric}: {sa['median']} -> {sb['median']} "
            f"(delta {delta:+}ms) {verdict}"
        )
        print(f"      ci95 {sa['ci95']} vs {sb['ci95']}")

    for metric in a.get("client", {}):
        _cmp(metric, a["client"].get(metric, {}), b.get("client", {}).get(metric, {}))
    for name, ablock in (a.get("server") or {}).items():
        bblock = (b.get("server") or {}).get(name) or {}
        for stage, sa in (ablock.get("stages") or {}).items():
            sb = (bblock.get("stages") or {}).get(stage) or {}
            if (sa.get("p50") or 0) >= 200 or (sb.get("p50") or 0) >= 200:
                _cmp(f"{name}.{stage}", sa, sb)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=12)
    ap.add_argument("--label", default=None)
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"), default=None)
    args = ap.parse_args()

    if args.compare:
        return _compare(*args.compare)
    label = args.label or datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    if args.runs < 8:
        print(
            f"[harness] WARNING: {args.runs} runs cannot resolve a 1-2s effect here; "
            "the observed spread has reached 25x. Use >=8.",
            flush=True,
        )
    _report(_collect(args.runs, label))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
