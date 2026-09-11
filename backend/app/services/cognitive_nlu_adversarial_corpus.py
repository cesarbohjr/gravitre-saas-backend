"""Large adversarial NLU corpus for the six-stage cognitive loop.

Hundreds of prompts, generated from templates — not a hand list of bugs
already found. Each item declares whether the Intent Gateway must fall
through (operator-shaped / obscure task) or may shortcut (narrow FAQ).

CI runs the corpus through the gateway + loop controller on every deploy.
Live LLM ACT is not required for the structural pass; the live probe uses a
representative subset against production.
"""
from __future__ import annotations

from typing import Literal

Expected = Literal["fallthrough", "shortcut"]

# Vendors and job verbs already real in this catalog — used as surface variety,
# not as new product claims.
_VENDORS = (
    "Google Ads",
    "HubSpot",
    "Apollo",
    "Salesforce",
    "Gmail",
    "Slack",
    "Stripe",
    "QuickBooks",
    "LinkedIn",
    "Marketo",
    "Mailchimp",
    "Greenhouse",
    "NVD",
    "Clay",
)

_JOBS = (
    "create a campaign",
    "check that my account is actually connected",
    "show me the complete plan",
    "don't execute without my approval",
    "list open opportunities",
    "who should I prioritize this week",
    "add these contacts to a list",
    "pull last week's performance",
    "draft the follow-up sequence",
    "flag the highest severity vulnerabilities",
)

_AMBIGUOUS_PREFIXES = (
    "uh,",
    "wait—",
    "ok so like",
    "not sure this is the right place but",
    "quick one,",
    "before I forget,",
    "if you can,",
    "sorry, circling back:",
    "between you and me,",
    "honestly I don't know the button name —",
)

_OBSCURE_WRAPS = (
    "in that thing we use for {}",
    "via the {} integration if it's even on",
    "whatever the {} connector is called this week",
    "using {} without touching anything else",
    "inside {} and nowhere else",
)

_MULTI_CLAUSE_TAILS = (
    "and also tell me if HubSpot is connected",
    "then summarize in one sentence, no tools after that",
    "but skip Salesforce even if the ad copy mentions it",
    "and don't create a workflow named after a quoted phrase",
    "once I approve, not before",
    "and keep Google Ads as the only write target",
)

_EDGE_AFFIXES = (
    lambda s: s.replace("don't", "don’t"),
    lambda s: f'"{s}"',
    lambda s: s + " ???",
    lambda s: s.upper(),
    lambda s: f"   {s}   ",
    lambda s: s.replace("account", "acct"),
    lambda s: s + " — thanks",
    lambda s: s.replace("Google Ads", "googleads"),
    lambda s: s.replace("HubSpot", "hub spot"),
    lambda s: "\n".join(s.split(" ", 3)[:2] + [s]),
)


def _item(item_id: str, message: str, expected: Expected, *, family: str) -> dict[str, str]:
    return {
        "id": item_id,
        "message": message,
        "expected": expected,
        "family": family,
    }


