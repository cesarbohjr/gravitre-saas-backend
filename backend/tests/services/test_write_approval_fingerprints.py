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


def test_all_webhook_routing_and_effect_arguments_are_sealed():
    baseline = {"connector_id": "a", "path": "/safe", "headers": {"X-Action": "read"}, "payload": {"amount": 10}}
    approved = write_target_fingerprint(invoke_action="webhook.post", payload=baseline)
    for field, changed in [("connector_id", "b"), ("path", "/execute"), ("headers", {"X-Action": "execute"})]:
        assert write_target_fingerprint(invoke_action="webhook.post", payload={**baseline, field: changed}) != approved


def test_cc_bcc_attachments_and_unknown_provider_fields_are_sealed():
    baseline = {"to": "a@example.com", "cc": ["b@example.com"], "bcc": [], "attachments": [], "provider_extension": False}
    approved = write_target_fingerprint(invoke_action="gmail.messages.send", payload=baseline)
    for field, changed in [("cc", ["c@example.com"]), ("bcc", ["hidden@example.com"]), ("attachments", [{"id": "file"}]), ("provider_extension", True)]:
        assert write_target_fingerprint(invoke_action="gmail.messages.send", payload={**baseline, field: changed}) != approved


def test_order_whitespace_and_null_are_not_discarded():
    fingerprint = lambda p: write_target_fingerprint(invoke_action="vendor.write", payload=p)
    assert fingerprint({"operations": [1, 2]}) != fingerprint({"operations": [2, 1]})
    assert fingerprint({"body": "text "}) != fingerprint({"body": "text"})
    assert fingerprint({"field": None}) != fingerprint({"other": None})


def test_nested_workflow_params_bind_provider_payload_and_dynamic_sources_block():
    definition = {"steps": [{"type": "invoke_tool", "config": {"action": "gmail.messages.send", "connector_id": "c", "params": {"to": "a@example.com", "body": "hi"}}}]}
    targets = allowed_write_targets_from_definition(definition)
    assert invoke_target_allowed(invoke_action="gmail.messages.send", params={"connector_id": "c", "to": "a@example.com", "body": "hi"}, allowed_targets=targets)
    definition["steps"][0]["config"]["param_sources"] = {"to": "input.recipient"}
    assert not invoke_target_allowed(invoke_action="gmail.messages.send", params={"to": "a@example.com"}, allowed_targets=allowed_write_targets_from_definition(definition))
