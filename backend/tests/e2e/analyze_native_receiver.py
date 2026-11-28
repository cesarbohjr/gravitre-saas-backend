#!/usr/bin/env python3
"""Analyze native receiver buffering from raw paired trials; never certify from averages."""
import json
import math
import statistics
import sys
from pathlib import Path

def percentile(values, q):
    a = sorted(v for v in values if isinstance(v, (int, float)) and math.isfinite(v))
    return a[math.ceil(q * len(a)) - 1] if a else None

def analyze_trial(trial):
    snapshots = sorted(trial.get("receiverSnapshots", []), key=lambda s: s.get("perfMs", 0))
    interrupt = trial.get("interruptPerfMs")
    windows = []
    for a, b in zip(snapshots, snapshots[1:]):
        if a.get("id") != b.get("id"):
            continue
        emitted = b.get("emitted", 0) - a.get("emitted", 0)
        delay = b.get("delay", 0) - a.get("delay", 0)
        target = b.get("target", 0) - a.get("target", 0)
        if emitted <= 0 or delay < 0 or target < 0:
            continue
        windows.append({"fromPerfMs": a["perfMs"], "toPerfMs": b["perfMs"],
                        "meanResidenceMs": 1000 * delay / emitted,
                        "meanTargetMs": 1000 * target / emitted,
                        "emittedCountDelta": emitted})
    around = [w for w in windows if isinstance(interrupt, (int, float))
              and w["fromPerfMs"] <= interrupt + 350 and w["toPerfMs"] >= interrupt - 100]
    server = trial.get("server", [])
    offset = (trial.get("clockSync") or {}).get("offsetMs")
    commit = next((e for e in server if e.get("boundary") == "marker_committed" and e.get("marker") == 2), None)
    recognition = (commit["monotonicMs"] - offset - interrupt
                   if commit and isinstance(offset, (int, float)) and isinstance(interrupt, (int, float)) else None)
    return {"repeat": trial.get("repeat"), "early": trial.get("early"),
            "recognitionMs": recognition, "receiverWindowCount": len(around),
            "receiverResidenceMs": percentile([w["meanResidenceMs"] for w in around], .5),
            "receiverTargetMs": percentile([w["meanTargetMs"] for w in around], .5),
            "receiverWindows": around, "residualMs": trial.get("interruptResidualMs"),
            "workletResidualMs": (trial.get("workletMetrics") or {}).get("interruptResidualMs")}

def main():
    source = Path(sys.argv[1])
    data = json.loads(source.read_text())
    trials = data.get("trials", [])
    if len(trials) != 40 or {t.get("repeat") for t in trials} != set(range(1, 21)):
        raise SystemExit("invalid 40-trial fixture")
    for repeat in range(1, 21):
        if sorted(str(t.get("early")) for t in trials if t.get("repeat") == repeat) != ["False", "True"]:
            raise SystemExit("missing matched control/candidate pair")
    rows = [analyze_trial(t) for t in trials]
    summary = {}
    for mode in (False, True):
        subset = [r for r in rows if r["early"] is mode]
        summary[str(mode)] = {field: {"valid": sum(isinstance(r[field], (int, float)) for r in subset),
                                       "p50": percentile([r[field] for r in subset], .5),
                                       "p95": percentile([r[field] for r in subset], .95)}
                              for field in ("recognitionMs", "receiverResidenceMs", "receiverTargetMs",
                                            "residualMs", "workletResidualMs")}
    result = {"sourceSha": data.get("sourceSha"), "synthetic": True, "trialCount": 40,
              "method": "per-snapshot same-SSRC cumulative delta; window estimate, not exact speaker playout",
              "summary": summary, "trials": rows, "promotionEligible": False}
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("native-onset-receiver-analysis.json")
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
