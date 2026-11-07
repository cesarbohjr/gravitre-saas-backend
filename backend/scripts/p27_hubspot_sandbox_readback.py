"""HubSpot-specific P27 sandbox acceptance: idempotent contact upsert + GET.

Only a manually approved GitHub Actions environment may invoke this script.
No token, portal ID, or credentials are supplied by default. Reject ordinary
production portals even if an operator accidentally points to one.

Docs: HubSpot CRM v3 contacts batch upsert (idProperty=email), individual
GET by contact record ID, account-info v3 details portalId/accountType.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from urllib.parse import quote
from uuid import uuid4

from p27_sandbox_provider_readback import _request

BASE = "https://api.hubapi.com"
ALLOWED_TYPES = frozenset({"DEVELOPER_TEST", "APP_DEVELOPER", "SANDBOX"})


def verify_hubspot(*, token: str, portal_id: str, email_domain: str, approved: bool):
    if not approved:
        raise RuntimeError("explicit sandbox approval required")
    if not token or len(token.strip()) < 12 or not portal_id.isdigit():
        raise RuntimeError("sandbox access token or expected portal ID missing")
    if (not re.fullmatch(r"[a-z0-9.-]{4,120}", email_domain)
        or "." not in email_domain
        or email_domain in {"gmail.com", "outlook.com", "yahoo.com", "hotmail.com"}):
        raise RuntimeError("explicit isolated test email domain required")

    # Before any write, verify token is scoped to the exact intended
    # developer-test portal AND the account is nonproduction.
    details = _request(BASE + "/account-info/v3/details", token=token, method="GET")
    if str(details.get("portalId")) != portal_id:
        raise RuntimeError("HubSpot portal ID mismatch: write refused")
    if str(details.get("accountType") or "").upper() not in ALLOWED_TYPES:
        raise RuntimeError("HubSpot account is not an accepted sandbox account type")

    marker = f"p27qa{uuid4().hex}"
    email = f"{marker}@{email_domain}"
    properties = {"email": email, "firstname": "P27QA", "lastname": marker}
    request = {"inputs": [{
        "idProperty": "email", "id": email,
        "properties": properties,
        "objectWriteTraceId": marker,
    }]}
    url = BASE + "/crm/v3/objects/contacts/batch/upsert"
    first = _request(url, token=token, method="POST", payload=request)
    if first.get("status") != "COMPLETE":
        raise RuntimeError("HubSpot sandbox batch not completed")
    items = first.get("results")
    if not isinstance(items, list) or len(items) != 1 or not items[0].get("id"):
        raise RuntimeError("HubSpot sandbox upsert has no single concrete contact ID")
    contact_id = str(items[0]["id"])
    get_url = (BASE + "/crm/v3/objects/contacts/" + quote(contact_id, safe="")
               + "?properties=email,firstname,lastname")

    def readback():
        record = _request(get_url, token=token, method="GET")
        props = record.get("properties")
        if str(record.get("id")) != contact_id or not isinstance(props, dict):
            raise RuntimeError("HubSpot contact GET did not confirm the created resource")
        if any(str(props.get(key) or "") != value for key, value in properties.items()):
            raise RuntimeError("HubSpot authoritative contact fields differ")
        return record

    readback()
    # Replay the IDENTICAL business operation, not a new synthetic key.
    repeated = _request(url, token=token, method="POST", payload=request)
    results = repeated.get("results")
    if repeated.get("status") != "COMPLETE" or not isinstance(results, list) or len(results) != 1:
        raise RuntimeError("HubSpot dedupe upsert did not complete")
    if str(results[0].get("id")) != contact_id:
        raise RuntimeError("Duplicate HubSpot contact detected on identical upsert")
    readback()
    return {
        "result": "PASS", "provider": "hubspot",
        "portal_id": portal_id, "contact_id": contact_id,
        "readback": "crm_v3_contacts_get_by_id",
        "resubmission": "same_email_same_contact_id",
        "duplicate_record": False,
        "synthetic_marker": marker,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approve-sandbox-write", action="store_true", required=True)
    args = parser.parse_args()
    result = verify_hubspot(
        token=os.environ.get("P27_HUBSPOT_SANDBOX_TOKEN", ""),
        portal_id=os.environ.get("P27_HUBSPOT_SANDBOX_PORTAL_ID", ""),
        email_domain=os.environ.get("P27_HUBSPOT_QA_EMAIL_DOMAIN", ""),
        approved=args.approve_sandbox_write,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