def build_adversarial_nlu_corpus() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    # --- operator-shaped fallthrough: vendor × job (140) ---
    n = 0
    for vendor in _VENDORS:
        for job in _JOBS:
            n += 1
            msg = f"In {vendor}, {job}."
            items.append(_item(f"vendor_job_{n:03d}", msg, "fallthrough", family="vendor_job"))

    # --- obscure phrasing (70) ---
    n = 0
    for vendor in _VENDORS:
        for wrap in _OBSCURE_WRAPS:
            n += 1
            job = _JOBS[n % len(_JOBS)]
            msg = f"{wrap.format(vendor)} — {job}"
            items.append(_item(f"obscure_{n:03d}", msg, "fallthrough", family="obscure"))

    # --- ambiguous + real ask (70) ---
    n = 0
    for prefix in _AMBIGUOUS_PREFIXES:
        for vendor in _VENDORS[:7]:
            n += 1
            job = _JOBS[n % len(_JOBS)]
            msg = f"{prefix} {job} in {vendor}"
            items.append(_item(f"ambiguous_{n:03d}", msg, "fallthrough", family="ambiguous"))

    # --- multi-clause (84) ---
    n = 0
    for vendor in _VENDORS:
        for tail in _MULTI_CLAUSE_TAILS:
            n += 1
            msg = f"Set it up in {vendor}, { _JOBS[0] }, {tail}."
            items.append(_item(f"multi_{n:03d}", msg, "fallthrough", family="multi_clause"))

    # --- edge / unicode / quoted copy (70) ---
    n = 0
    base_ads = (
        "Set it up in Google Ads. Ad groups include \"AI agent for Salesforce\" "
        "and \"AI agent for HubSpot\". Don't execute without my approval first."
    )
    for affix in _EDGE_AFFIXES:
        n += 1
        try:
            msg = affix(base_ads)
        except Exception:  # noqa: BLE001
            msg = base_ads
        items.append(_item(f"edge_{n:03d}", msg, "fallthrough", family="edge"))
    for vendor in _VENDORS:
        n += 1
        msg = (
            f"this is infuriating — check that my {vendor} account is actually connected"
        )
        items.append(_item(f"edge_{n:03d}", msg, "fallthrough", family="edge"))
        n += 1
        msg = f"Show me where I can verify the enterprise campaign in {vendor}."
        items.append(_item(f"edge_{n:03d}", msg, "fallthrough", family="edge"))

    # --- prioritization / signal-scoring prompts (40) ---
    priority_templates = (
        "who should I prioritize this week",
        "who should I focus this week in sales",
        "top prospects to call this week",
        "prioritize my pipeline for the next five days",
        "which accounts have hiring momentum I should work",
        "rank opportunities by engagement and tech adoption",
        "MSP: which clients have the highest severity vulnerabilities this week",
        "priority list — sales, hiring plus engagement, cite sources",
    )
    n = 0
    for tmpl in priority_templates:
        for vendor in ("HubSpot", "Apollo", "Clay", "NVD", ""):
            n += 1
            msg = f"{tmpl} using {vendor}".strip() if vendor else tmpl
            items.append(_item(f"priority_{n:03d}", msg, "fallthrough", family="prioritize"))

    # --- known live Ads brief variants (keep as anchors) ---
    items.append(
        _item(
            "anchor_ads_brief",
            "Set it up in Google Ads. Create four campaigns. Don't execute without my approval.",
            "fallthrough",
            family="anchor",
        )
    )
    items.append(
        _item(
            "anchor_ads_quoted_salesforce",
            'Set it up in Google Ads. Ad groups include "AI agent for Salesforce". Don\'t execute.',
            "fallthrough",
            family="anchor",
        )
    )
    items.append(
        _item(
            "anchor_hubspot_connected",
            "check that my HubSpot account is actually connected",
            "fallthrough",
            family="anchor",
        )
    )

    # --- narrow FAQ that MUST shortcut (proven Intent Gateway candidates) ---
    items.append(
        _item(
            "shortcut_001",
            "In the Gravitre sidebar, which primary nav item holds Enterprise, Federation, and Environments?",
            "shortcut",
            family="shortcut_seed",
        )
    )
    # Greetings / social: reported honestly, not required to shortcut.
    social = (
        "Hi",
        "hello there",
        "thanks",
        "good morning",
        "what can you help with in one sentence",
    )
    n = 0
    for msg in social:
        n += 1
        items.append(_item(f"social_{n:03d}", msg, "shortcut", family="social_report"))

    # De-dupe by message while keeping first expected.
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for row in items:
        key = " ".join((row["message"] or "").split())
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def corpus_stats(items: list[dict[str, str]] | None = None) -> dict[str, int]:
    rows = items if items is not None else build_adversarial_nlu_corpus()
    by_family: dict[str, int] = {}
    by_expected: dict[str, int] = {}
    for row in rows:
        by_family[row["family"]] = by_family.get(row["family"], 0) + 1
        by_expected[row["expected"]] = by_expected.get(row["expected"], 0) + 1
    return {
        "total": len(rows),
        **{f"family_{k}": v for k, v in by_family.items()},
        **{f"expected_{k}": v for k, v in by_expected.items()},
    }
