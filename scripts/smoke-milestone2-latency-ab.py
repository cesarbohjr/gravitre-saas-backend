#!/usr/bin/env python3
"""Milestone 2 — pre/post Research Manager latency A/B on prod.

Playbook (OIL/claim3 pattern):
  1. Brief rollback: deploy pre-RM SHA (09e57595, parent of 4eb6adbe)
  2. Run the same 5 internal-only queries; capture p50/p95
  3. Restore prod tip (latest main)
  4. Re-run queries; report delta (IMPROVED / FLAT / REGRESSION)

Modes:
  --probe-only          Run latency probe against current prod (no Railway deploy)
  --compare A.json B.json  Compare two saved probe JSON files
  --full-ab             Deploy pre-RM, probe, restore tip, probe, compare (needs RAILWAY_TOKEN)

Usage:
  python scripts/smoke-milestone2-latency-ab.py --probe-only --json docs/delivery/m2-latency-post.json
  python scripts/smoke-milestone2-latency-ab.py --compare pre.json post.json
  python scripts/smoke-milestone2-latency-ab.py --full-ab --json docs/delivery/milestone2-latency-ab-latest.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO))

from scripts.milestone2_perf_common import (  # noqa: E402
    ORG_DEFAULT,
    PRE_RM_SHA,
    PROD_DEFAULT,
    RM_MERGE_COMMIT,
    compare_latency,
    fetch_health,
    run_latency_probe,
)
from scripts.railway_prod_deploy import wait_for_health  # noqa: E402


def _load_env() -> dict[str, str]:
    from dotenv import dotenv_values

    merged: dict[str, str] = {}
    for path in (
        BACKEND / ".env",
        BACKEND / ".env.operator.local",
        REPO / ".env.operator.local",
        REPO / ".env",
    ):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in __import__("os").environ.items() if v})
    return merged


def _apply_env() -> dict[str, str]:
    """Load operator.local into os.environ for Option B local runs."""
    env = _load_env()
    for key, value in env.items():
        if value:
            __import__("os").environ.setdefault(key, value)
    return env


def _mint_and_actor(env: dict[str, str], org_id: str) -> tuple[str, str, str]:
    import jwt
    from supabase import create_client
    from scripts.smoke_auth import resolve_smoke_actor_and_email

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    actor, email = resolve_smoke_actor_and_email(client, org_id=org_id, env=env)
    now = int(time.time())
    url = env["SUPABASE_URL"].rstrip("/")
    token = jwt.encode(
        {
            "sub": actor,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    return actor, email, token


def _railway_deploy(commit_sha: str | None, *, latest: bool, wait_health: bool) -> dict[str, Any]:
    cmd = [sys.executable, str(REPO / "scripts/railway_prod_deploy.py")]
    if latest:
        cmd.append("--latest-commit")
    elif commit_sha:
        cmd.extend(["--commit-sha", commit_sha])
    if wait_health:
        cmd.append("--wait-health")
    child_env = {**__import__("os").environ, **_load_env()}
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1200, env=child_env)
    if proc.returncode != 0:
        raise RuntimeError(
            f"railway_prod_deploy failed exit={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return json.loads(proc.stdout)


def run_probe_only(args: argparse.Namespace) -> dict[str, Any]:
    env = _apply_env()
    for key in ("SUPABASE_URL", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
        if not env.get(key):
            raise SystemExit(f"Missing {key}")

    org_id = (args.org_id or env.get("OAUTH_SMOKE_ORG_ID") or ORG_DEFAULT).strip()
    actor, _email, token = _mint_and_actor(env, org_id)
    base_url = (args.base_url or PROD_DEFAULT).rstrip("/")

    report = run_latency_probe(
        base_url=base_url,
        org_id=org_id,
        token=token,
        tag=args.tag,
        include_metrics=args.include_metrics,
    )
    report["actor_id"] = actor
    if args.expected_sha_prefix:
        sha = str(report.get("health_git_sha") or "")
        report["sha_check"] = {
            "expected_prefix": args.expected_sha_prefix,
            "actual": sha,
            "pass": sha.lower().startswith(args.expected_sha_prefix.lower()),
        }
    return report


def run_compare(path_a: Path, path_b: Path) -> dict[str, Any]:
    before = json.loads(path_a.read_text(encoding="utf-8"))
    after = json.loads(path_b.read_text(encoding="utf-8"))
    b_sum = before.get("latency_summary") or {}
    a_sum = after.get("latency_summary") or {}
    delta = compare_latency(b_sum, a_sum)
    return {
        "probe": "milestone2_latency_compare",
        "compared_at": datetime.now(timezone.utc).isoformat(),
        "before_file": str(path_a),
        "after_file": str(path_b),
        "before_git_sha": before.get("health_git_sha"),
        "after_git_sha": after.get("health_git_sha"),
        "before_latency": b_sum,
        "after_latency": a_sum,
        "delta": delta,
        "verdict": "PASS" if delta.get("latency_guardrail_pass") else "FAIL",
        "milestone2_latency_guardrail": delta.get("direction"),
    }


def _finalize_ab_report(
    report: dict[str, Any],
    *,
    pre_probe: dict[str, Any],
    post_probe: dict[str, Any],
) -> dict[str, Any]:
    delta = compare_latency(
        pre_probe.get("latency_summary") or {},
        post_probe.get("latency_summary") or {},
    )
    report["delta"] = delta
    report["before_latency"] = pre_probe.get("latency_summary")
    report["after_latency"] = post_probe.get("latency_summary")
    report["before_git_sha"] = pre_probe.get("health_git_sha")
    report["after_git_sha"] = post_probe.get("health_git_sha")
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["verdict"] = "PASS" if delta.get("latency_guardrail_pass") else "FAIL"
    report["milestone2_latency_guardrail"] = delta.get("direction")
    return report


def run_manual_wait_ab(args: argparse.Namespace) -> dict[str, Any]:
    """Poll prod /health while operator briefly rollbacks/restores via Railway UI."""
    _apply_env()
    base_url = (args.base_url or PROD_DEFAULT).rstrip("/")
    started = datetime.now(timezone.utc).isoformat()
    tip_health = fetch_health(base_url)
    tip_sha = str(tip_health.get("git_sha") or "")

    report: dict[str, Any] = {
        "probe": "milestone2_latency_manual_wait_ab",
        "started_at": started,
        "base_url": base_url,
        "pre_rm_sha_target": PRE_RM_SHA,
        "rm_merge_commit": RM_MERGE_COMMIT,
        "tip_sha_at_start": tip_sha,
        "mode": "manual_railway_rollback",
        "phases": {},
    }

    print(
        "\n=== MANUAL ROLLBACK REQUIRED ===\n"
        f"In Railway dashboard: deploy gravitre-saas-backend @ commit {PRE_RM_SHA}\n"
        "(Project → service → Deployments → redeploy that SHA, or API with project token.)\n"
        f"CI will poll /health until git_sha starts with {PRE_RM_SHA[:8]} (up to 25 min).\n",
        flush=True,
    )
    report["phases"]["wait_pre_rm"] = wait_for_health(
        f"{base_url}/health",
        sha_prefix=PRE_RM_SHA[:8],
        timeout_s=1500,
        poll_s=15,
    )

    print("phase: probe pre-RM", flush=True)
    args_pre = argparse.Namespace(**{**vars(args), "expected_sha_prefix": PRE_RM_SHA[:8], "tag": None})
    pre_probe = run_probe_only(args_pre)
    report["phases"]["probe_pre_rm"] = pre_probe

    print(
        "\n=== RESTORE PROD TIP NOW ===\n"
        "Redeploy latest main on Railway (Deploy Latest Commit / restore current tip).\n"
        f"CI will poll until git_sha is no longer {PRE_RM_SHA[:8]} prefix (up to 25 min).\n",
        flush=True,
    )
    report["phases"]["wait_tip_restore"] = wait_for_health(
        f"{base_url}/health",
        exclude_sha_prefix=PRE_RM_SHA[:8],
        timeout_s=1500,
        poll_s=15,
    )

    print("phase: probe post-RM (current tip)", flush=True)
    post_probe = run_probe_only(args)
    report["phases"]["probe_post_rm"] = post_probe
    return _finalize_ab_report(report, pre_probe=pre_probe, post_probe=post_probe)


def run_full_ab(args: argparse.Namespace) -> dict[str, Any]:
    env = _apply_env()
    if not env.get("RAILWAY_TOKEN"):
        raise SystemExit(
            "RAILWAY_TOKEN required for --full-ab "
            "(set in env or backend/.env.operator.local)"
        )

    base_url = (args.base_url or PROD_DEFAULT).rstrip("/")
    started = datetime.now(timezone.utc).isoformat()
    tip_health = fetch_health(base_url)
    tip_sha = str(tip_health.get("git_sha") or "")

    report: dict[str, Any] = {
        "probe": "milestone2_latency_full_ab",
        "started_at": started,
        "base_url": base_url,
        "pre_rm_sha_target": PRE_RM_SHA,
        "rm_merge_commit": RM_MERGE_COMMIT,
        "tip_sha_at_start": tip_sha,
        "phases": {},
    }

    print("phase: deploy pre-RM", PRE_RM_SHA, flush=True)
    report["phases"]["deploy_pre_rm"] = _railway_deploy(PRE_RM_SHA, latest=False, wait_health=True)

    print("phase: probe pre-RM", flush=True)
    args_pre = argparse.Namespace(**{**vars(args), "expected_sha_prefix": PRE_RM_SHA[:8], "tag": None})
    pre_probe = run_probe_only(args_pre)
    report["phases"]["probe_pre_rm"] = pre_probe

    print("phase: restore prod tip", flush=True)
    report["phases"]["deploy_tip"] = _railway_deploy(None, latest=True, wait_health=True)

    print("phase: probe post-RM (current tip)", flush=True)
    post_probe = run_probe_only(args)
    report["phases"]["probe_post_rm"] = post_probe
    return _finalize_ab_report(report, pre_probe=pre_probe, post_probe=post_probe)


def main() -> int:
    parser = argparse.ArgumentParser(description="Milestone 2 prod latency A/B")
    parser.add_argument("--base-url", default=PROD_DEFAULT)
    parser.add_argument("--org-id", default=None)
    parser.add_argument("--tag", default=None, help="Unique tag embedded in probe messages")
    parser.add_argument("--expected-sha-prefix", default=None)
    parser.add_argument("--include-metrics", action="store_true")
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--full-ab", action="store_true")
    parser.add_argument(
        "--manual-wait-ab",
        action="store_true",
        help="Poll /health while operator rollbacks/restores via Railway UI (no RAILWAY_TOKEN)",
    )
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE_JSON", "AFTER_JSON"))
    parser.add_argument(
        "--json",
        dest="json_path",
        default=str(REPO / "docs/delivery/milestone2-latency-ab-latest.json"),
    )
    args = parser.parse_args()

    if args.compare:
        report = run_compare(Path(args.compare[0]), Path(args.compare[1]))
    elif args.full_ab:
        report = run_full_ab(args)
    elif args.manual_wait_ab:
        report = run_manual_wait_ab(args)
    else:
        report = run_probe_only(args)

    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.json_path:
        out = Path(args.json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"\nWROTE {out}", flush=True)
        if args.full_ab or args.manual_wait_ab:
            pre = (report.get("phases") or {}).get("probe_pre_rm")
            if isinstance(pre, dict) and pre:
                pre_out = out.parent / "milestone2-latency-pre-rm-probe.json"
                pre_out.write_text(json.dumps(pre, indent=2, default=str) + "\n", encoding="utf-8")
                print(f"WROTE {pre_out}", flush=True)

    verdict = report.get("verdict")
    direction = report.get("milestone2_latency_guardrail") or (report.get("delta") or {}).get("direction")
    if verdict:
        print(f"\nVERDICT: {verdict} ({direction or 'probe-only'})", flush=True)
        return 0 if verdict == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
