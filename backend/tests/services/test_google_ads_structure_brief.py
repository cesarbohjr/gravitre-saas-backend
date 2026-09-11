"""Google Ads brief → structure.create args (typed/spoken share this parser)."""

from app.services.chat_action_mapper import get_chat_action_mapper
from app.services.google_ads_structure_brief import (
    extract_google_ads_structure_args,
    format_google_ads_structure_plan_details,
    parse_daily_budget_total,
)
from app.services.parameter_ledger import quoted_strings
from tests.services.task_execution_parity_fixtures import (
    GOOGLE_ADS_CAMPAIGN_BRIEF,
    GOOGLE_ADS_CAMPAIGN_BRIEF_LIVE,
)


def test_dont_apostrophe_is_not_a_quoted_title() -> None:
    quotes = quoted_strings(GOOGLE_ADS_CAMPAIGN_BRIEF_LIVE)
    assert quotes
    assert not any(q.lower().startswith("t execute") for q in quotes)
    assert "Problem Aware" in quotes
    assert "Free Trial Signup" in quotes


def test_live_brief_parses_four_named_campaigns() -> None:
    args = extract_google_ads_structure_args(GOOGLE_ADS_CAMPAIGN_BRIEF_LIVE)
    assert args is not None
    names = [c["name"] for c in args["campaigns"]]
    assert names == [
        "RevOps / Sales Ops",
        "IT / Security Ops",
        "DevOps / Engineering Leaders",
        "Customer Support Ops",
    ]
    assert args["campaigns"][0]["budget_weight"] == 0.3
    assert args["campaigns"][2]["budget_weight"] == 0.2
    assert args["campaigns"][0]["bidding_strategy"] == "MAXIMIZE_CONVERSIONS"
    assert args["campaigns"][1]["bidding_strategy"] == "TARGET_CPA"
    groups = {g["name"] for c in args["campaigns"] for g in c.get("ad_groups") or []}
    assert {"Problem Aware", "Solution Aware", "Ready to Buy"} <= groups
    ready = next(
        g
        for g in args["campaigns"][0]["ad_groups"]
        if g["name"] == "Ready to Buy"
    )
    assert all(k["match_type"] == "EXACT" for g in [ready] for k in g["keywords"])
    problem = next(
        g
        for g in args["campaigns"][0]["ad_groups"]
        if g["name"] == "Problem Aware"
    )
    assert all(k["match_type"] == "PHRASE" for k in problem["keywords"])
    assert "gravitee" in args["negative_keywords"]
    assert "open source" in args["negative_keywords"]
    conv = [c["name"] for c in args["conversion_actions"]]
    assert conv == ["Free Trial Signup", "Demo Request"]
    assert "daily_budget_total" not in args
    assert args["status"] == "PAUSED"
    assert "t execute" not in str(args).lower()


def test_short_parity_brief_still_parses_campaign_names() -> None:
    args = extract_google_ads_structure_args(GOOGLE_ADS_CAMPAIGN_BRIEF)
    assert args is not None
    names = [c["name"] for c in args["campaigns"]]
    assert "RevOps / Sales Ops" in names
    assert "Customer Support Ops" in names
    assert parse_daily_budget_total(GOOGLE_ADS_CAMPAIGN_BRIEF) is None


def test_plan_copy_lists_campaigns_and_does_not_invent_budget() -> None:
    args = extract_google_ads_structure_args(GOOGLE_ADS_CAMPAIGN_BRIEF_LIVE)
    copy = format_google_ads_structure_plan_details(args)
    assert "RevOps / Sales Ops" in copy
    assert "Problem Aware" in copy
    assert "I will not invent one" in copy
    assert "t execute" not in copy


def test_daily_budget_requires_currency_not_random_numbers() -> None:
    assert parse_daily_budget_total("AI agent platform 50 integrations") is None
    assert parse_daily_budget_total("first 3 weeks") is None
    assert parse_daily_budget_total("yes, $200/day") == 200.0


def test_chat_mapper_stages_campaigns_not_dont_fragment() -> None:
    match = get_chat_action_mapper().match_segment(
        GOOGLE_ADS_CAMPAIGN_BRIEF_LIVE,
        connected_integrations=["google_ads"],
    )
    assert match is not None
    assert "structure.create" in match.entry.action_key
    assert match.args.get("name") is None
    assert match.args.get("summary") is None
    assert "intent_text" not in (match.args.get("payload") or {})
    names = [c["name"] for c in match.args["campaigns"]]
    assert names[0] == "RevOps / Sales Ops"
    assert len(names) == 4
