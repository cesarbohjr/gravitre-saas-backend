"""Phase 3 — catalog-wide success verification declarations."""
from __future__ import annotations

from app.services.write_success_verification import (
    build_default_verification,
    coverage_report,
    resolve_success_verification,
    success_verification_catalog,
)


def test_catalog_covers_all_mutating_actions():
    report = coverage_report()
    assert report["catalog_path_exists"], "success_verification_catalog.json missing — run generator"
    assert report["full_coverage"], (
        f"missing={report['missing_count']} sample={report['missing_sample']}"
    )
    assert report["coverage_pct"] == 100.0
    assert report["mutating_action_count"] >= 300


def test_f6_membership_actions_declared():
    for action in (
        "apollo.lists.add",
        "hubspot.lists.add_contact",
        "marketo.lists.add_to_static_list",
    ):
        ver = resolve_success_verification(action)
        assert ver.mode == "follow_up_membership"
        assert ver.read_action


def test_mailchimp_members_add_uses_sibling_get():
    ver = build_default_verification("mailchimp.members.add")
    assert ver.mode in {"follow_up_entity_get", "follow_up_membership", "accepted_async"}
    if ver.mode == "follow_up_entity_get":
        assert ver.read_action == "mailchimp.members.get"


def test_catalog_json_loads():
    cat = success_verification_catalog()
    assert cat
    assert "apollo.lists.add" in cat


def test_schedule_write_success_verification_returns_immediately(monkeypatch):
    """Phase 3 hard gate: scheduling must not block on F6 settle sleeps."""
    import time

    from app.services import write_success_verification as mod

    started = time.perf_counter()
    blocked = {"slept": False}

    def _fake_apply(**kwargs):  # noqa: ANN003
        time.sleep(0.05)
        blocked["slept"] = True
        from app.services.collection_population_verify import PopulationVerifyResult

        return (
            "partial_success",
            "accepted_async",
            PopulationVerifyResult(
                verified=False,
                effect="accepted_async",
                membership_count=0,
                detail="test",
                follow_up_attempted=True,
            ),
        )

    monkeypatch.setattr(mod, "apply_population_verify_to_status", _fake_apply)
    monkeypatch.setattr(mod, "is_population_write_action", lambda _a: True)

    class _Ctx:
        connector_id = "c1"
        settings = None
        client = None
        org_id = "o"
        actor_id = "u"
        environment_name = "production"

    mod.schedule_write_success_verification(
        client=object(),
        org_id="o",
        run_id="r1",
        invoke_action="apollo.lists.add",
        result_data={"list_id": "x"},
        settings=None,
        ctx=_Ctx(),
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert elapsed_ms < 20, f"schedule blocked TTFT path ({elapsed_ms:.1f}ms)"
