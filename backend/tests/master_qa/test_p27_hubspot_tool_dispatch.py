"""No-network contracts for tool-driven protected HubSpot acceptance."""
from __future__ import annotations

import json
from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[3]
module = run_path(
    str(ROOT / "backend/scripts/p27_hubspot_dispatch_guard.py"),
    run_name="__p27_dispatch_contract__",
)
check_dispatch = module["check_dispatch"]
summarize = module["summarize"]
has_review = module["has_independent_exact_head_review"]
SHA = "a" * 40
REPO = "cesarbohjr/gravitre-saas-backend"


def env(event="pull_request", **kw):
    data = {
        "GITHUB_EVENT_NAME": event,
        "GITHUB_ACTOR": "cesarbohjr",
        "GITHUB_REPOSITORY": REPO,
        "EXPECTED_HEAD_SHA": SHA,
        "EVENT_PR_NUMBER": "611" if event == "pull_request" else "0",
        "GITHUB_REF": "refs/pull/611/merge" if event == "pull_request" else "refs/heads/main",
    }
    data.update(kw)
    return data


def protected_environment():
    return {
        "name": "p27-provider-sandbox",
        "protection_rules": [{
            "type": "required_reviewers", "prevent_self_review": True,
            "reviewers": [{"type": "User", "reviewer": {"id": 123, "login": "independent-reviewer"}}],
        }],
        "deployment_branch_policy": {"protected_branches": True, "custom_branch_policies": False},
    }


def test_owner_labeled_exact_pr_head_can_be_authorized():
    result = check_dispatch(env=env(), checked_out_sha=SHA, fetch_head=lambda: SHA,
                            approved_review=True, fetch_environment=protected_environment)
    assert result["result"] == "PASS"
    assert result["event"] == "pull_request"


@pytest.mark.parametrize("update", [
    {"GITHUB_ACTOR": "unknown-user"},
    {"GITHUB_REPOSITORY": "other/repo"},
    {"EVENT_PR_NUMBER": "612"},
    {"EXPECTED_HEAD_SHA": "not-a-sha"},
    {"GITHUB_EVENT_NAME": "issue_comment"},
])
def test_wrong_actor_repository_pr_sha_or_event_never_authorizes(update):
    with pytest.raises(RuntimeError):
        check_dispatch(env=env(**update), checked_out_sha=SHA, fetch_head=lambda: SHA)


def test_stale_pr_head_or_wrong_checkout_never_authorizes():
    with pytest.raises(RuntimeError, match="PR head changed"):
        check_dispatch(env=env(), checked_out_sha=SHA, fetch_head=lambda: "b" * 40, approved_review=True)
    with pytest.raises(RuntimeError, match="checkout SHA"):
        check_dispatch(env=env(), checked_out_sha="b" * 40, fetch_head=lambda: SHA, approved_review=True)
    with pytest.raises(RuntimeError, match="cannot verify"):
        check_dispatch(env=env(), checked_out_sha=SHA)


def test_pr_label_requires_independent_exact_head_approval():
    with pytest.raises(RuntimeError, match="independent exact-head"):
        check_dispatch(env=env(), checked_out_sha=SHA, fetch_head=lambda: SHA)
    with pytest.raises(RuntimeError, match="independent exact-head"):
        check_dispatch(
            env=env(), checked_out_sha=SHA,
            fetch_head=lambda: SHA, approved_review=False,
        )


def test_manual_dispatch_only_allowed_on_main():
    assert check_dispatch(
        env=env("workflow_dispatch"), checked_out_sha=SHA,
        fetch_environment=protected_environment,
    )["result"] == "PASS"
    with pytest.raises(RuntimeError, match="must run from main"):
        check_dispatch(
            env=env("workflow_dispatch", GITHUB_REF="refs/heads/feature"),
            checked_out_sha=SHA,
        )


@pytest.mark.parametrize("event", ["pull_request", "workflow_dispatch"])
@pytest.mark.parametrize("defect", [
    "unprotected", "no_branch_policy", "self_review_allowed", "no_reviewers",
    "author_only", "wrong_environment", "malformed_rules", "malformed_reviewer",
    "disabled_branch_policy", "ambiguous_branch_policy", "missing_metadata",
    "malformed_branch_policy", "nonboolean_branch_policy", "reviewer_without_id",
])
def test_unprotected_environment_never_authorizes_provider_write(event, defect):
    metadata = protected_environment()
    if defect == "unprotected":
        metadata["protection_rules"] = []
        metadata["deployment_branch_policy"] = None
    elif defect == "no_branch_policy":
        metadata["deployment_branch_policy"] = None
    elif defect == "self_review_allowed":
        metadata["protection_rules"][0]["prevent_self_review"] = False
    elif defect == "no_reviewers":
        metadata["protection_rules"][0]["reviewers"] = []
    elif defect == "author_only":
        metadata["protection_rules"][0]["reviewers"][0]["reviewer"]["login"] = "cesarbohjr"
    elif defect == "wrong_environment":
        metadata["name"] = "production"
    elif defect == "malformed_rules":
        metadata["protection_rules"] = "required_reviewers"
    elif defect == "malformed_reviewer":
        metadata["protection_rules"][0]["reviewers"] = ["independent-reviewer"]
    elif defect == "disabled_branch_policy":
        metadata["deployment_branch_policy"] = {"protected_branches": False, "custom_branch_policies": False}
    elif defect == "ambiguous_branch_policy":
        metadata["deployment_branch_policy"] = {"protected_branches": True, "custom_branch_policies": True}
    elif defect == "missing_metadata":
        metadata = None
    elif defect == "malformed_branch_policy":
        metadata["deployment_branch_policy"]["protected_branches"] = []
    elif defect == "nonboolean_branch_policy":
        metadata["deployment_branch_policy"]["protected_branches"] = 1
    elif defect == "reviewer_without_id":
        del metadata["protection_rules"][0]["reviewers"][0]["reviewer"]["id"]
    with pytest.raises(RuntimeError, match="environment"):
        check_dispatch(
            env=env(event), checked_out_sha=SHA, fetch_head=lambda: SHA,
            approved_review=True, fetch_environment=lambda: metadata,
        )


