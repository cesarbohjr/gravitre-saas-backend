"""Persist Gravitre Test Customer Alpha into the isolated E2E org.

Synthetic host/email only. Never customer PII. Never operator org.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import FORBIDDEN_OPERATOR_ORG_ID, resolve_isolated_conversation_actor  # noqa: E402


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    for k, v in merged.items():
        if v and not os.environ.get(k):
            os.environ[k] = v
    return merged


def main() -> int:
    env = load_env()
    from supabase import create_client

    from app.services.business_entity_fabric import persist_join_store
    from app.services.conversation_write_guard import isolated_conversation_test_org_id
    from app.services.gravitre_e2e_test_org import ALPHA_ENTITY_ID, seed_test_customer_alpha

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, _user, _email = resolve_isolated_conversation_actor(env, sb)
    if org_id == FORBIDDEN_OPERATOR_ORG_ID:
        raise SystemExit("refusing operator org")
    if org_id != isolated_conversation_test_org_id():
        raise SystemExit(f"refusing non-isolated org {org_id}")
    entity = seed_test_customer_alpha(org_id=org_id)
    written = persist_join_store(sb, entity)
    print(
        json.dumps(
            {
                "org_id": org_id,
                "entity_id": entity.id,
                "expected_entity_id": ALPHA_ENTITY_ID,
                "bindings": [b.system for b in entity.bindings],
                "rows_written": written,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
