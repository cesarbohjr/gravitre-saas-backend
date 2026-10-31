"""Read-only subscription probe using the exact ElevenLabs acceptance key.

Exports only fixed verdicts and bounded usage fields. Account identity, key
material, billing details, provider bodies and exception messages stay private.
A successful GET is not synthesis or voice certification.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

URL = "https://api.elevenlabs.io/v1/user/subscription"
TIERS = {"free", "trial", "starter", "creator", "pro", "scale", "business", "enterprise"}
STATUSES = {"active", "trialing", "past_due", "unpaid", "canceled", "free"}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def sanitize_subscription(data):
    if not isinstance(data, dict):
        raise ValueError("invalid subscription shape")
    result = {"tier": data.get("tier") if data.get("tier") in TIERS else "unrecognized",
              "subscription_status": data.get("status") if data.get("status") in STATUSES else "unrecognized"}
    for field in ("character_count", "character_limit", "next_character_count_reset_unix"):
        value = data.get(field)
        if type(value) is int and 0 <= value <= 10**15:
            result[field] = value
    if all(field in result for field in ("character_count", "character_limit")):
        result["remaining_reported_units"] = max(0, result["character_limit"] - result["character_count"])
    result["tier_matches_reported_starter"] = result["tier"] == "starter"
    return result

def probe(env, opener=None):
    report = {"status": "NOT RUN", "certified": False,
              "checked_at": datetime.now(timezone.utc).isoformat(),
              "source_sha": env.get("ACCEPTANCE_SOURCE_SHA", ""),
              "secret_source": "acceptance/ACCEPTANCE_ELEVENLABS_API_KEY",
              "scope": "read_only_subscription", "workspace_identity": "NOT VERIFIED",
              "key_specific_credit_cap": "NOT VERIFIED"}
    key = env.get("ELEVENLABS_API_KEY")
    if not key:
        report["diagnostic"] = "missing_acceptance_key"
        return report
    request = urllib.request.Request(URL, headers={"xi-api-key": key, "Accept": "application/json"})
    try:
        opener = opener or urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=20) as response:
            report["http_status"] = response.status
            if response.status != 200:
                report.update(status="BLOCKED", diagnostic="subscription_read_rejected")
                return report
            body = response.read(262145)
            if len(body) > 262144:
                raise ValueError("oversized response")
            report.update(sanitize_subscription(json.loads(body)))
            report["status"] = "OBSERVED"
    except urllib.error.HTTPError as error:
        report.update(status="BLOCKED", http_status=error.code, diagnostic="subscription_read_rejected")
    except (ValueError, TypeError):
        report.update(status="BLOCKED", diagnostic="invalid_subscription_response")
    except Exception:
        report.update(status="BLOCKED", diagnostic="subscription_transport_error")
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = probe(os.environ)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("ELEVENLABS_ACCOUNT_CHECK " + json.dumps(report, sort_keys=True))
    # Observational only: permission to read billing is not required for TTS.
    # Never change the independent synthesis job's pass/fail verdict.
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
