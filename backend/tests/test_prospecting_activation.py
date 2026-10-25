from app.plays.prospecting_activation import ProspectingActivation, REQUIRED_STAGES

def test_partial_workflow_cannot_activate():
    gate = ProspectingActivation(enabled_stages=frozenset({"enrich"}))
    assert not gate.can_activate()
    assert "stage:consent_review" in gate.blockers()
    assert "tenant_isolation_verified" in gate.blockers()

def test_fully_tested_nonproduction_still_requires_live_e2e_for_production():
    fields = {key: True for key in (
        "migrations_verified","tenant_isolation_verified","connector_runtime_verified",
        "credential_vault_verified","credit_reservation_verified",
        "intelligence_router_verified","workflow_runtime_verified","review_interface_verified"
    )}
    gate = ProspectingActivation(**fields, enabled_stages=REQUIRED_STAGES)
    assert gate.can_activate(production=False)
    assert not gate.can_activate(production=True)
