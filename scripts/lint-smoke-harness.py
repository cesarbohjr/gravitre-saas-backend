#!/usr/bin/env python3
"""CI lint: conversation-writing smoke scripts must use gravitree_test_client.

Fails when a scripts/smoke-*.py:
  1) Touches conversations / ensure_owned / conversation_id minting without importing
     gravitree_test_client (or isolated_conversation_org during transition), OR
  2) Prefers OAUTH_SMOKE_ORG_ID / SMOKE_ORG_ID ahead of the isolated org for defaults.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

HARNESS_IMPORT = re.compile(
    r"gravitree_test_client|isolated_conversation_org",
    re.IGNORECASE,
)
CONVERSATION_WRITE = re.compile(
    r"""table\(\s*['\"]conversations['\"]\)|ensure_owned_conversation|"""
    r"""create_workflow_conversation|assert_conversation_create_allowed|"""
    r"""ConversationStateService|/api/conversations|ensureConversation""",
    re.IGNORECASE,
)
BAD_PREF = re.compile(
    r"""(?:args\.org_id|org_id)\s*=\s*\([^)]*env\.get\(\s*["']OAUTH_SMOKE_ORG_ID["']"""
    r"""|env\.get\(\s*["']OAUTH_SMOKE_ORG_ID["']\s*\)\s*or\s*env\.get\(\s*["']SMOKE_ORG_ID["']"""
    r"""|os\.getenv\(\s*["']OAUTH_SMOKE_ORG_ID["']""",
    re.IGNORECASE,
)

# Connector OAuth smokes may still target a connected customer org — exempt from (2)
# only when they do not match conversation-write patterns.
EXEMPT_PREF = {
    "smoke-oauth-live.py",
}


def main() -> int:
    failures: list[str] = []
    for path in sorted(SCRIPTS.glob("smoke-*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        name = path.name
        touches_conv = bool(CONVERSATION_WRITE.search(text))
        has_harness = bool(HARNESS_IMPORT.search(text))
        bad_pref = bool(BAD_PREF.search(text))

        if touches_conv and not has_harness:
            failures.append(f"{name}: conversation-write patterns without gravitree_test_client import")
        if bad_pref and name not in EXEMPT_PREF:
            failures.append(
                f"{name}: prefers OAUTH_SMOKE_ORG_ID/SMOKE_ORG_ID — use gravitree_test_client.require_isolated_org"
            )

    if failures:
        print("SMOKE_HARNESS_LINT_FAIL")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("SMOKE_HARNESS_LINT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
