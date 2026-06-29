"""Trigger production company intelligence run without echoing secrets."""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request


def _internal_secret() -> str:
    secret = os.environ.get("CI_SECRET", "").strip()
    if secret:
        return secret
    listed = subprocess.check_output(
        "railway variables --service gravitre-saas-backend --json",
        shell=True,
        text=True,
    )
    return json.loads(listed)["INTERNAL_API_SECRET"]


def main() -> None:
    secret = _internal_secret()
    body = json.dumps({"org_id": "00000000-0000-0000-0000-000000000001"}).encode()
    req = urllib.request.Request(
        "https://api.gravitre.app/api/internal/ops/company-intelligence-run",
        data=body,
        method="POST",
        headers={"X-Internal-Secret": secret, "Content-Type": "application/json"},
    )
    print(urllib.request.urlopen(req, timeout=300).read().decode())


if __name__ == "__main__":
    main()
