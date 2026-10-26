#!/usr/bin/env python3
"""Read-only deletion go-live step 8: sample Railway lifecycle readiness.

Run from an authenticated Railway CLI context linked to the backend service and
production environment. Do not provide or echo INTERNAL_API_SECRET locally;
'railway run' injects the service variable into its child command.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

URL = "https://gravitre-saas-backend-production.up.railway.app/api/internal/ops/ingestion-interlock"
# IMPORTANT: single quotes prevent host-shell interpolation of the secret.
PROBE = 'curl --fail-with-body --silent --show-error --max-time 15 -H "X-Internal-Secret: $INTERNAL_API_SECRET" ' + URL


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicas", type=int, required=True, help="Running backend replicas from Railway")
    parser.add_argument("--calls", type=int, default=8, help="At least 2 times the replica count; default 8")
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    if args.replicas < 1 or args.calls < max(2 * args.replicas, 2) or args.delay < 0:
        parser.error("require replicas >= 1, calls >= 2*replicas, delay >= 0")

    true_count = false_count = errors = 0
    failing = []
    for attempt in range(1, args.calls + 1):
        # Never log the subprocess command, environment, stderr or any credentials.
        proc = subprocess.run(
            ["railway", "run", "--", "sh", "-c", PROBE],
            text=True, capture_output=True, timeout=35, check=False,
        )
        try:
            response = json.loads(proc.stdout)
            if not isinstance(response, dict):
                raise ValueError("not a JSON object")
        except (ValueError, json.JSONDecodeError):
            response = None

        if proc.returncode != 0 or response is None:
            errors += 1
            failing.append({"call": attempt, "error": "probe failed or returned invalid JSON",
                            "exit_code": proc.returncode})
        else:
            runtime = response.get("runtime") or {}
            ok = (response.get("lifecycle_ready") is True
                  and response.get("missing") == []
                  and runtime.get("ready") is True
                  and runtime.get("blockers") == []
                  and runtime.get("relay_task") == "running"
                  and isinstance(runtime.get("heartbeat_age_s"), (float, int))
                  and not isinstance(runtime.get("heartbeat_age_s"), bool)
                  and isinstance(runtime.get("heartbeat_window_s"), (float, int))
                  and runtime["heartbeat_age_s"] >= 0
                  and runtime["heartbeat_age_s"] < runtime["heartbeat_window_s"])
            if ok:
                true_count += 1
            else:
                if response.get("lifecycle_ready") is False:
                    false_count += 1
                errors += response.get("lifecycle_ready") is not False
                failing.append({"call": attempt, "response": response})
        print(f"Call {attempt}/{args.calls}: " +
              ("PASS" if attempt == true_count + false_count + errors and not any(f["call"] == attempt for f in failing) else "FAIL"))
        if attempt < args.calls:
            time.sleep(args.delay)

    report = {
        "replicas": args.replicas, "calls": args.calls,
        "lifecycle_ready_true": true_count,
        "lifecycle_ready_false": false_count,
        "invalid_or_other_failures": errors,
        "failing_responses": failing,
        "result": "PASS" if true_count == args.calls else "FAIL",
        "coverage_limitation": "No replica ID in response; sampling cannot prove every distinct replica was contacted.",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
