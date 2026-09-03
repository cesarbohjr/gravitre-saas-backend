#!/usr/bin/env python3
"""How often does the Fabric router fail to resolve a department on real traffic?

Reachability measured before fixing, per the standing lesson. The Phase 5 finding
was one query routing to zero packs; one query is an anecdote. This asks what
real user messages do.

Two failure directions, both real and both measured here:

  * MISS  -- the message carries department vocabulary the keyword list does not
    contain, or contains only in another inflection. "statutory" misses because
    the list holds "statute"; "regulator" misses because it holds "regulation".
    "privacy", "HIPAA", "GDPR" and "CCPA" are absent from the legal list outright.

  * SPURIOUS -- the list matches by naked substring, with no word boundary, so
    "flawed" contains "law" and routes to legal, and "coincident" contains
    "incident" and routes to cybersecurity.

PRIVACY: aggregates only. No message content is printed or written. The one
exception is a redacted matched-token report -- the specific keyword that fired
and the word it fired inside -- which is needed to tell a real match from a
substring accident, and is vocabulary, not user data.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = REPO / "docs" / "delivery" / "router-department-reach.json"

# Vocabulary a legal/privacy question plainly uses, which the current list has
# no entry for in any inflection. Used only to size the miss, not to fix it.
_ABSENT_LEGAL_VOCAB = (
    "privacy", "hipaa", "gdpr", "ccpa", "cpra", "phipa", "pipa", "phi",
    "breach notification", "data subject", "consent", "retention policy",
    "compliance", "statutory", "regulator", "regulatory", "liability",
    "indemnity", "contract", "terms of service", "dpa", "subprocessor",
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


def _match_detail(lower: str) -> list[tuple[str, str, bool]]:
    """Every keyword that fires, the word it fired inside, and whether it is whole.

    A keyword firing inside a longer word is the spurious case. Returned rather
    than counted here so the caller can separate the two without re-deriving it.
    """
    from app.knowledge_fabric.router import _DEPT_KEYWORDS

    out: list[tuple[str, str, bool]] = []
    for dept, keys in _DEPT_KEYWORDS.items():
        for k in keys:
            idx = lower.find(k)
            if idx < 0:
                continue
            # The whole token the keyword landed in.
            start = idx
            while start > 0 and (lower[start - 1].isalnum() or lower[start - 1] in "-*"):
                start -= 1
            end = idx + len(k)
            while end < len(lower) and (lower[end].isalnum() or lower[end] in "-*"):
                end += 1
            token = lower[start:end]
            out.append((dept, k, token == k))
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
            .select("id,role,content,created_at")
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
    no_dept = 0
    routed = 0
    miss_with_vocab = 0
    spurious_only = 0
    dept_counter: Counter[str] = Counter()
    spurious_tokens: Counter[str] = Counter()
    absent_vocab_hits: Counter[str] = Counter()

    for r in rows:
        text = str(r.get("content") or "").strip()
        if not text:
            continue
        total += 1
        lower = text.lower()
        route = classify_knowledge_query(text)
        details = _match_detail(lower)
        whole = [d for d in details if d[2]]
        partial = [d for d in details if not d[2]]

        for _dept, key, is_whole in partial:
            # Record the accident, not the message.
            m = re.search(
                r"[a-z0-9*-]*" + re.escape(key) + r"[a-z0-9*-]*", lower
            )
            if m and not is_whole:
                spurious_tokens[f"{key} -> {m.group(0)}"] += 1

        if route.departments:
            routed += 1
            for d in route.departments:
                dept_counter[d] += 1
            if not whole and partial:
                # Routed ONLY because a keyword matched inside a longer word.
                spurious_only += 1
        else:
            no_dept += 1
            hit = [v for v in _ABSENT_LEGAL_VOCAB if v in lower]
            if hit:
                miss_with_vocab += 1
                for v in hit:
                    absent_vocab_hits[v] += 1

    report = {
        "user_messages_scanned": total,
        "routed_to_a_department": routed,
        "routed_to_nothing": no_dept,
        "routed_to_nothing_pct": round(100 * no_dept / total, 1) if total else None,
        "routed_ONLY_by_substring_accident": spurious_only,
        "unrouted_but_carrying_legal_vocab": miss_with_vocab,
        "departments": dict(dept_counter.most_common()),
        "top_absent_vocab_in_unrouted": dict(absent_vocab_hits.most_common(15)),
        "top_substring_accidents": dict(spurious_tokens.most_common(15)),
    }

    print(f"user messages scanned          : {total}")
    print(f"routed to a department         : {routed}")
    print(f"routed to NOTHING              : {no_dept} "
          f"({report['routed_to_nothing_pct']}%)")
    print(f"  of those, carrying legal vocab: {miss_with_vocab}")
    print(f"routed ONLY by substring accident: {spurious_only}")
    print()
    print("departments resolved:")
    for d, n in dept_counter.most_common():
        print(f"   {d:16} {n}")
    print()
    print("absent vocabulary seen in unrouted messages:")
    for v, n in absent_vocab_hits.most_common(15):
        print(f"   {v:22} {n}")
    print()
    print("substring accidents (keyword -> the word it fired inside):")
    for t, n in spurious_tokens.most_common(15):
        print(f"   {t:34} {n}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print()
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
