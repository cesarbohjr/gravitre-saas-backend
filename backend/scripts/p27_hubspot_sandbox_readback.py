"""P27 controlled existing-HubSpot-portal QA contact acceptance.

Explicit owner-approved test contact in the existing Gravitre AI portal only.
No customers on Gravitre does not remove the requirement for exact account
binding, a unique disposable record, affirmative approval, and cleanup.
Never used in ordinary PR CI. The protected manual GitHub Actions workflow
is the only documented live invocation.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import urllib.error
from urllib.parse import quote
from uuid import uuid4

from p27_sandbox_provider_readback import _request

logger = logging.getLogger(__name__)
BASE = "https://api.hubapi.com"
GRAVITRE_HUBSPOT_PORTAL_ID = "343328749"
QA_TYPES = frozenset({"DEVELOPER_TEST", "APP_DEVELOPER", "SANDBOX"})


def _qa_domain_valid(domain: str) -> bool:
    """Reject public email, lookalike and malformed namespaces."""
    return bool(
        re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,118}[a-z0-9]", domain)
        and "." in domain
        and ".." not in domain
        and not domain.endswith((".com.", ".invalid."))
        and domain not in {"gmail.com", "outlook.com", "yahoo.com",
                           "hotmail.com", "icloud.com"}
    )


def _get_with_bounded_404_retry(url: str, *, token: str, attempts: int = 5, delay: float = 0.75):
    """Retry only eventual-consistency 404s; never retry a write or mask other errors."""
    for attempt in range(attempts):
        try:
            return _request(url, token=token, method="GET")
        except urllib.error.HTTPError as exc:
            if exc.code != 404 or attempt == attempts - 1:
                raise
            time.sleep(delay)


def verify_hubspot(*, token: str, portal_id: str, email_domain: str,
                   approved: bool, approve_existing_live_portal: bool = False):
    """One synthetic upsert, authoritative GET, identical replay, delete/404.

    Any failure after a contact ID is known still attempts cleanup; a failed
    cleanup *never* returns PASS. No real user records or inbound search lists.
    """
    if not approved or not approve_existing_live_portal:
        raise RuntimeError("APPROVE_LIVE_TEST_CONTACT consent is required")
    if portal_id != GRAVITRE_HUBSPOT_PORTAL_ID:
        raise RuntimeError("existing-live-portal test bound to Gravitre portal only")
    if not token or len(token.strip()) < 12 or not _qa_domain_valid(email_domain):
        raise RuntimeError("missing credential or dedicated QA email namespace")

    # This read must succeed before any write and identify this exact account.
    details = _request(BASE + "/account-info/v3/details",
                       token=token, method="GET")
    # HubSpot may return a successful HTTP response with JSON null or another
    # unexpected shape. Never allow an unverified account to reach a write.
    if not isinstance(details, dict):
        raise RuntimeError(
            "HubSpot account verification returned a non-object JSON response; "
            "provider write refused"
        )
    if str(details.get("portalId")) != portal_id:
        raise RuntimeError("HubSpot portal mismatch: write refused")
    if str(details.get("accountType") or "").upper() != "STANDARD":
        raise RuntimeError("expected existing Gravitre STANDARD portal")

    marker = "p27qa" + uuid4().hex
    email = f"{marker}@{email_domain}"
    properties = {"email": email, "firstname": "P27QA", "lastname": marker}
    payload = {"inputs": [{
        "idProperty": "email", "id": email,
        "properties": properties,
        "objectWriteTraceId": marker,
    }]}
    upsert_url = BASE + "/crm/v3/objects/contacts/batch/upsert"
    contact_id = None
    write_attempted = False
    primary_error = None
    cleanup_error = None
    try:
        write_attempted = True
        written = _request(upsert_url, token=token, method="POST", payload=payload)
        logger.warning(
            "p27_upsert_receipt status=%s result_count=%s has_result_id=%s",
            str(written.get("status"))[:32] if isinstance(written, dict) else "invalid",
            len(written.get("results")) if isinstance(written, dict) and isinstance(written.get("results"), list) else -1,
            bool(isinstance(written, dict) and isinstance(written.get("results"), list)
                 and len(written["results"]) == 1 and isinstance(written["results"][0], dict)
                 and written["results"][0].get("id")),
        )
        if written.get("status") != "COMPLETE":
            raise RuntimeError("HubSpot QA contact upsert incomplete")
        results = written.get("results")
        # HubSpot may acknowledge a batch without returning a usable ID.
        # Recover only by an authoritative lookup of our unique QA email;
        # never infer an ID or operate on a non-owned contact.
        response_id = (
            str(results[0].get("id"))
            if isinstance(results, list) and len(results) == 1
            and isinstance(results[0], dict) and results[0].get("id")
            else None
        )
        by_email_url = (
            BASE + "/crm/v3/objects/contacts/" + quote(email, safe="")
            + "?idProperty=email&properties=email,firstname,lastname"
        )
        try:
            located = _get_with_bounded_404_retry(by_email_url, token=token)
        except urllib.error.HTTPError as exc:
            logger.error("p27_readback_failure http_status=%d receipt_id_present=%s",
                         exc.code, response_id is not None)
            raise
        fields = located.get("properties") if isinstance(located, dict) else None
        located_id = str(located.get("id") or "") if isinstance(located, dict) else ""
        if (not re.fullmatch(r"[0-9]+", located_id)
                or not isinstance(fields, dict)
                or any(str(fields.get(k) or "") != v for k, v in properties.items())):
            raise RuntimeError("HubSpot QA upsert not independently verified by unique email")
        if response_id is not None and response_id != located_id:
            raise RuntimeError("HubSpot QA upsert receipt conflicts with authoritative GET")
        contact_id = located_id

        get_url = (BASE + "/crm/v3/objects/contacts/" + quote(contact_id, safe="")
                   + "?properties=email,firstname,lastname")

        def readback():
            record = _request(get_url, token=token, method="GET")
            fields = record.get("properties")
            if str(record.get("id")) != contact_id or not isinstance(fields, dict):
                raise RuntimeError("HubSpot QA authoritative GET mismatched id")
            if any(str(fields.get(k) or "") != v for k, v in properties.items()):
                raise RuntimeError("HubSpot QA record fields mismatched")
            return record

        readback()
        repeated = _request(upsert_url, token=token, method="POST", payload=payload)
        again = repeated.get("results")
        if repeated.get("status") != "COMPLETE":
            raise RuntimeError("HubSpot QA replay incomplete")
        if (isinstance(again, list) and len(again) == 1
                and isinstance(again[0], dict) and again[0].get("id")
                and str(again[0]["id"]) != contact_id):
            raise RuntimeError("HubSpot QA replay receipt changed contact ID")
        # The same unique email must still resolve to exactly the original ID.
        replay_record = _request(by_email_url, token=token, method="GET")
        if (not isinstance(replay_record, dict)
                or str(replay_record.get("id")) != contact_id):
            raise RuntimeError("HubSpot QA replay changed email identity")
        readback()
    except Exception as exc:
        primary_error = exc
    finally:
        if contact_id is None and write_attempted:
            # Provider may commit a POST then lose the response. Reconcile by
            # this exact random QA email; never assume no effect occurred.
            try:
                by_email_url = (
                    BASE + "/crm/v3/objects/contacts/"
                    + quote(email, safe="")
                    + "?idProperty=email&properties=email,firstname,lastname")
                try:
                    located = _request(by_email_url, token=token, method="GET")
                except urllib.error.HTTPError as exc:
                    if exc.code != 404:
                        raise
                else:
                    fields = located.get("properties")
                    identifier = str(located.get("id") or "")
                    if (not re.fullmatch(r"[0-9]+", identifier)
                            or not isinstance(fields, dict)
                            or any(str(fields.get(k) or "") != v
                                   for k, v in properties.items())):
                        raise RuntimeError("unverified orphan QA contact; manual cleanup required")
                    contact_id = identifier
            except Exception as exc:
                cleanup_error = exc
        if contact_id is not None and cleanup_error is None:
            # Do not trust an ID in an upsert response as deletion authority.
            # Before DELETE, independently GET that ID and prove it is OUR
            # unique contact by the email AND both QA marker fields. This
            # also protects against incorrect provider responses and ID reuse.
            try:
                delete_url = BASE + "/crm/v3/objects/contacts/" + quote(contact_id, safe="")
                owned = _request(
                    delete_url + "?properties=email,firstname,lastname",
                    token=token, method="GET")
                fields = owned.get("properties")
                if (str(owned.get("id")) != contact_id
                        or not isinstance(fields, dict)
                        or any(str(fields.get(k) or "") != v
                               for k, v in properties.items())):
                    raise RuntimeError(
                        "HubSpot QA deletion refused: target is not independently proven synthetic")
                _request(delete_url, token=token, method="DELETE")
                try:
                    _request(
                        delete_url + "?properties=email,firstname,lastname",
                        token=token, method="GET")
                except urllib.error.HTTPError as exc:
                    if exc.code != 404:
                        raise
                else:
                    raise RuntimeError("HubSpot QA cleanup failed: contact still readable")
            except Exception as exc:
                cleanup_error = exc

    if cleanup_error is not None:
        raise RuntimeError(
            f"HubSpot QA cleanup NOT verified: record={contact_id}, marker={marker}"
        ) from cleanup_error
    if primary_error is not None:
        raise RuntimeError(
            f"HubSpot QA test failed: marker={marker}, record={contact_id}"
        ) from primary_error
    return {
        "result": "PASS", "provider": "hubspot",
        "portal_id": portal_id, "contact_id": contact_id,
        "readback": "crm_v3_contacts_get_by_id",
        "resubmission": "same_email_same_contact_id",
        "duplicate_record": False,
        "cleanup": "archived_and_get_404_verified",
        "synthetic_marker": marker,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approve-live-test-contact", action="store_true")
    args = parser.parse_args()
    result = verify_hubspot(
        token=os.environ.get("P27_HUBSPOT_LIVE_TEST_TOKEN", ""),
        portal_id=os.environ.get("P27_HUBSPOT_EXPECTED_PORTAL_ID", ""),
        email_domain=os.environ.get("P27_HUBSPOT_QA_EMAIL_DOMAIN", ""),
        approved=args.approve_live_test_contact,
        approve_existing_live_portal=args.approve_live_test_contact,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
