from app.plays.prospecting_providers import ProviderEntitlement, select_verifier

def make(name, **changes):
    args = dict(provider=name, api_key_present=True, free_credits_confirmed=50,
                credits_used=0, limit=50, enabled=True, entitlement_valid=True)
    args.update(changes)
    return ProviderEntitlement(**args)

def test_free_credit_waterfall_and_default_pause():
    ent = {"emailable": make("emailable", credits_used=50),
           "hunter": make("hunter")}
    assert select_verifier(ent, score=90, suppressed=False, previous_verified=False) == "hunter"
    assert select_verifier(ent, score=20, suppressed=False, previous_verified=False) is None
    assert select_verifier(ent, score=90, suppressed=True, previous_verified=False) is None
    assert select_verifier(ent, score=90, suppressed=False, previous_verified=True) is None

def test_missing_credentials_or_entitlement_disables_provider():
    for changes in ({"api_key_present":False}, {"entitlement_valid":False},
                    {"enabled":False}, {"free_credits_confirmed":0}):
        assert not make("hunter",**changes).can_call()
