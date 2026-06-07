"""Partner security review tests (STA-97)."""
from __future__ import annotations

import json
from pathlib import Path

from app.connectors.sdk.manifest import parse_manifest
from app.services.partner_security_review_service import (
    review_permission_scopes,
    run_certification_review,
    scan_package_sources,
)

EXAMPLE_MANIFEST = json.loads(
    Path(__file__).resolve().parents[3].joinpath("docs/integration/examples/acme-tools/manifest.json").read_text(
        encoding="utf-8"
    )
)


def test_scan_detects_hardcoded_secret():
    sources = {"handlers.py": 'API_KEY = "sk_test_abcdefghijklmnopqrstuvwxyz"\n'}
    result = scan_package_sources(sources)
    assert result.passed is False
    assert any(f.severity == "critical" for f in result.findings)


def test_scan_passes_clean_handler():
    sources = {"handlers.py": "def tickets_list(ctx, params):\n    return {'tickets': []}\n"}
    result = scan_package_sources(sources)
    assert result.passed is True
    assert result.files_scanned == 1


def test_scope_review_flags_wildcard_on_destructive_action():
    manifest = parse_manifest(
        {
            **EXAMPLE_MANIFEST,
            "actions": [
                {
                    "id": "records.delete",
                    "name": "Delete records",
                    "scopes": ["acme_tools:*"],
                    "destructive": True,
                }
            ],
        }
    )
    review = review_permission_scopes(manifest)
    assert review.passed is False
    assert any("Destructive" in issue for entry in review.entries for issue in entry.issues)


def test_certification_passes_with_clean_sources():
    manifest = parse_manifest(EXAMPLE_MANIFEST)
    result = run_certification_review(
        manifest,
        package_sources={"handlers.py": "def tickets_list(ctx, params):\n    return {}\n"},
    )
    assert result.certification_status == "passed"
    assert result.badge_eligible is True


def test_certification_pending_without_sources():
    manifest = parse_manifest(EXAMPLE_MANIFEST)
    result = run_certification_review(manifest, package_sources={})
    assert result.certification_status == "pending"
    assert result.badge_eligible is False