def test_environment_inspection_is_required_even_with_exact_head_approval():
    with pytest.raises(RuntimeError, match="environment"):
        check_dispatch(env=env(), checked_out_sha=SHA, fetch_head=lambda: SHA,
                       approved_review=True)


def test_unavailable_environment_metadata_never_authorizes():
    def unavailable():
        raise RuntimeError("environment metadata unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        check_dispatch(env=env(), checked_out_sha=SHA, fetch_head=lambda: SHA,
                       approved_review=True, fetch_environment=unavailable)


def test_team_reviewers_and_restricted_branch_environment_can_authorize():
    metadata = protected_environment()
    metadata["protection_rules"][0]["reviewers"] = [{"type": "Team", "reviewer": {"id": 321}}]
    metadata["deployment_branch_policy"] = {"protected_branches": False, "custom_branch_policies": True}
    result = check_dispatch(env=env(), checked_out_sha=SHA, fetch_head=lambda: SHA,
                            approved_review=True, fetch_environment=lambda: metadata)
    assert result["environment_protection_verified"] is True


def test_environment_metadata_request_is_read_only_and_scoped(monkeypatch):
    from unittest.mock import MagicMock
    import io
    read = module["current_environment_protection"]
    requests = []
    def open_metadata(request, *, timeout):
        requests.append(request)
        assert timeout == 12
        response = MagicMock()
        response.__enter__.return_value = io.StringIO(json.dumps(protected_environment()))
        return response
    monkeypatch.setattr(read.__globals__["urllib"].request, "urlopen", open_metadata)
    assert read("synthetic-token") == protected_environment()
    assert len(requests) == 1
    assert requests[0].get_method() == "GET"
    assert requests[0].full_url == f"https://api.github.com/repos/{REPO}/environments/p27-provider-sandbox"
    with pytest.raises(RuntimeError, match="token required"):
        read("")
    assert len(requests) == 1


def test_exact_head_review_cannot_be_faked_by_author_or_stale_approval():
    author = {"user": {"login": "cesarbohjr"}, "state": "APPROVED", "commit_id": SHA}
    stale = {"user": {"login": "reviewer"}, "state": "APPROVED", "commit_id": "b" * 40}
    approved = {"user": {"login": "reviewer"}, "state": "APPROVED", "commit_id": SHA}
    withdrawn = {"user": {"login": "reviewer"}, "state": "CHANGES_REQUESTED", "commit_id": SHA}
    assert not has_review([author], SHA)
    assert not has_review([stale], SHA)
    assert has_review([author, approved], SHA)
    assert not has_review([approved, withdrawn], SHA)
    with pytest.raises(RuntimeError, match="incomplete"):
        has_review([approved] * 100, SHA)


def test_summary_only_passes_verified_cleanup(tmp_path):
    file = tmp_path / "proof.json"
    good = {"result": "PASS", "portal_id": "343328749",
            "cleanup": "archived_and_get_404_verified",
            "duplicate_record": False,
            "resubmission": "same_email_same_contact_id",
            "synthetic_marker": "p27qaconfidential", "contact_id": "12345"}
    file.write_text(json.dumps(good))
    summary = summarize(file)
    assert summary["verified_cleanup_404"]
    assert "contact_id" not in summary and "synthetic_marker" not in summary
    for field, wrong in [
        ("result", "FAILED"), ("portal_id", "1"),
        ("cleanup", "unknown"), ("duplicate_record", True),
        ("resubmission", "different_record"),
    ]:
        candidate = dict(good)
        candidate[field] = wrong
        file.write_text(json.dumps(candidate))
        with pytest.raises(RuntimeError):
            summarize(file)


def test_workflow_exposes_preflight_without_provider_secrets():
    workflow = (ROOT / ".github/workflows/master-qa-p27-sandbox-readback.yml").read_text()
    assert "pull_request:" in workflow
    assert "types: [labeled]" in workflow
    assert "p27-hubspot-preflight" in workflow
    assert "p27-hubspot-live-approved" in workflow
    assert "github.actor == 'cesarbohjr'" in workflow
    assert "environment: p27-provider-sandbox" in workflow
    assert "  actions: read" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "python scripts/p27_hubspot_dispatch_guard.py" in workflow
    assert "P27_HUBSPOT_LIVE_TEST_TOKEN: ${{ secrets.P27_HUBSPOT_LIVE_TEST_TOKEN }}" in workflow
    preflight = workflow.split("  label-preflight:", 1)[1].split("  provider-readback:", 1)[0]
    assert "secrets." not in preflight
