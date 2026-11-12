"""Fail-closed GitHub / HubSpot P27 dispatch identity and evidence guard.

This file never writes to GitHub or HubSpot; reads GitHub PR head and
environment protection metadata after checkout. No token or provider response log.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

REPO = "cesarbohjr/gravitre-saas-backend"
OWNER = "cesarbohjr"
PR = "611"
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
ALLOWED_EVENTS = {"pull_request", "workflow_dispatch"}
ENVIRONMENT = "p27-provider-sandbox"


def require_protected_environment(metadata) -> None:
    """Verify the live environment, not merely its name in workflow YAML.

    GitHub enforces branch compatibility and deployment approval. This guard
    additionally refuses provider writes if owner-only environment approval
    or branch restrictions cannot be inspected.
    """
    if not isinstance(metadata, dict) or metadata.get("name") != ENVIRONMENT:
        raise RuntimeError("provider environment identity cannot be verified")
    rules = metadata.get("protection_rules")
    if not isinstance(rules, list):
        raise RuntimeError("provider environment reviewer protection missing")
    owner_reviewer = False
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != "required_reviewers":
            continue
        # Owner explicitly authorized sole-reviewer control. The environment
        # still requires manual approval; self-review prevention must be off.
        if rule.get("prevent_self_review") is not False:
            continue
        reviewers = rule.get("reviewers")
        if not isinstance(reviewers, list) or len(reviewers) != 1:
            continue
        entry = reviewers[0]
        if not isinstance(entry, dict) or entry.get("type") != "User":
            continue
        reviewer = entry.get("reviewer")
        owner_reviewer = (
            isinstance(reviewer, dict)
            and str(reviewer.get("login") or "").casefold() == OWNER
            and type(reviewer.get("id")) is int
            and reviewer["id"] > 0
        )
        if owner_reviewer:
            break
    if not owner_reviewer:
        raise RuntimeError("provider environment requires sole owner reviewer with self review allowed")
    policy = metadata.get("deployment_branch_policy")
    if (not isinstance(policy, dict)
            or type(policy.get("protected_branches")) is not bool
            or type(policy.get("custom_branch_policies")) is not bool
            or policy["protected_branches"] is not False
            or policy["custom_branch_policies"] is not True):
        raise RuntimeError("provider environment deployment branch policy missing or invalid")


def check_dispatch(*, env: dict[str, str], checked_out_sha: str,
                   fetch_head=None, fetch_environment=None) -> dict:
    """Require owner, repo, exact immutable checkout and current PR HEAD."""
    event = env.get("GITHUB_EVENT_NAME", "")
    actor = env.get("GITHUB_ACTOR", "")
    repo = env.get("GITHUB_REPOSITORY", "")
    expected = env.get("EXPECTED_HEAD_SHA", "")
    pr_number = env.get("EVENT_PR_NUMBER", "0")
    if repo != REPO or actor != OWNER or event not in ALLOWED_EVENTS:
        raise RuntimeError("unapproved repository, caller or event; no provider test")
    if not SHA_RE.fullmatch(expected) or checked_out_sha != expected:
        raise RuntimeError("checkout SHA does not equal approved event SHA")
    if event == "pull_request":
        if pr_number != PR:
            raise RuntimeError("wrong PR; refusing live provider acceptance")
        if fetch_head is None:
            raise RuntimeError("cannot verify PR head at execution time")
        head = fetch_head()
        if not SHA_RE.fullmatch(head) or head != expected:
            raise RuntimeError("PR head changed after owner label; refusing write")
        if (env.get("GITHUB_EVENT_ACTION") != "labeled"
                or env.get("OWNER_APPROVAL_LABEL") != "p27-hubspot-live-approved"):
            raise RuntimeError("owner live approval label required")
    else:
        if env.get("GITHUB_REF") != "refs/heads/main" or pr_number != "0":
            raise RuntimeError("workflow_dispatch must run from main")
        if env.get("OWNER_DISPATCH_APPROVAL") != "APPROVE_LIVE_TEST_CONTACT":
            raise RuntimeError("explicit owner manual approval required")
    if fetch_environment is None:
        raise RuntimeError("cannot verify provider environment protection")
    require_protected_environment(fetch_environment())
    return {"result": "PASS", "repository": repo,
            "checked_out_sha": expected, "event": event,
            "environment_protection_verified": True}


def current_environment_protection(token: str) -> dict:
    if not token:
        raise RuntimeError("GitHub token required to inspect provider environment")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/environments/{ENVIRONMENT}",
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "gravitre-p27-environment-preflight"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.load(response)


def current_pr_head(token: str) -> str:
    if not token:
        raise RuntimeError("GitHub token missing: cannot verify live PR head")
    url = f"https://api.github.com/repos/{REPO}/pulls/{PR}"
    request = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "gravitre-p27-provider-preflight"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.load(response)
    return str(payload.get("head", {}).get("sha", ""))


def summarize(path: Path) -> dict:
    """Emit only success and bounded evidence, never credentials or markers."""
    obj = json.loads(path.read_text())
    if (obj.get("result") != "PASS"
            or obj.get("portal_id") != "343328749"
            or obj.get("cleanup") != "archived_and_get_404_verified"
            or obj.get("duplicate_record") is not False
            or obj.get("resubmission") != "same_email_same_contact_id"):
        raise RuntimeError("HubSpot readback/cleanup proof missing or incomplete")
    return {"result": "PASS", "portal_id": "343328749",
            "independent_readback": True, "idempotent_replay": True,
            "verified_cleanup_404": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summarize", type=Path)
    args = parser.parse_args()
    if args.summarize:
        print(json.dumps(summarize(args.summarize), sort_keys=True))
        return 0
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, timeout=8
    ).strip()
    data = check_dispatch(
        env=dict(os.environ), checked_out_sha=actual,
        fetch_head=lambda: current_pr_head(os.getenv("GH_TOKEN", "")),
        fetch_environment=lambda: current_environment_protection(os.getenv("GH_TOKEN", "")),
    )
    print(json.dumps(data, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
