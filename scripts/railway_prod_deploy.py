#!/usr/bin/env python3
"""Brief prod deploy/restore via Railway GraphQL (OIL/claim3 rollback pattern).

Uses a Railway API token. Deploy mutations require an account or team token
(https://railway.com/account/tokens) with Authorization: Bearer. Project-scoped
tokens (Project-Access-Token) can resolve IDs but may not redeploy.

Examples:
  python scripts/railway_prod_deploy.py --commit-sha 09e57595 --wait-health
  python scripts/railway_prod_deploy.py --latest-commit --wait-health
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

RAILWAY_GQL = "https://backboard.railway.com/graphql/v2"
DEFAULT_SERVICE = "gravitre-saas-backend"
DEFAULT_HEALTH_URL = "https://api.gravitre.app/health"


def _gql_raw(headers: dict[str, str], query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"query": query}
    if variables:
        body["variables"] = variables
    req = urllib.request.Request(
        RAILWAY_GQL,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError(f"Railway GraphQL error: {payload['errors']}")
    return payload.get("data") or {}


def _gql(token: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Try account/team Bearer auth first, then project token header."""
    attempts = [
        {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        {"Project-Access-Token": token, "Content-Type": "application/json"},
    ]
    last_http: urllib.error.HTTPError | None = None
    for headers in attempts:
        try:
            return _gql_raw(headers, query, variables)
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:  # noqa: BLE001
                pass
            last_http = urllib.error.HTTPError(
                exc.url, exc.code, f"{exc.reason} {body}", exc.headers, None
            )
            if exc.code in (401, 403):
                continue
            raise
    if last_http is not None:
        raise last_http
    raise RuntimeError("Railway GraphQL request failed")


def _pick_environment(env_edges: list[Any]) -> str:
    for edge in env_edges:
        node = edge.get("node") or {}
        name = str(node.get("name") or "").lower()
        if name in {"production", "prod"}:
            return str(node.get("id") or "")
    if env_edges:
        return str(((env_edges[0].get("node") or {}).get("id")) or "")
    return ""


def _resolve_ids_from_projects(token: str, service_name: str) -> dict[str, str]:
    data = _gql(
        token,
        """
        query listProjects {
          projects {
            edges {
              node {
                id
                name
                environments { edges { node { id name } } }
                services { edges { node { id name } } }
              }
            }
          }
        }
        """,
    )
    for edge in (data.get("projects") or {}).get("edges") or []:
        project = edge.get("node") or {}
        project_id = str(project.get("id") or "")
        env_id = _pick_environment((project.get("environments") or {}).get("edges") or [])
        service_id = ""
        for svc_edge in (project.get("services") or {}).get("edges") or []:
            node = svc_edge.get("node") or {}
            name = str(node.get("name") or "")
            if name == service_name or service_name in name:
                service_id = str(node.get("id") or "")
                break
        if service_id and project_id and env_id:
            return {
                "project_id": project_id,
                "environment_id": env_id,
                "service_id": service_id,
            }
    raise RuntimeError(
        f"Service '{service_name}' not found via account token. "
        "Set RAILWAY_PROJECT_ID and RAILWAY_ENVIRONMENT_ID or check token scope."
    )


def _resolve_ids(token: str, service_name: str) -> dict[str, str]:
    os_mod = __import__("os")
    project_id = str(os_mod.environ.get("RAILWAY_PROJECT_ID") or "").strip()
    environment_id = str(os_mod.environ.get("RAILWAY_ENVIRONMENT_ID") or "").strip()
    service_id = str(os_mod.environ.get("RAILWAY_SERVICE_ID") or "").strip()

    if project_id and environment_id and service_id:
        return {
            "project_id": project_id,
            "environment_id": environment_id,
            "service_id": service_id,
        }

    try:
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
    except urllib.error.HTTPError:
        project_id = ""
        environment_id = ""

    if not project_id or not environment_id:
        return _resolve_ids_from_projects(token, service_name)

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


def redeploy_via_cli(service: str, token: str) -> str:
    """Trigger Railway redeploy (GitHub-connected latest). Works with project tokens in CLI."""
    railway = shutil.which("railway") or shutil.which("railway.cmd")
    if not railway:
        raise RuntimeError("railway CLI not found on PATH")
    env = __import__("os").environ.copy()
    env["RAILWAY_TOKEN"] = token
    proc = subprocess.run(
        [railway, "redeploy", "-y", "-s", service],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"railway redeploy failed (exit {proc.returncode}): {detail[:500]}")
    print(f"railway redeploy ok: {(proc.stdout or proc.stderr or '').strip()[:200]}", flush=True)
    return "cli-redeploy"


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
            prefix = sha_prefix.lower()
            # Exact prefix match, or tip already moved past the requested SHA
            # (common when GitHub auto-deploy races railway up).
            ok = sha.startswith(prefix) or sha_is_ancestor(prefix, sha)
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


def _parse_env_lines(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    text: str | None = None
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return out
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, _, val = raw.partition("=")
        key = key.strip()
        val = val.strip().strip('"')
        if key and val:
            out[key] = val
    return out


def _load_railway_token_from_railway_variables(service: str) -> str | None:
    """Read RAILWAY_TOKEN from Railway service variables (requires ``railway login``)."""
    try:
        proc = subprocess.run(
            ["railway", "variables", "--service", service, "--json"],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    token = str(data.get("RAILWAY_TOKEN") or "").strip()
    return token or None


def _load_operator_env() -> None:
    from dotenv import dotenv_values

    repo = Path(__file__).resolve().parent.parent
    for path in (repo / "backend" / ".env.operator.local", repo / ".env.operator.local", repo / "backend" / ".env"):
        if not path.is_file():
            continue
        parsed: dict[str, str] = {}
        try:
            parsed = {k: v for k, v in dotenv_values(path).items() if v}
        except UnicodeDecodeError:
            parsed = _parse_env_lines(path)
        for key, value in parsed.items():
            if value:
                __import__("os").environ.setdefault(key, value)
        if path.name == ".env.operator.local" and not parsed:
            for key, value in _parse_env_lines(path).items():
                if value:
                    __import__("os").environ.setdefault(key, value)


def main() -> int:
    _load_operator_env()
    parser = argparse.ArgumentParser(description="Deploy a specific commit to Railway prod")
    parser.add_argument("--redeploy-cli", action="store_true", help="Use `railway redeploy` instead of GraphQL")
    parser.add_argument(
        "--wait-health-only",
        action="store_true",
        help="Skip deploy; only poll /health until commit_sha matches",
    )
    parser.add_argument("--commit-sha", default=None, help="Full or prefix git SHA to deploy")
    parser.add_argument("--latest-commit", action="store_true", help="Deploy latest main commit")
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    parser.add_argument("--wait-health", action="store_true")
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument("--json", dest="json_out", default=None)
    args = parser.parse_args()

    os_mod = __import__("os")
    if not (os_mod.environ.get("RAILWAY_TOKEN") or "").strip():
        railway_token = _load_railway_token_from_railway_variables(args.service)
        if railway_token:
            os_mod.environ["RAILWAY_TOKEN"] = railway_token

    token = (os_mod.environ.get("RAILWAY_TOKEN") or "").strip()
    if not token and not args.wait_health_only:
        print(
            "RAILWAY_TOKEN is required (Railway account/team token from "
            "https://railway.com/account/tokens, or project token for CLI redeploy). "
            "Set $env:RAILWAY_TOKEN, add to backend/.env.operator.local, "
            f"or run `railway login` so this script can read RAILWAY_TOKEN from Railway service variables ({args.service}).",
            file=sys.stderr,
        )
        return 2

    report: dict[str, Any] = {
        "commit_sha_requested": args.commit_sha,
        "latest_commit": args.latest_commit,
        "wait_health_only": bool(args.wait_health_only),
    }

    if not args.wait_health_only:
        if args.redeploy_cli:
            deployment_id = redeploy_via_cli(args.service, token)
            ids = {"project_id": "", "environment_id": "", "service_id": args.service}
        else:
            try:
                ids = _resolve_ids(token, args.service)
                deployment_id = deploy_commit(
                    token,
                    service_id=ids["service_id"],
                    environment_id=ids["environment_id"],
                    commit_sha=args.commit_sha,
                    latest_commit=args.latest_commit,
                )
            except (urllib.error.HTTPError, RuntimeError) as exc:
                print(f"GraphQL deploy failed ({exc}); falling back to railway redeploy CLI.", file=sys.stderr)
                deployment_id = redeploy_via_cli(args.service, token)
                ids = {"project_id": "", "environment_id": "", "service_id": args.service}
        report["deployment_id"] = deployment_id
        report.update(ids)

    if args.wait_health or args.wait_health_only:
        if not args.commit_sha:
            print("--commit-sha is required with --wait-health / --wait-health-only", file=sys.stderr)
            return 2
        health = wait_for_health(
            args.health_url,
            sha_prefix=args.commit_sha[:8],
            timeout_s=args.timeout_s,
        )
        report["health"] = health
        deployed = str(health.get("git_sha") or "")
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
