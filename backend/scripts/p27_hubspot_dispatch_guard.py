"""Fail-closed GitHub / HubSpot P27 dispatch identity and evidence guard.

This file never writes to GitHub or HubSpot; requests only a public PR HEAD
document for comparison after a checkout. No token or provider response log.
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


def check_dispatch(*, env: dict[str, str], checked_out_sha: str,
                   fetch_head=None) -> dict:
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
    else:
        if env.get("GITHUB_REF") != "refs/heads/main" or pr_number != "0":
            raise RuntimeError("workflow_dispatch must run from main")
    return {"result": "PASS", "repository": repo,
            "checked_out_sha": expected, "event": event}


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
    )
    print(json.dumps(data, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
