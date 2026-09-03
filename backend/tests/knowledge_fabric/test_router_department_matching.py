"""Guards for how the Fabric router decides a keyword fired.

The router matched department keywords with a naked `in lower` test. That has
two failure directions and both were live:

  * "law" is inside "flawed" and "outlaw"; "incident" is inside "coincident".
    Ordinary sentences routed to legal and cybersecurity, and the retrieval that
    followed was charged to a department the user never asked about.
  * The list held one surface form per concept, so "statutory" missed because
    the entry was "statute". Privacy vocabulary -- "privacy", "HIPAA", "GDPR",
    "CCPA" -- was absent outright, so the most ordinary privacy question in the
    product routed nowhere and retrieved no legal evidence.

The fix is not "add word boundaries". Measured on 1982 real user messages, the
partial matches were mostly the ones we want -- "prospect" inside "prospects",
"msp" inside "msps", "cyber" inside "cybersecurity" -- and a plain boundary rule
would have destroyed 38 good matches to remove 17 accidents. These tests pin the
asymmetric rule that came out of that measurement, in both directions, because a
future edit that "tidies" it either way reintroduces one of the two defects.
"""
from __future__ import annotations

import pytest

from app.knowledge_fabric.router import (
    _COMPLIANCE_MATCHERS,
    _DEPT_KEYWORDS,
    _DEPT_MATCHERS,
    _EXACT_ONLY_KEYWORDS,
    classify_knowledge_query,
)


def _depts(query: str) -> set[str]:
    return set(classify_knowledge_query(query).departments)


# --------------------------------------------------------------------------
# Direction 1: keywords must not fire inside unrelated words
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,accidental_dept",
    [
        ("That was a flawed approach to the redesign.", "legal"),
        ("Can you outlaw duplicate records in the import?", "legal"),
        ("The two events were coincident last quarter.", "cybersecurity"),
        ("Show the secondary contact for each account.", "finance"),
        ("Rotate the security group membership.", "finance"),
    ],
)
def test_a_keyword_does_not_fire_inside_a_longer_word(query, accidental_dept):
    assert accidental_dept not in _depts(query), (
        f"{query!r} routed to {accidental_dept} on a substring accident; the "
        "left word boundary is not being applied"
    )


def test_a_neutral_message_routes_nowhere():
    assert _depts("What is the weather like today?") == set()
    assert _depts("Summarise yesterday's standup notes.") == set()


# --------------------------------------------------------------------------
# Direction 2: the inflections that the measurement said to keep
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected",
    [
        # 30 of these in the measured corpus. A plain \b rule kills them.
        ("Which prospects should I call today?", "sales"),
        ("Start prospecting the mid-market list.", "sales"),
        # 10 in the corpus.
        ("How do other MSPs price this?", "cybersecurity"),
        # 7 in the corpus.
        ("Give me a cybersecurity posture summary.", "cybersecurity"),
        ("What are the relevant laws here?", "legal"),
        ("Which regulators have jurisdiction?", "legal"),
    ],
)
def test_an_inflected_form_still_matches(query, expected):
    assert expected in _depts(query), (
        f"{query!r} lost its {expected} routing; the suffix rule was removed and "
        "the measured majority of partial matches were desirable inflections"
    )


def test_exact_only_keywords_do_not_take_a_suffix():
    """`sec` is the reason this set exists.

    Every one of its partial matches in the measured corpus was wrong -- 13
    inside "secondary", 2 inside "security", 2 inside "cybersecurity" -- and it
    was routing security questions to finance.
    """
    assert "sec" in _EXACT_ONLY_KEYWORDS
    assert "finance" in _depts("Pull the latest SEC filing.")
    assert "finance" not in _depts("Show the secondary contact.")


def test_every_exact_only_keyword_is_actually_in_the_vocabulary():
    """A typo here disables the protection silently.

    An entry that matches no keyword makes `sec` look guarded when it is not,
    and nothing else in the system would report it.
    """
    vocab = {k for keys in _DEPT_KEYWORDS.values() for k in keys}
    vocab |= {
        "can-spam", "can spam", "ftc", "endorsement", "influencer",
        "native advertising", "deceptive advertising", "competition bureau",
        "deceptive marketing",
    }
    unknown = sorted(k for k in _EXACT_ONLY_KEYWORDS if k not in vocab)
    assert not unknown, f"exact-only entries matching no keyword: {unknown}"


# --------------------------------------------------------------------------
# Direction 3: the vocabulary gap Phase 5 surfaced
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "What are our privacy obligations?",
        "Does HIPAA apply to us?",
        "What does GDPR require for data subject requests?",
        "What does CCPA require?",
        "What is the statutory deadline?",
        "What is the regulatory deadline?",
        "When must we send a breach notification?",
        "Review the contract before we sign.",
    ],
)
def test_ordinary_legal_and_privacy_questions_reach_legal(query):
    assert "legal" in _depts(query), (
        f"{query!r} routes to no legal department, so it retrieves no legal "
        "evidence -- the gap Phase 5 found"
    )


def test_the_phase_5_multi_hop_query_now_routes():
    """The specific query that exposed all of this.

    It resolved three jurisdictions and no department, so it retrieved nothing.
    Recorded as a named case because it is the one that made the gap visible.
    """
    route = classify_knowledge_query(
        "Compare the statutory breach notification deadline for personal health "
        "information in Ontario with the consumer breach notification deadline "
        "in California, and say which one obliges us to notify a regulator "
        "sooner and on what effective date each applies."
    )
    assert "legal" in route.departments
    assert "pack.legal" in route.pack_ids
    assert {"CA-ON", "US-CA"} <= set(route.jurisdictions)


# --------------------------------------------------------------------------
# Structural: the two matcher tables must stay derived from the vocabulary
# --------------------------------------------------------------------------


def test_matchers_are_derived_from_the_keyword_table_not_a_copy():
    """A second hand-maintained list is free to drift from the first.

    If `_DEPT_MATCHERS` is ever written out by hand, adding a keyword to
    `_DEPT_KEYWORDS` stops having any effect, and the reachability probe -- which
    reads `_DEPT_KEYWORDS` -- would report on vocabulary the router never uses.
    """
    assert set(_DEPT_MATCHERS) == set(_DEPT_KEYWORDS)
    for dept, keys in _DEPT_KEYWORDS.items():
        assert len(_DEPT_MATCHERS[dept]) == len(keys), (
            f"{dept} has {len(keys)} keywords but "
            f"{len(_DEPT_MATCHERS[dept])} matchers"
        )


def test_compliance_markers_use_the_same_rule_as_departments():
    """Fixing one and not the other leaves half the router matching by accident.

    The boundary assertion below is the load-bearing one. An earlier version of
    this test checked only that the markers still fire on a real compliance
    question, and mutation testing walked straight past it: reverting the markers
    to a naked substring match kept every positive case working, because the
    defect is what they match *additionally*.
    """
    assert _COMPLIANCE_MATCHERS, "compliance markers are not compiled"
    depts = _depts("Draft an influencer endorsement disclosure for the campaign.")
    assert {"legal", "marketing"} <= depts

    # "ftc" sits inside "swiftcode", which a product handling vendor banking
    # details will genuinely see. Under a naked substring match this pulls both
    # pack.legal and pack.marketing into a payments question.
    accidental = _depts("Update the swiftcode on the vendor record.")
    assert "legal" not in accidental and "marketing" not in accidental, (
        "a compliance marker fired inside a longer word; the markers are not "
        "going through _compile_keyword"
    )

    # Inflections still work, same asymmetry as the department keywords.
    assert {"legal", "marketing"} <= _depts("Review our endorsements policy.")
