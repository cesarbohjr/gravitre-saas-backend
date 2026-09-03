#!/usr/bin/env python3
"""Before/after for the router department fix, on real production messages.

Same corpus both ways: every `role='user'` message in `conversation_messages`.

BEFORE is the old logic, reimplemented here verbatim -- naked `in lower` against
the keyword list as it stood, with the pre-fix vocabulary. It is reconstructed
rather than imported because the fix replaced it in place. The reconstruction is
pinned by `test_before_baseline_matches_the_old_router` so it cannot quietly
drift into flattering the after.

AFTER is the live `classify_knowledge_query`.

WHAT WOULD MAKE THIS A BAD RESULT, stated up front:

  * Messages that lose a department they should have kept. The suffix rule was
    chosen precisely because the measured accidents were mostly desirable
    inflections; if the fix strips "prospects" or "msps", it is worse than the
    defect regardless of how many new legal matches it wins.
  * A large newly-routed count. Routing more traffic into expert packs is not
    self-evidently good -- it costs retrieval on every one of those turns.

PRIVACY: aggregates only. No message content is printed or written.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = REPO / "docs" / "delivery" / "router-department-beforeafter.json"

# The legal keyword tuple exactly as it stood before this change. The other five
# departments were not edited, so the after-list is used for them and only the
# matching rule differs there.
BEFORE_LEGAL = (
    "law", "statute", "regulation", "court", "opinion", "jurisdiction",
    "constitution", "equal protection", "employment law", "flsa", "fmla",
    "ftc", "can-spam", "can spam", "endorsement guide", "deceptive advertising",
    "native advertising", "pipeda", "justice laws", "competition act",
    "competition bureau",
)


def _load_env() -> None:
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local"):
        if not path.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        for k, v in (loaded or {}).items():
            if v and k not in os.environ:
                os.environ[k] = v


def _before_departments(lower: str) -> list[str]:
    """The old rule: naked substring, pre-fix vocabulary."""
    from app.knowledge_fabric.router import _DEPT_KEYWORDS

    out: list[str] = []
    for dept, keys in _DEPT_KEYWORDS.items():
        vocab = BEFORE_LEGAL if dept == "legal" else keys
        if any(k in lower for k in vocab):
            out.append(dept)
    return out


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.knowledge_fabric.router import classify_knowledge_query
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)

    rows: list[dict[str, Any]] = []
    page = 0
    while True:
        batch = (
            client.table("conversation_messages")
            .select("id,content")
            .eq("role", "user")
            .order("created_at", desc=True)
            .range(page * 1000, page * 1000 + 999)
            .execute()
            .data
            or []
        )
        rows.extend(batch)
        if len(batch) < 1000 or len(rows) >= 5000:
            break
        page += 1

    total = 0
    before_routed = 0
    after_routed = 0
    newly_routed = 0
    de_routed = 0
    changed_dept = 0
    newly_by_dept: Counter[str] = Counter()
    lost_by_dept: Counter[str] = Counter()

    for r in rows:
        text = str(r.get("content") or "").strip()
        if not text:
            continue
        total += 1
        lower = text.lower()
        before = set(_before_departments(lower))
        after = set(classify_knowledge_query(text).departments)

        before_routed += 1 if before else 0
        after_routed += 1 if after else 0
        if not before and after:
            newly_routed += 1
        if before and not after:
            de_routed += 1
        if before != after:
            changed_dept += 1
        for d in after - before:
            newly_by_dept[d] += 1
        for d in before - after:
            lost_by_dept[d] += 1

    report = {
        "corpus": "all role='user' conversation_messages in production",
        "messages": total,
        "before_routed_to_a_department": before_routed,
        "after_routed_to_a_department": after_routed,
        "newly_routed": newly_routed,
        "de_routed": de_routed,
        "any_department_change": changed_dept,
        "departments_gained": dict(newly_by_dept.most_common()),
        "departments_lost": dict(lost_by_dept.most_common()),
    }

    print(f"messages                    : {total}")
    print(f"routed before               : {before_routed}")
    print(f"routed after                : {after_routed}")
    print(f"newly routed                : {newly_routed}")
    print(f"de-routed (lost all depts)  : {de_routed}")
    print(f"any department set change   : {changed_dept}")
    print()
    print("departments gained:")
    for d, n in newly_by_dept.most_common():
        print(f"   {d:16} +{n}")
    print()
    print("departments lost (the accidents this fix removes):")
    for d, n in lost_by_dept.most_common():
        print(f"   {d:16} -{n}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print()
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
