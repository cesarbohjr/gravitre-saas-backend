#!/usr/bin/env python3
"""Brief prod deploy/restore via Railway GraphQL (OIL/claim3 rollback pattern).

Uses a Railway *project* token (Project-Access-Token header). Discovers project,
environment, and service IDs when not supplied via env.

Examples:
  python scripts/railway_prod_deploy.py --commit-sha 09e57595 --wait-health
  python scripts/railway_prod_deploy.py --latest-commit --wait-health
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

RAILWAY_GQL = "https://backboard.railway.com/graphql/v2"
DEFAULT_SERVICE = "gravitre-saas-backend"
DEFAULT_HEALTH_URL = "https://gravitre-saas-backend-production.up.railway.app/health"


def _gql(token: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"query": query}
    if variables:
        body["variables"] = variables
    req = urllib.request.Request(
        RAILWAY_GQL,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Project-Access-Token": token,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError(f"Railway GraphQL error: {payload['errors']}")
    return payload.get("data") or {}


def _resolve_ids(token: str, service_name: str) -> dict[str, str]:
    data = _gql(
        token,
        """
        query projectToken {
          projectToken { projectId environmentId }
        }
        """,
    )
    pt = data.get("projectToken") or {}
    project_id = str(pt.get("projectId") or "")
    environment_id = str(pt.get("environmentId") or "")
    if not project_id or not environment_id:
        raise RuntimeError("Could not resolve projectId/environmentId from project token")

    services_data = _gql(
        token,
        """
        query services($projectId: String!, $environmentId: String!) {
          project(id: $projectId) {
            services {
              edges {
                node {
                  id
                  name
                  serviceInstances(environmentId: $environmentId) {
                    edges { node { id } }
                  }
                }
              }
            }
          }
        }
        """,
        {"projectId": project_id, "environmentId": environment_id},
    )
    edges = ((services_data.get("project") or {}).get("services") or {}).get("edges") or []
    service_id = ""
    for edge in edges:
        node = edge.get("node") or {}
        name = str(node.get("name") or "")
        if name == service_name or service_name in name:
            service_id = str(node.get("id") or "")
            break
    if not service_id and edges:
        service_id = str((edges[0].get("node") or {}).get("id") or "")
    if not service_id:
        raise RuntimeError(f"Service '{service_name}' not found in project {project_id}")

    return {
        "project_id": project_id,
        "environment_id": environment_id,
        "service_id": service_id,
    }


def deploy_commit(
    token: str,
    *,
    service_id: str,
    environment_id: str,
    commit_sha: str | None = None,
    latest_commit: bool = False,
) -> str:
    variables: dict[str, Any] = {
        "serviceId": service_id,
        "environmentId": environment_id,
    }
    if latest_commit:
        variables["latestCommit"] = True
    elif commit_sha:
        variables["commitSha"] = commit_sha
    else:
        raise ValueError("Provide commit_sha or latest_commit=True")

    data = _gql(
        token,
        """
        mutation deploy($serviceId: String!, $environmentId: String!, $commitSha: String, $latestCommit: Boolean) {
          serviceInstanceDeployV2(
            serviceId: $serviceId
            environmentId: $environmentId
            commitSha: $commitSha
            latestCommit: $latestCommit
          )
        }
        """,
        variables,
    )
    deployment_id = str(data.get("serviceInstanceDeployV2") or "")
    if not deployment_id:
        raise RuntimeError(f"Deploy returned no deployment id: {data}")
    return deployment_id


def wait_for_health(
    health_url: str,
    *,
    sha_prefix: str | None = None,
    exclude_sha_prefix: str | None = None,
    timeout_s: int = 900,
    poll_s: int = 20,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=30) as resp:
                last = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"attempt={attempt} health_error={exc}", flush=True)
            time.sleep(poll_s)
            continue

        sha = str(last.get("git_sha") or "").lower()
        ok = True
        if sha_prefix:
            ok = sha.startswith(sha_prefix.lower())
            if ok and exclude_sha_prefix:
                ok = not sha.startswith(exclude_sha_prefix.lower())
        if not sha_prefix and exclude_sha_prefix:
            ok = not sha.startswith(exclude_sha_prefix.lower())

        print(f"attempt={attempt} git_sha={sha} ok={ok}", flush=True)
        if ok and sha and sha != "unknown":
            return last
        time.sleep(poll_s)

    raise TimeoutError(f"Timed out waiting for health match; last={last}")


def sha_is_ancestor(ancestor_prefix: str, descendant_sha: str) -> bool:
    try:
        subprocess.run(
            ["git", "fetch", "origin", "main", "--depth", "200"],
            check=True,
            capture_output=True,
            timeout=120,
        )
        proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor_prefix, descendant_sha],
            capture_output=True,
            timeout=30,
        )
        return proc.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return descendant_sha.lower().startswith(ancestor_prefix.lower())


def _load_operator_env() -> None:
    from dotenv import dotenv_values

    repo = Path(__file__).resolve().parent.parent
    for path in (repo / "backend" / ".env.operator.local", repo / ".env.operator.local", repo / "backend" / ".env"):
        if not path.is_file():
            continue
        try:
            for key, value in dotenv_values(path).items():
                if value:
                    __import__("os").environ.setdefault(key, value)
        except UnicodeDecodeError:
            continue


def main() -> int:
    _load_operator_env()
    parser = argparse.ArgumentParser(description="Deploy a specific commit to Railway prod")
    parser.add_argument("--commit-sha", default=None, help="Full or prefix git SHA to deploy")
    parser.add_argument("--latest-commit", action="store_true", help="Deploy latest main commit")
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    parser.add_argument("--wait-health", action="store_true")
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument("--json", dest="json_out", default=None)
    args = parser.parse_args()

    token = (__import__("os").environ.get("RAILWAY_TOKEN") or "").strip()
    if not token:
        print("RAILWAY_TOKEN is required (Railway project token)", file=sys.stderr)
        return 2

    ids = _resolve_ids(token, args.service)
    deployment_id = deploy_commit(
        token,
        service_id=ids["service_id"],
        environment_id=ids["environment_id"],
        commit_sha=args.commit_sha,
        latest_commit=args.latest_commit,
    )

    report: dict[str, Any] = {
        "deployment_id": deployment_id,
        "commit_sha_requested": args.commit_sha,
        "latest_commit": args.latest_commit,
        **ids,
    }

    if args.wait_health:
        if args.commit_sha:
            health = wait_for_health(
                args.health_url,
                sha_prefix=args.commit_sha[:8],
                timeout_s=args.timeout_s,
            )
        else:
            health = wait_for_health(
                args.health_url,
                exclude_sha_prefix="09e57595",
                timeout_s=args.timeout_s,
            )
        report["health"] = health
        deployed = str(health.get("git_sha") or "")
        if args.commit_sha:
            prefix = args.commit_sha[:8]
            if not (
                deployed.lower().startswith(prefix.lower())
                or sha_is_ancestor(prefix, deployed)
            ):
                print(f"Deployed SHA {deployed} does not match requested {args.commit_sha}", file=sys.stderr)
                return 1

    text = json.dumps(report, indent=2)
    print(text)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
