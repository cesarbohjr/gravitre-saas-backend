from app.capabilities.publish_validation import validate_capability_for_publish


def _package() -> dict:
    return {
        "name": "SEO analyst",
        "package_format": "agent_skill",
        "license_policy": "allow",
        "risk_level": "low",
        "content_digest": "sha256:test",
        "source_uri": "https://github.com/acme/capabilities",
        "source_commit_sha": "a" * 40,
        "signature_status": "unsigned",
        "publisher_trusted": False,
        "publisher_verified": False,
        "manifest": {"name": "SEO analyst", "license": "MIT"},
        "inspection": {"components": [{"kind": "skill", "name": "seo"}]},
        "security_scan": {"blocked": False, "risk": "low"},
    }


def test_publish_validation_passes_strong_git_provenance_without_execution() -> None:
    report = validate_capability_for_publish(
        _package(),
        [{"path": "SKILL.md", "kind": "reference", "content": "Use evidence.", "executable": False}],
    )
    assert report["readyForMarketplace"] is True
    assert report["executionPerformed"] is False


def test_publish_validation_rejects_embedded_script_content() -> None:
    report = validate_capability_for_publish(
        _package(),
        [{"path": "scripts/run.py", "kind": "script", "content": "danger()", "executable": True}],
    )
    assert report["readyForMarketplace"] is False
    assert any(
        row["key"] == "inert_executable_resources" and not row["passed"]
        for row in report["checks"]
    )


def test_publish_validation_requires_strong_provenance() -> None:
    package = _package()
    package["source_uri"] = None
    package["source_commit_sha"] = None
    report = validate_capability_for_publish(package, [])
    assert report["readyForMarketplace"] is False
