from app.services.intelligence_outcome_verification import verified_business_evidence


def evidence(state="VERIFIED SUCCESS", verified=True, sources=True, measured=True):
    return {
        "verification": {"state": state, "verified": verified, "method": "provider_readback"},
        "sourceRecords": [{"system": "hubspot", "record_id": "contact-1"}] if sources else [],
        "metric": {"key": "retained_accounts", "baseline": 1 if measured else None,
                   "result": 2 if measured else None},
    }


def test_positive_result_requires_proof_and_measured_metric():
    assert verified_business_evidence("VERIFIED SUCCESS", evidence())
    assert not verified_business_evidence("VERIFIED SUCCESS", evidence(sources=False))
    assert not verified_business_evidence("VERIFIED SUCCESS", evidence(measured=False))
    assert not verified_business_evidence("VERIFIED SUCCESS", evidence(verified=False))


def test_unverified_and_mismatched_status_fail_closed():
    assert not verified_business_evidence("PENDING VERIFICATION", evidence())
    assert not verified_business_evidence("VERIFIED FAILURE", evidence())
    assert not verified_business_evidence("VERIFIED SUCCESS", {})
    assert not verified_business_evidence("VERIFIED SUCCESS", None)


def test_negative_verified_result_needs_verification_method():
    failure = evidence(state="VERIFIED FAILURE", sources=False, measured=False)
    assert verified_business_evidence("VERIFIED FAILURE", failure)
    failure["verification"]["method"] = ""
    assert not verified_business_evidence("VERIFIED FAILURE", failure)
