from app.services.write_approval_fingerprints import (
    allowed_write_targets_from_definition,
    invoke_target_allowed,
    write_target_fingerprint,
)


def test_changed_recipient_fingerprint_mismatch():
    definition = {
        "schema_version": "v1",
        "steps": [
            {
                "id": "s1",
                "type": "invoke_tool",
                "config": {"action": "gmail.messages.send", "email": "a@example.com", "subject": "Hi"},
            }
        ],
    }
    targets = allowed_write_targets_from_definition(definition)
    assert targets
    assert invoke_target_allowed(
        invoke_action="gmail.messages.send",
        params={"email": "a@example.com", "subject": "Hi"},
        allowed_targets=targets,
    )
    assert not invoke_target_allowed(
        invoke_action="gmail.messages.send",
        params={"email": "other@example.com", "subject": "Hi"},
        allowed_targets=targets,
    )


def test_message_body_change_mismatch():
    fp_a = write_target_fingerprint(
        invoke_action="gmail.messages.send",
        payload={"email": "a@example.com", "body": "hello"},
    )
    fp_b = write_target_fingerprint(
        invoke_action="gmail.messages.send",
        payload={"email": "a@example.com", "body": "goodbye"},
    )
    assert fp_a and fp_b and fp_a != fp_b


def test_email_normalized_case_insensitive():
    fp1 = write_target_fingerprint(invoke_action="x.y", payload={"email": "A@Example.com"})
    fp2 = write_target_fingerprint(invoke_action="x.y", payload={"email": "a@example.com"})
    assert fp1 == fp2


def test_record_id_preserves_case():
    fp1 = write_target_fingerprint(invoke_action="hubspot.contacts.update", payload={"id": "AbC"})
    fp2 = write_target_fingerprint(invoke_action="hubspot.contacts.update", payload={"id": "abc"})
    assert fp1 != fp2


def test_empty_allowed_targets_fail_closed():
    assert not invoke_target_allowed(
        invoke_action="gmail.messages.send",
        params={"email": "a@example.com"},
        allowed_targets=[],
    )


def test_amount_change_mismatch():
    fp_a = write_target_fingerprint(
        invoke_action="stripe.charges.create",
        payload={"amount": 100, "id": "cust_1"},
    )
    fp_b = write_target_fingerprint(
        invoke_action="stripe.charges.create",
        payload={"amount": 200, "id": "cust_1"},
    )
    assert fp_a and fp_b and fp_a != fp_b
