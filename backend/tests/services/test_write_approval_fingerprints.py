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
                "config": {"action": "gmail.messages.send", "email": "a@example.com"},
            }
        ],
    }
    targets = allowed_write_targets_from_definition(definition)
    assert targets
    assert invoke_target_allowed(
        invoke_action="gmail.messages.send",
        params={"email": "a@example.com"},
        allowed_targets=targets,
    )
    assert not invoke_target_allowed(
        invoke_action="gmail.messages.send",
        params={"email": "other@example.com"},
        allowed_targets=targets,
    )


def test_fingerprint_stable():
    fp1 = write_target_fingerprint(invoke_action="x.y", payload={"email": "A@Example.com"})
    fp2 = write_target_fingerprint(invoke_action="x.y", payload={"email": "a@example.com"})
    assert fp1 == fp2
